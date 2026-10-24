"""4.6: the Chartered application forms in Career."""

from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.career import application, cpd, store
from app.entrypoint import app
from tests.test_career import EA_CSV
from tests.test_hub import AUTH


@pytest.fixture
def career_file(tmp_path, monkeypatch):
    path = tmp_path / "career.json"
    monkeypatch.setenv("SIRISOS_CAREER_PATH", str(path))
    return path


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_old_career_files_get_the_new_cpeng_steps_once(career_file):
    doc = store.seeded()
    cpeng = next(p for p in doc.pathways if p.id == "cpeng")
    cpeng.steps = [s for s in cpeng.steps if s.id not in ("reflection", "cpd-evidence", "bia")]
    cpeng.steps[0].status = "done"
    raw = json.loads(doc.model_dump_json())
    raw.pop("defaults_version")
    raw.pop("application")
    career_file.write_text(json.dumps(raw))

    loaded = store.load()
    ids = [s.id for s in next(p for p in loaded.pathways if p.id == "cpeng").steps]
    assert ids[:5] == ["self-assess", "reflection", "cpd-evidence", "bia", "evidence"]
    assert next(p for p in loaded.pathways if p.id == "cpeng").steps[0].status == "done"

    # Removed after the upgrade: stays removed.
    cpeng = next(p for p in loaded.pathways if p.id == "cpeng")
    cpeng.steps = [s for s in cpeng.steps if s.id != "bia"]
    store.save(loaded)
    assert "bia" not in [s.id for s in next(p for p in store.load().pathways if p.id == "cpeng").steps]


def test_readiness_moves_with_the_answers(career_file, client):
    r = client.get("/api/v1/career/application", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["readiness"]["percent"] == 0
    assert len(body["part1"]) == 19 and len(body["part2"]) == 4 and len(body["cpd_questions"]) == 16
    assert len(body["elements"]) == 16 and body["elements"][0]["meaning"]

    edit = {
        "area_of_practice": "Civil", "cpd_evidence": "questionnaire",
        "cpd_answers": {q["id"]: "N/A" for q in application.CPD_QUESTIONS} | {"bogus": "x"},
        "part1": {q["id"]: "yes" for q in application.PART1} | {"risk": "not_sure"},
        "part2": {q["id"]: "yes" for q in application.PART2},
        "part3": {"1": "On the Melrose pump station upgrade I raised a conflict of interest when a supplier offered hospitality during tender evaluation, and stepped back from scoring."},
        "signed": True,
        "bia": {"required": False},
    }
    r = client.put("/api/v1/career/application", headers=AUTH, json=edit)
    assert r.status_code == 200
    ready = {i["id"]: i for i in r.json()["readiness"]["items"]}
    assert all(ready[k]["done"] for k in ("aop", "cpd", "part1", "part2", "bia", "signed"))
    assert not ready["part3"]["done"] and ready["part3"]["detail"] == "1 of 16 written"
    assert r.json()["readiness"]["prepare"][0]["id"] == "risk"
    assert "bogus" not in r.json()["application"]["cpd_answers"]

    steps = client.get("/api/v1/career/overview", headers=AUTH).json()
    assert steps["application"]["percent"] == 75
    assert any(s["kind"] == "application" and "Not sure" in s["title"] for s in steps["next_steps"])


def test_building_industry_assessment_needs_its_documents(career_file):
    doc = store.load()
    doc.application.bia = store.Bia(required=True, state="VIC", cv=True)
    item = next(i for i in application.readiness(doc)["items"] if i["id"] == "bia")
    assert not item["done"]
    assert item["detail"] == "Victorian Building Industry Endorsement: still needs building-industry CPD, the experience statement"


def test_drafts_from_cpd_records_and_evidence(career_file):
    doc, _ = cpd.merge(store.load(), cpd.parse(EA_CSV.encode(), "cpd.csv"), "cpd.csv")
    text = application.cpd_draft(doc, "conferences", today=date(2026, 10, 10))
    assert text.startswith("About 14 hours") and "Ozwater 2026 (AWA), Jun 2026: 14 h" in text
    assert application.cpd_draft(doc, "academic") == "N/A"
    assert application.cpd_draft(doc, "mentoring", today=date(2026, 10, 10)) == ""

    doc.evidence = [store.Evidence(title="Melrose pump station", date="2026-05-01", elements=["11"],
                                   summary="I chose to bypass the failed valve overnight. It kept supply on.")]
    comment = application.element_draft(doc, "11")
    assert comment.startswith("On Melrose pump station (May 2026), i chose to bypass") or comment.startswith("On Melrose pump station (May 2026), I chose")
    assert application.element_draft(doc, "12") == ""


def test_upload_and_download_a_filled_in_form(career_file, client):
    r = client.post("/api/v1/career/application/reflection/file", headers=AUTH,
                    files={"file": ("Self reflection - Brad.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert r.status_code == 200
    assert r.json()["application"]["files"]["reflection"]["filename"] == "Self reflection - Brad.pdf"
    got = client.get("/api/v1/career/application/reflection/file", headers=AUTH)
    assert got.status_code == 200 and got.content == b"%PDF-1.4 test"
    assert client.post("/api/v1/career/application/reflection/file", headers=AUTH,
                       files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 422
    assert client.post("/api/v1/career/application/nope/file", headers=AUTH,
                       files={"file": ("x.pdf", b"%PDF", "application/pdf")}).status_code == 404
    assert client.delete("/api/v1/career/application/reflection/file", headers=AUTH).json()["application"]["files"] == {}
    assert client.get("/api/v1/career/application/reflection/file", headers=AUTH).status_code == 404
