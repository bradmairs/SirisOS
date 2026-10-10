"""Career module (ADR 110): Engineers Australia CPD import, the rolling
three-year summary, pathways, evidence and goals."""

from __future__ import annotations

import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.career import cpd, store
from app.entrypoint import app
from tests.test_hub import AUTH

TODAY = date(2026, 10, 10)

EA_CSV = """﻿Start Date,End Date,Activity Type,Activity Title,Provider,Hours,Risk Management Hours,Business and Management Hours,Area of Practice Hours,Notes
05/09/2026,05/09/2026,Short course,Stormwater design to AR&R 2019,IPWEA,7,0,0,7,Updated hydrology methods
12/06/2026,12/06/2026,Conference,Ozwater 2026,AWA,14,2,3,9,
20/02/2025,20/02/2025,Webinar,Safe design in water infrastructure,Engineers Australia,1.5,1.5,0,0,
14/11/2022,14/11/2022,Course,Project management fundamentals,WSP,8,0,8,0,
01/01/2022,01/01/2022,Course,Too old to count,WSP,20,0,0,20,
,,,Total,,50.5,,,,
"""


def _xlsx(rows: list[list[object]]) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.append(["Engineers Australia CPD record"])  # a title row above the table
    sheet.append([])
    for row in rows:
        sheet.append(row)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


@pytest.fixture
def career_file(tmp_path, monkeypatch):
    path = tmp_path / "career.json"
    monkeypatch.setenv("SIRISOS_CAREER_PATH", str(path))
    return path


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# -- parsing ------------------------------------------------------------------


def test_parses_an_engineers_australia_csv_with_category_hours() -> None:
    records = cpd.parse(EA_CSV.encode(), "cpd-export.csv")
    assert [r.title for r in records][:2] == ["Stormwater design to AR&R 2019", "Ozwater 2026"]
    assert len(records) == 5  # the Total row is skipped
    ozwater = records[1]
    assert ozwater.date == "2026-06-12" and ozwater.provider == "AWA" and ozwater.type == "Conference"
    assert ozwater.split == {"risk": 2, "business": 3, "area": 9} and ozwater.basis == "export"


def test_guesses_categories_when_the_export_has_only_hours() -> None:
    raw = ("Date;Activity;Duration;Provider\n"
           "3/10/2026;Pump station design workshop;2h 30m;GVW\n"
           "4/10/2026;Working at heights refresher;1:30;Pinnacle Safety\n"
           "5/10/2026;Leadership for engineers;3;EA\n"
           "6/10/2026;Toastmasters;1;Club\n").encode("cp1252")
    records = {r.title: r for r in cpd.parse(raw, "cpd.csv")}
    assert records["Pump station design workshop"].hours == 2.5
    assert records["Pump station design workshop"].split == {"area": 2.5}
    assert records["Working at heights refresher"].split == {"risk": 1.5}
    assert records["Leadership for engineers"].split == {"business": 3}
    assert records["Toastmasters"].split == {"other": 1} and records["Toastmasters"].basis == "guess"


def test_reads_excel_below_a_title_row_and_excel_dates() -> None:
    from datetime import datetime

    raw = _xlsx([
        ["Date", "Title", "Type", "CPD Hours"],
        [datetime(2026, 8, 1), "Civil 3D pipe networks", "Course", 6],
        [46000, "Contract law for engineers", "Seminar", "2"],
    ])
    records = cpd.parse(raw, "export.xlsx")
    assert [(r.date, r.title, r.hours) for r in records] == [
        ("2026-08-01", "Civil 3D pipe networks", 6.0),
        ("2025-12-09", "Contract law for engineers", 2.0),
    ]


@pytest.mark.parametrize("raw,name,message", [
    (b"%PDF-1.4", "report.pdf", "export your CPD as CSV or Excel"),
    (b"a,b,c\n1,2,3\n", "x.csv", "Couldn't find the CPD table"),
    (b"Title,Hours\nSomething,0\n", "x.csv", "no activities with hours"),
    (b"x" * (cpd.MAX_UPLOAD_BYTES + 1), "x.csv", "larger than 5 MB"),
])
def test_explains_files_it_cannot_use(raw, name, message) -> None:
    with pytest.raises(cpd.CpdImportError, match=message):
        cpd.parse(raw, name)


