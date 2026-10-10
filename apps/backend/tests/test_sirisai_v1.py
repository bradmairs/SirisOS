"""SirisAI's hub contract v1 (ADR 110), as SirisOS uses it: the brief, search,
inbox, protocols, cameras, guest mode and SirisHydro, against a fake SirisAI
that answers with the contract's own example payloads
(tests/contracts/sirisai-hub-v1/, copied from SirisAI by
scripts/sync-sirisai-contract.sh)."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app.attention import service as attention
from app.brief import news
from app.brief import service as brief_service
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from tests.test_hub import AUTH

CONTRACT = Path(__file__).parent / "contracts" / "sirisai-hub-v1"


def example(name: str) -> dict:
    return json.loads((CONTRACT / f"{name}.json").read_text())


class FakeSirisAI:
    """SirisAI with the hub contract, answering from the examples."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.brief = example("brief")
        self.info = example("info")
        self.attention = example("attention")
        self.stream_events = [example("attention_event")]
        self.llm_text = "1.65% for DN 100 [1]."

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host in ("news.google.com", "www.abc.net.au"):
            return httpx.Response(503)
        if request.url.host != "sirisai":
            return httpx.Response(404)
        self.requests.append(request)
        assert request.headers["authorization"] == "Bearer ai-key"
        path = request.url.path
        if path == "/siris/hub/v1":
            return httpx.Response(200, json=self.info)
        if path == "/siris/hub/v1/brief":
            return httpx.Response(200, json=self.brief)
        if path == "/siris/hub/v1/widgets":
            return httpx.Response(200, json=example("widgets"))
        if path == "/siris/hub/v1/search":
            return httpx.Response(200, json=example("search"))
        if path == "/siris/hub/v1/attention":
            return httpx.Response(200, json=self.attention)
        if path == "/siris/hub/v1/attention/stream":
            body = "".join(f"data: {json.dumps(e)}\n\n" for e in self.stream_events)
            return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
        if path.startswith("/siris/hub/v1/attention/") and path.endswith("/act"):
            item = copy.deepcopy(self.attention["items"][0])
            item["status"] = "done"
            assert json.loads(request.content) == {"action": "approve"}
            return httpx.Response(200, json={"item": item, "result": {"ok": True}})
        if path == "/siris/hub/v1/protocols/lockdown":
            return httpx.Response(200, json=example("protocol_preview"))
        if path == "/siris/hub/v1/protocols/lockdown/run":
            if not json.loads(request.content).get("confirmed"):
                return httpx.Response(409, json={"detail": {"message": "confirm first", "preview": example("protocol_preview")}})
            return httpx.Response(200, json=example("protocol_run"))
        if path == "/siris/hub/v1/cameras/front_door/look":
            return httpx.Response(200, json=example("camera_look"))
        if path == "/siris/cameras/front_door/latest.jpg":
            return httpx.Response(200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"})
        if path == "/siris/hub/v1/llm/complete":
            body = json.loads(request.content)
            assert body["task"] == "sirishydro" and "[1]" in body["prompt"]
            return httpx.Response(200, json={"text": self.llm_text, "role": "general", "model": "m"})
        if path == "/siris/status":
            return httpx.Response(200, json={"llm_provider": "ollama"})
        return httpx.Response(404, json={"detail": "not found"})


@pytest.fixture
def ai(monkeypatch, tmp_path):
    fake = FakeSirisAI()
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(fake))
    monkeypatch.setattr(brief_service, "brief_service", brief_service.BriefService())
    monkeypatch.setattr(brief_service, "news_service", news.NewsService())
    monkeypatch.setenv("SIRISOS_BRIEF_STATE_PATH", str(tmp_path / "brief.json"))
    monkeypatch.setenv("SIRISOS_ATTENTION_STATE_PATH", str(tmp_path / "attention.json"))
    reset_hub({"SIRISAI_URL": "http://sirisai:8000", "SIRISAI_API_KEY": "ai-key", "SIRISAI_USER": "brad",
               "APD_PM_URL": "http://apd:8080", "APD_PM_EMAIL": "e", "APD_PM_PASSWORD": "p"})
    yield fake
    reset_hub({})


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_requests_say_who_is_asking(client, ai) -> None:
    client.get("/api/v1/assistant/info", headers=AUTH)
    sent = ai.requests[-1].headers
    assert sent["x-siris-client"] == "SirisOS" and sent["x-siris-user"] == "brad"


