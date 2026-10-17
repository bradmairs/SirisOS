"""Stage 2 competency claim drafts: built from tagged evidence, saved to Siris."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.career import claims, store
from app.entrypoint import app
from app.hub import service
from app.hub.service import reset_hub
from tests.test_hub import AUTH


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_CAREER_PATH", str(tmp_path / "career.json"))
    return TestClient(app)


def _with_evidence(client):
    doc = client.get("/api/v1/career", headers=AUTH).json()["document"]
    doc["evidence"] = [
        {"title": "Pump station risk workshop", "date": "2026-03-04", "elements": ["6", "5"],
         "summary": "Ran the HAZOP for the Shepparton pump station upgrade; 14 actions closed.",
         "links": [{"label": "Workshop notes", "url": "/brain?q=HAZOP"}]},
        {"title": "Older risk review", "date": "2025-01-10", "elements": ["6"], "summary": ""},
    ]
    client.put("/api/v1/career", headers=AUTH, json={k: doc[k] for k in ("profile", "pathways", "evidence", "goals")})


def test_drafts_list_every_element_with_its_evidence(client):
    _with_evidence(client)
    elements = {e["id"]: e for e in client.get("/api/v1/career/claims", headers=AUTH).json()["elements"]}
    assert len(elements) == 16
    assert len(elements["6"]["evidence"]) == 2 and elements["1"]["evidence"] == []
    assert elements["6"]["note_title"] == "CPEng claim draft – E6 Identify, assess and manage risks"


def test_a_draft_uses_the_evidence_newest_first_and_leaves_the_claim_to_finish(client):
    _with_evidence(client)
    body = client.get("/api/v1/career/claims/6", headers=AUTH).json()
    md = body["markdown"]
    assert md.index("Pump station risk workshop (2026-03-04)") < md.index("Older risk review (2025-01-10)")
    assert "14 actions closed" in md and "[Workshop notes](/brain?q=HAZOP)" in md
    assert "_No summary yet" in md  # the older one has no summary
    assert "**How this shows identify, assess and manage risks:**" in md
    assert body["prose"] is None and body["prose_available"] is False

    empty = client.get("/api/v1/career/claims/1", headers=AUTH).json()["markdown"]
    assert "No evidence tagged yet" in empty and "ethical" in empty
    assert client.get("/api/v1/career/claims/99", headers=AUTH).status_code == 404


def test_prose_comes_from_the_local_model_only_with_evidence(client):
    _with_evidence(client)

    class Model:
        enabled = True
        prompts: list[str] = []

        async def complete(self, *, system: str, prompt: str) -> str:
            self.prompts.append(prompt)
            assert "never invent" in system
            return "In March 2026 I ran the HAZOP…"

    doc = store.load()
    model = Model()
    assert asyncio.run(claims.prose(doc, claims.element(doc, "6"), model)) == "In March 2026 I ran the HAZOP…"
    assert "14 actions closed" in model.prompts[0]
    assert asyncio.run(claims.prose(doc, claims.element(doc, "1"), model)) is None


def test_saving_a_draft_captures_it_into_the_second_brain(client, monkeypatch):
    _with_evidence(client)
    assert client.post("/api/v1/career/claims/6/save", headers=AUTH, json={"markdown": "x"}).status_code == 503

    captured = []

    def sirisai(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/siris/brain/capture"
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"saved": True, "action": "created", "path": "00-Inbox/x.md", "title": "t"})

    monkeypatch.setattr(service, "transport", httpx.MockTransport(sirisai))
    reset_hub({"SIRISAI_URL": "http://sirisai:8000", "SIRISAI_API_KEY": "ai-key"})
    try:
        saved = client.post("/api/v1/career/claims/6/save", headers=AUTH, json={"markdown": "My claim"}).json()
    finally:
        reset_hub({})
    assert saved == {"saved": True, "title": "CPEng claim draft – E6 Identify, assess and manage risks", "action": "created", "path": "00-Inbox/x.md"}
    assert captured == [{"title": saved["title"], "text": "My claim", "tags": ["career", "cpeng", "competency-claim"]}]
