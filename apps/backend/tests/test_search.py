"""Search everything (ADR 109), against mocked app HTTP."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import engineering_standards, projects, sirishydro
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.search import service
from tests.test_hub import AUTH, ENV, FakeApps


class SearchApps(FakeApps):
    def __init__(self) -> None:
        super().__init__()
        self.slow: set[str] = set()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host in self.slow:
            raise httpx.ReadTimeout("slow", request=request)
        if host == "archive" and path == "/api/external/search":
            assert request.headers["x-api-key"] == "ea_key"
            return httpx.Response(200, json={
                "query": request.url.params["q"],
                "assets": [{"id": "as1", "name": "Pump Station 4", "description": "", "assetType": "Pump station"}],
                "media": [{"id": "m1", "fileName": "DJI_0435.JPG", "kind": "photo", "capturedAt": "2026-09-30T01:00:00Z",
                           "locationName": None, "asset": {"id": "as1", "name": "Pump Station 4"}}],
                "files": [{"id": "f1", "fileName": "PS4 GA.pdf", "category": "Drawings", "asset": None}],
            })
        if host == "sirisai" and path == "/siris/brain/search":
            return httpx.Response(200, json=[
                {"title": "Pump curves", "path": "Resources/Pump curves.md", "type": "resource", "excerpts": ["Reading a pump curve…"]},
            ])
        if host == "sirisai" and path == "/siris/tools/search_conversations/run":
            args = json.loads(request.content)["arguments"]
            assert args["query"] == "pump"
            said = [
                {"conversation_id": "c1", "role": "user", "when": "2026-10-06T08:00:00+11:00", "text": "What size pump do I need for the new tank?"},
                {"conversation_id": "c1", "role": "assistant", "when": "2026-10-06T08:00:05+11:00", "text": "A pump of about 2 kW."},
                {"conversation_id": "c2", "role": "assistant", "when": "2026-10-01T09:00:00+10:00", "text": "The pump station report is due Friday."},
            ]
            return httpx.Response(200, json={"tool_call": {"name": "search_conversations", "arguments": args, "result": said}})
        return super().__call__(request)

    def apd(self, request: httpx.Request, path: str) -> httpx.Response:
        if path == "/api/search" and request.headers.get("cookie", "").startswith("apd_token=t"):
            return httpx.Response(200, json={"query": request.url.params["q"], "results": [
                {"type": "project", "typeLabel": "Project", "id": "p1", "projectId": "p1", "projectName": "Pump station upgrade",
                 "title": "Pump station upgrade", "subtitle": "Shepparton", "date": None},
                {"type": "rfi", "typeLabel": "RFI", "id": "r1", "projectId": "p1", "projectName": "Pump station upgrade",
                 "title": "RFI 12: pump pad levels", "subtitle": "Open", "date": None},
            ]})
        return super().apd(request, path)


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_LINKS_PATH", str(tmp_path / "links.json"))
    (tmp_path / "links.json").write_text(json.dumps({"groups": [{"id": "g", "name": "Work", "links": [
        {"id": "l1", "name": "Pump selector", "url": "https://pumps.example.com", "note": "Grundfos"},
        {"id": "l2", "name": "Bunnings", "url": "https://bunnings.com.au", "note": ""},
    ]}]}))
    monkeypatch.setattr(engineering_standards, "LIBRARY_ROOT", tmp_path / "standards")
    monkeypatch.setattr(projects, "PROJECTS_PATH", tmp_path / "projects.json")
    monkeypatch.setattr(projects, "PROJECT_CONTEXT_PATH", tmp_path / "project-context.json")
    (tmp_path / "projects.json").write_text(json.dumps([
        {"id": "sp1", "name": "Pump station hydraulics", "description": "Duty point checks", "kind": "other", "status": "active",
         "tags": [], "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z"},
    ]))
    monkeypatch.setattr(sirishydro, "HISTORY_PATH", tmp_path / "hydro.json")
    (tmp_path / "hydro.json").write_text(json.dumps([
        {"id": "h1", "question": "minimum submergence for a pump intake", "sufficient_evidence": True, "citations": [], "created_at": "2026-10-02T00:00:00Z"},
    ]))
    return tmp_path


@pytest.fixture
def apps(monkeypatch, data):
    fake = SearchApps()
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(fake))
    reset_hub(ENV)
    yield fake
    reset_hub({})


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _groups(body: dict) -> dict:
    return {g["id"]: g for g in body["groups"]}


def test_scoring_prefers_title_matches() -> None:
    assert service.score("pump", "Pump") > service.score("pump", "Pump curves") > service.score("pump", "Big pump") \
        > service.score("pump", "Sumps", "about a pump")
    assert service.matches("pump station", "Station 4", "a pump") and not service.matches("pump x", "pump")
    assert service.snippet("x " * 80 + "the pump is here " + "y " * 80, "pump").startswith("…")


def test_search_requires_login_and_two_characters(client, apps) -> None:
    assert client.get("/api/v1/search?q=pump").status_code == 401
    body = client.get("/api/v1/search?q=p", headers=AUTH).json()
    assert body["groups"] == [] and apps.calls == []


def test_search_reaches_every_source(client, apps) -> None:
    body = client.get("/api/v1/search?q=pump", headers=AUTH).json()
    groups = _groups(body)
    assert body["failed"] == []

    brain = groups["brain"]["hits"][0]
    assert brain["title"] == "Pump curves" and brain["url"] == "/brain?q=Pump%20curves" and not brain["external"]

    chats = groups["chats"]["hits"]
    assert [c["url"] for c in chats] == ["/assistant?c=c1", "/assistant?c=c2"]  # one per conversation
    assert chats[0]["subtitle"] == "You said · 2026-10-06"

    apd = groups["apd-pm"]
    assert apd["label"] == "Project Management"
    assert apd["hits"][0]["url"] == "http://apd:8080/projects/p1" and apd["hits"][0]["external"]
    rfi = next(h for h in apd["hits"] if h["kind"] == "rfi")
    assert rfi["url"] == "http://apd:8080/projects/p1?tab=quality" and rfi["subtitle"] == "RFI · Pump station upgrade · Open"

    archive = {h["kind"]: h for h in groups["archive"]["hits"]}
    assert archive["asset"]["url"] == "http://archive:8091/assets/as1"
    assert archive["media"]["subtitle"] == "Photo · Pump Station 4 · 2026-09-30"
    assert archive["file"]["url"] == "http://archive:8091/files"

    reviews = groups["reviewer"]["hits"]
    assert [r["title"] for r in reviews] == ["Pump station"] and reviews[0]["url"] == "http://reviewer:8082/#/review/r1"

    links = groups["links"]["hits"]
    assert [link["title"] for link in links] == ["Pump selector"] and links[0]["external"]

    eng = {h["kind"]: h for h in groups["engineering"]["hits"]}
    assert eng["project"]["url"] == "/engineering/projects/sp1"
    assert eng["hydro"]["url"].startswith("/engineering/hydro?q=minimum%20submergence")

    # Widgets on the home screen: APD PM's due tasks, the Reviewer's recent reviews.
    widgets = [h["title"] for h in groups["widgets"]["hits"]]
    assert "Pump station" in widgets

    # Most relevant group first.
    assert body["groups"][0]["best"] == max(g["best"] for g in body["groups"])


def test_apps_match_by_name_and_open_their_sheet(client, apps) -> None:
    hits = _groups(client.get("/api/v1/search?q=archive", headers=AUTH).json())["apps"]["hits"]
    assert hits[0]["app_id"] == "archive" and hits[0]["kind"] == "app" and hits[0]["score"] == 2.5


def test_a_slow_app_is_listed_and_the_rest_still_answer(client, apps) -> None:
    apps.slow = {"archive"}
    body = client.get("/api/v1/search?q=pump", headers=AUTH).json()
    assert "Engineering Archive" in body["failed"]
    assert "archive" not in _groups(body) and "brain" in _groups(body)


def test_without_sirisai_brain_and_chats_are_skipped(client, monkeypatch, data) -> None:
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(SearchApps()))
    reset_hub({k: v for k, v in ENV.items() if not k.startswith("SIRISAI")})
    body = client.get("/api/v1/search?q=pump", headers=AUTH).json()
    assert "brain" not in _groups(body) and "chats" not in _groups(body) and body["failed"] == []
    reset_hub({})