def test_the_contract_brief_becomes_the_daily_brief(ai) -> None:
    parts, failed = brief_service.parts_from_hub(example("brief"))
    brief = brief_service.compose(datetime(2026, 10, 9, 6, 30, tzinfo=ZoneInfo("Australia/Melbourne")), "brad", parts, failed)
    assert brief["headline"] == [
        "1 urgent thing in your inbox.",
        "19° today, slight rain, 70% chance of rain: take a jacket.",
        "2 things on today, starting with Site visit, Werribee at 10:30 am.",
        "1 task overdue or due today, starting with Send Werribee levels to Dana.",
        "1 important email, from Dana Lee.",
        "2 things waiting in the Second Brain inbox.",
    ]
    assert brief["email"] == {"unread": 2, "important": [{"from": "Dana Lee", "subject": "Drainage report comments"}]}
    # Each event names its calendar (Gmail, an iCloud calendar), shown in the schedule.
    assert [(e["title"], e["calendar"]) for e in brief["schedule"]] == [("Bin night", "Home"), ("Site visit, Werribee", "Work")]
    assert brief["todo"] == ["Milk"] and brief["health"][0] == "Slept 6.1 h"
    assert brief["home"][0] == "Parcel: New drill in transit"
    assert "24%" in brief["home"][1] and brief["home"][1].endswith("Low and not plugged in.")
    assert brief["brain"]["inbox"] == 2 and brief["brain"]["unsure_links"] == 1
    assert brief["attention"] == example("brief")["attention"] and brief["guest_mode"] is False


def test_brief_endpoint_uses_one_hub_call(client, ai) -> None:
    brief = client.get("/api/v1/brief", headers=AUTH).json()
    paths = [r.url.path for r in ai.requests]
    assert "/siris/hub/v1/brief" in paths
    assert not any(p.startswith("/siris/tools/") for p in paths) and "/siris/brain/insights" not in paths
    assert brief["schedule"][0]["title"] == "Bin night" and brief["unavailable"] == ["news"]


def test_guest_mode_brief_and_widgets(client, ai) -> None:
    ai.brief = {**example("brief"), "guest_mode": True, "hidden": ["calendar", "email"], "calendar": None, "email": None,
                "health": None, "car": None, "parcels": None, "brain": None, "todo": None}
    ai.info = {**example("info"), "guest_mode": True}
    brief = client.get("/api/v1/brief", headers=AUTH).json()
    assert brief["guest_mode"] is True and brief["email"] is None and brief["schedule"] == []
    widgets = client.get("/api/v1/hub/widgets", headers=AUTH).json()
    assert widgets["guest_mode"] is True
    assert not {"sirisai", "second-brain"} & {w["app_id"] for w in widgets["widgets"]}


def test_search_uses_the_hub_search(client, ai) -> None:
    result = client.get("/api/v1/search", params={"q": "Hazen-Williams"}, headers=AUTH).json()
    groups = {g["id"]: g for g in result["groups"]}
    assert groups["brain"]["hits"][0]["url"] == "/brain?q=Hazen-Williams"
    assert sum(r.url.path == "/siris/hub/v1/search" for r in ai.requests) == 1  # shared by every SirisAI group
    assert not any(r.url.path.startswith("/siris/tools/") for r in ai.requests)


def test_protocols_cameras_widgets(client, ai) -> None:
    assert client.get("/api/v1/assistant/widgets", headers=AUTH).json()["protocols"]
    assert client.get("/api/v1/assistant/protocols/lockdown", headers=AUTH).json()["name"] == "lockdown"
    held = client.post("/api/v1/assistant/protocols/lockdown/run", json={}, headers=AUTH)
    assert held.status_code == 409 and held.json()["detail"]["preview"]["name"] == "lockdown"
    ran = client.post("/api/v1/assistant/protocols/lockdown/run", json={"confirmed": True}, headers=AUTH)
    assert ran.status_code == 200 and ran.json()["can_undo"] is True
    look = client.post("/api/v1/assistant/cameras/front_door/look", json={"question": "Who's there?"}, headers=AUTH).json()
    assert look["description"].startswith("A courier")
    frame = client.get("/api/v1/assistant/cameras/front_door/latest.jpg", headers=AUTH)
    assert frame.status_code == 200 and frame.content.startswith(b"\xff\xd8")
    assert client.get("/api/v1/assistant/cameras/..%2Fstatus/latest.jpg", headers=AUTH).status_code in (404, 422)