def test_dates_and_hours_formats() -> None:
    assert cpd.parse_date("05/09/2026") == "2026-09-05"  # day first, Australian
    assert cpd.parse_date("2026-09-05T00:00:00") == "2026-09-05"
    assert cpd.parse_date("5 Sep 2026") == "2026-09-05"
    assert cpd.parse_date("nonsense") is None
    assert cpd.parse_hours("1,5") == 1.5 and cpd.parse_hours("45m") == 0.75 and cpd.parse_hours("") == 0


# -- merge and summary ----------------------------------------------------------


def test_reimporting_never_duplicates(career_file) -> None:
    doc, first = cpd.merge(store.load(), cpd.parse(EA_CSV.encode(), "a.csv"), "a.csv")
    assert (first.added, first.updated, first.unchanged) == (5, 0, 0)
    doc, again = cpd.merge(store.load(), cpd.parse(EA_CSV.encode(), "a.csv"), "a.csv")
    assert (again.added, again.unchanged) == (0, 5) and len(doc.cpd.records) == 5
    newer = EA_CSV.replace("Updated hydrology methods", "Updated hydrology methods (ARR)")
    doc, changed = cpd.merge(store.load(), cpd.parse(newer.encode(), "b.csv"), "b.csv")
    assert changed.updated == 1 and len(doc.cpd.records) == 5
    assert [i.filename for i in doc.cpd.imports] == ["b.csv", "a.csv", "a.csv"]


def test_summary_counts_the_rolling_three_years_against_the_minimums(career_file) -> None:
    doc, _ = cpd.merge(store.load(), cpd.parse(EA_CSV.encode(), "a.csv"), "a.csv")
    s = cpd.summary(doc, today=TODAY)
    assert s["window"] == {"from": "2023-10-10", "to": "2026-10-10", "years": 3}
    # 2022 activities fall outside the window.
    assert s["total"] == 22.5 and s["short"] == 127.5 and s["met"] is False
    assert s["categories"] == {"area": 16.0, "risk": 3.5, "business": 3.0, "other": 0.0}
    assert {m["category"]: m["short"] for m in s["minimums"]} == {"area": 34.0, "risk": 6.5, "business": 12.0}
    assert s["by_year"] == {"2025": 1.5, "2026": 21.0}
    assert s["latest_activity"] == "2026-09-05"


def test_hours_about_to_leave_the_window_are_flagged(career_file) -> None:
    raw = "Date,Title,Hours\n01/12/2023,Old seminar,4\n01/06/2026,Recent course,3\n".encode()
    doc, _ = cpd.merge(store.load(), cpd.parse(raw, "x.csv"), "x.csv")
    assert cpd.summary(doc, today=TODAY)["expiring_90_days"] == 4


# -- API --------------------------------------------------------------------------


def test_career_requires_login(client, career_file) -> None:
    assert client.get("/api/v1/career").status_code == 401


def test_first_look_is_seeded_with_the_pathways_and_16_elements(client, career_file) -> None:
    body = client.get("/api/v1/career", headers=AUTH).json()
    doc, ov = body["document"], body["overview"]
    assert [p["id"] for p in doc["pathways"]] == ["ea-member", "cpeng", "ner", "vic-rpe"]
    assert len(doc["elements"]) == 16 and doc["elements"][0]["title"] == "Deal with ethical issues"
    assert ov["competencies"] == {**ov["competencies"], "total": 16, "evidenced": 0}
    assert ov["next_steps"][0] == {"title": "Qualification recognised", "detail": "Engineers Australia membership", "kind": "pathway"}
    assert any(s["kind"] == "cpd" for s in ov["next_steps"])
    assert not career_file.exists()  # nothing written until something changes