def test_inbox_merges_sirisai_and_sirisos_items(client, ai, monkeypatch) -> None:
    async def apps(self, fresh=False, with_widgets=False):  # noqa: ANN001
        return [
            {"id": "apd-pm", "name": "Project Management", "launch_url": "https://pm", "status": {"state": "ok"},
             "widget": {"metrics": [{"label": "Overdue", "value": "2"}], "items": [{"title": "Submit RFI", "tone": "critical"}]}},
            {"id": "archive", "name": "Engineering Archive", "launch_url": None, "status": {"state": "down", "detail": "Timed out"}, "widget": None},
        ]

    monkeypatch.setattr(hub_service.Hub, "apps", apps)
    inbox = client.get("/api/v1/attention", headers=AUTH).json()
    ids = [i["id"] for i in inbox["items"]]
    assert ids[0].startswith("ai:")  # the urgent SirisAI alert sorts first
    assert "os:app:archive:down" in ids and any(i.startswith("os:apd:overdue:2:") for i in ids)
    assert inbox["counts"]["urgent"] == 1 and inbox["unavailable"] == []

    # SirisAI items act through SirisAI...
    confirm = next(i for i in inbox["items"] if i["kind"] == "confirm")
    done = client.post(f"/api/v1/attention/{confirm['id']}/act", json={"action": "approve"}, headers=AUTH)
    assert done.status_code == 200 and done.json()["result"] == {"ok": True}
    # ...SirisOS's own can only be dismissed, and stay dismissed until they change.
    assert client.post("/api/v1/attention/os:app:archive:down/act", json={"action": "approve"}, headers=AUTH).status_code == 422
    assert client.post("/api/v1/attention/os:app:archive:down/dismiss", headers=AUTH).status_code == 200
    after = [i["id"] for i in client.get("/api/v1/attention", headers=AUTH).json()["items"]]
    assert "os:app:archive:down" not in after
    assert client.post("/api/v1/attention/nope/act", json={"action": "x"}, headers=AUTH).status_code == 404


def test_inbox_survives_sirisai_being_down(client, ai, monkeypatch) -> None:
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(lambda r: httpx.Response(503)))
    inbox = client.get("/api/v1/attention", headers=AUTH).json()
    assert inbox["unavailable"] == ["SirisAI"]
    assert any(i["id"] == "os:app:sirisai:down" or i["title"].startswith("SirisAI is") for i in inbox["items"])


def test_inbox_stream_relays_sirisai_events(client, ai) -> None:
    upsert = {"type": "upsert", "items": [{**example("attention")["items"][0], "id": 99, "title": "SirisAI: person at front_door"}],
              "counts": {"open": 4, "urgent": 2}}
    ai.stream_events = [example("attention_event"), upsert]
    body = client.get("/api/v1/attention/stream", params={"max_events": 2}, headers=AUTH).text
    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert events[0]["type"] == "snapshot" and events[1]["type"] == "upsert"
    assert events[1]["items"][0]["id"] == "ai:99" and events[1]["items"][0]["origin"] == "sirisai"


def test_sirishydro_synthesis_goes_through_sirisai(client, ai, monkeypatch, tmp_path) -> None:
    from app.api import sirishydro
    from app.services.engineering_standards_evidence import EngineeringEvidence

    evidence = EngineeringEvidence(document_id="d", title="Sanitary", authority="SA", reference="AS/NZS 3500.2", edition="2021",
                                   page=41, citation="AS/NZS 3500.2:2021 p.41", excerpt="minimum grade of 1.65% for DN 100", score=80)
    monkeypatch.setattr(sirishydro, "assemble_evidence", lambda q, limit: [evidence])
    monkeypatch.setattr(sirishydro, "HISTORY_PATH", tmp_path / "h.json")
    result = client.get("/api/v1/engineering/sirishydro/evidence", params={"question": "minimum grade DN 100"}, headers=AUTH).json()
    assert result["synthesized_answer"] == "1.65% for DN 100 [1]."

    ai.llm_text = ""  # SirisAI said nothing useful: fall back to SirisOS's own model (not configured here -> None)
    result = client.get("/api/v1/engineering/sirishydro/evidence", params={"question": "minimum grade DN 100"}, headers=AUTH).json()
    assert result["synthesized_answer"] is None and result["sufficient_evidence"] is True


def test_every_contract_example_is_present() -> None:
    names = {p.stem for p in CONTRACT.glob("*.json")}
    assert {"schema", "brief", "widgets", "search", "attention", "attention_event", "attention_act", "info",
            "protocol_preview", "protocol_run", "camera_look", "llm_complete"} <= names