def test_editing_progress_goals_and_evidence(client, career_file) -> None:
    doc = client.get("/api/v1/career", headers=AUTH).json()["document"]
    doc["pathways"][0]["steps"][0]["status"] = "done"
    doc["goals"] = [{"title": "Chartered by mid 2027", "target_date": "2027-06-30", "next_step": "Draft element 6 claim"}]
    doc["evidence"] = [{"title": "Pump station upgrade risk workshop", "elements": ["6", "5", "6", "99"],
                        "links": [{"label": "CPEng Chartership", "url": "/brain?q=CPEng%20Chartership"}]}]
    edit = {k: doc[k] for k in ("profile", "pathways", "evidence", "goals")}
    body = client.put("/api/v1/career", json=edit, headers=AUTH).json()
    assert body["document"]["evidence"][0]["elements"] == ["6", "5"]  # deduped, unknown ids dropped
    ov = body["overview"]
    assert ov["pathways"][0]["done"] == 1 and ov["pathways"][0]["next"]["title"] == "Join as a Member (MIEAust)"
    assert ov["competencies"]["evidenced"] == 2 and ov["competencies"]["counts"]["6"] == 1
    assert {"title": "Draft element 6 claim", "detail": "Chartered by mid 2027", "kind": "goal"} in ov["next_steps"]
    assert career_file.exists()
    # The PUT can't touch CPD.
    assert client.get("/api/v1/career", headers=AUTH).json()["document"]["cpd"]["records"] == []


def test_import_upload_and_recategorise(client, career_file) -> None:
    files = {"file": ("ea-cpd.csv", EA_CSV.encode(), "text/csv")}
    body = client.post("/api/v1/career/cpd/import", files=files, headers=AUTH).json()
    assert body["import"]["added"] == 5 and body["overview"]["cpd"]["records"] == 5
    rid = next(r["id"] for r in body["document"]["cpd"]["records"] if r["title"] == "Ozwater 2026")
    r = client.put(f"/api/v1/career/cpd/{rid}/category", json={"category": "business"}, headers=AUTH).json()
    assert r["document"]["cpd"]["overrides"] == {rid: "business"}
    # A re-import keeps the correction.
    again = client.post("/api/v1/career/cpd/import", files=files, headers=AUTH).json()
    assert again["document"]["cpd"]["overrides"] == {rid: "business"} and again["import"]["unchanged"] == 5
    assert client.put(f"/api/v1/career/cpd/{rid}/category", json={"category": None}, headers=AUTH).json()["document"]["cpd"]["overrides"] == {}
    assert client.put("/api/v1/career/cpd/nope/category", json={"category": "risk"}, headers=AUTH).status_code == 404
    bad = client.post("/api/v1/career/cpd/import", files={"file": ("r.pdf", b"%PDF", "application/pdf")}, headers=AUTH)
    assert bad.status_code == 422 and "CSV or Excel" in bad.json()["detail"]


def test_search_and_brief_see_career(client, career_file) -> None:
    from app.brief import service as brief_service
    from app.search import service as search_service

    doc = client.get("/api/v1/career", headers=AUTH).json()["document"]
    doc["goals"] = [{"title": "Chartered by mid 2027", "next_step": "Book the interview"}]
    client.put("/api/v1/career", json={k: doc[k] for k in ("profile", "pathways", "evidence", "goals")}, headers=AUTH)
    client.post("/api/v1/career/cpd/import", files={"file": ("ea.csv", EA_CSV.encode(), "text/csv")}, headers=AUTH)

    hits = search_service.career_source("chartered")
    assert hits[0]["title"] == "Chartered by mid 2027" and hits[0]["url"] == "/career?view=goals"
    assert any(h["kind"] == "step" for h in hits)  # the "Chartered" pathway steps
    assert [h["title"] for h in search_service.career_source("ozwater")] == ["Ozwater 2026"]

    brief = brief_service._career()
    assert brief["cpd"]["records"] == 5 and brief["goals"] == [{"title": "Chartered by mid 2027", "target_date": None}]
    assert brief["next_steps"][0]["detail"] == "Engineers Australia membership"
