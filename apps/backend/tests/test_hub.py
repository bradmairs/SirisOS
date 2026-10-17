"""Hub connectors and API (ADR 106), against mocked app HTTP."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service
from app.hub.service import reset_hub

ENV = {
    "SIRISAI_URL": "http://sirisai:8000",
    "SIRISAI_API_KEY": "ai-key",
    "SIRISAI_PUBLIC_URL": "https://siris.local",
    "REVIEWER_URL": "http://reviewer:8082",
    "ARCHIVE_URL": "http://archive:8091",
    "ARCHIVE_API_KEY": "ea_key",
    "SIRISDRONE_URL": "http://drone:8096",
    "SIRISLEARN_URL": "http://learn:8100",
    "SIRISLEARN_PUBLIC_URL": "https://learn.local",
    "SIRISLEARN_HUB_KEY": "learn-key",
}


def _token() -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "brad", "iat": now, "exp": now + timedelta(hours=1), "iss": "sirisos-api"},
        "change-this-development-secret",
        algorithm="HS256",
    )


AUTH = {"Authorization": f"Bearer {_token()}"}
TODAY = date.today()


class FakeApps:
    """One handler standing in for every app's HTTP API."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.down: set[str] = set()
        self.learn_at_risk = False
        self.captured: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        self.calls.append(f"{request.method} {host}{path}")
        if host in self.down:
            raise httpx.ConnectError("refused", request=request)
        if host == "sirisai":
            if request.headers.get("authorization") != "Bearer ai-key":
                return httpx.Response(401, json={"detail": "Missing or invalid API key."})
            return self.sirisai(request, path)
        if host == "reviewer":
            if path == "/api/health":
                return httpx.Response(200, json={"ok": True, "llm_provider": "ollama", "llm_model": "qwen3", "llm_available": True})
            if path == "/api/reviews":
                return httpx.Response(200, json=[
                    {"id": "r1", "name": "Pump station", "status": "done", "counts": {"critical": 1, "minor": 3}},
                    {"id": "r2", "name": "Outfall", "status": "running", "counts": {}},
                ])
        if host == "archive":
            if request.headers.get("x-api-key") != "ea_key":
                return httpx.Response(401, json={"error": "Missing X-API-Key header"})
            return httpx.Response(200, json={
                "status": "ok", "totalMedia": 12034, "unassignedMedia": 7, "needsReview": 3,
                "totalFiles": 900, "totalAssets": 41,
                "lastScan": {"target": "media", "status": "completed", "startedAt": "2026-10-01T02:00:00Z", "finishedAt": "2026-10-01T02:05:00Z"},
            })
        if host == "drone":
            if path == "/api/config":
                return httpx.Response(200, json={"output_roots": [{"name": "NAS", "path": "/nas/exports", "available": True}]})
            if path == "/api/media":
                return httpx.Response(200, json=[{"id": "a", "kind": "photo"}, {"id": "b", "kind": "photo"}, {"id": "c", "kind": "video"}])
            if path == "/api/jobs":
                return httpx.Response(200, json=[
                    {"id": "j1", "name": "DJI_0435.MP4", "status": "running", "progress": 0.42},
                    {"id": "j2", "name": "DJI_0568.jpg", "status": "done", "progress": 1.0},
                ])
        if host == "learn":
            return self.sirislearn(request, path)
        return httpx.Response(404, json={"detail": "not found"})

    def sirislearn(self, request: httpx.Request, path: str) -> httpx.Response:
        if request.headers.get("x-api-key") != "learn-key":
            return httpx.Response(401, json={"detail": "Missing or invalid X-API-Key."})
        if path == "/api/hub/v1/status":
            return httpx.Response(200, json={"status": "ok", "version": "1.0", "llm": {"provider": "anthropic", "configured": True}})
        if path == "/api/hub/v1/summary":
            return httpx.Response(200, json={
                "streak": {"current": 12, "best": 20, "today_done": not self.learn_at_risk, "at_risk": self.learn_at_risk},
                "xp": {"total": 4200, "today": 0 if self.learn_at_risk else 60, "goal": 50, "goal_met": not self.learn_at_risk, "week": 300},
                "level": {"level": 9, "xp_into": 600, "xp_for_next": 900, "progress": 0.66},
                "courses": {"total": 3, "active": 2, "completed": 1, "planning": 0},
                "continue": {"course_title": "Heat pumps", "lesson_title": "Refrigerants", "url": "/lesson/l2",
                             "progress": {"lessons": 8, "passed": 3, "percent": 37}},
                "recent": [{"kind": "achievement", "title": "Week warrior", "url": "/awards"},
                           {"kind": "quiz_finished", "title": "Moving heat", "url": "/lesson/l1"}],
            })
        if path == "/api/hub/v1/search":
            q = request.url.params.get("q", "")
            hits = [{"title": "Heat pumps", "subtitle": "Course · 3/8 lessons", "url": "/course/c1", "kind": "course"},
                    {"title": "Refrigerants", "subtitle": "Lesson · Heat pumps", "url": "/lesson/l2", "kind": "lesson"}]
            return httpx.Response(200, json={"hits": [h for h in hits if q.lower() in (h["title"] + h["subtitle"]).lower()]})
        return httpx.Response(404, json={"detail": "not found"})

    def sirisai(self, request: httpx.Request, path: str) -> httpx.Response:
        if path == "/siris/status":
            return httpx.Response(200, json={"llm_provider": "ollama", "stt_provider": "openai_compatible", "tts_provider": "none"})
        if path == "/siris/voice/converse":
            body = request.content.decode(errors="replace")
            heard = "a recording" if 'name="file"' in body else "typed"
            events = [
                {"type": "transcript", "text": heard},
                {"type": "sentence", "text": "Hello.", "audio": None},
                {"type": "final", "conversation_id": "v1", "response": "Hello.", "expects_reply": False},
            ]
            return httpx.Response(200, content="".join(json.dumps(e) + "\n" for e in events).encode(), headers={"content-type": "application/x-ndjson"})
        if path == "/siris/hud/summary":
            return httpx.Response(200, json={
                "weather": {"temperature_c": 17.6, "conditions": "Partly cloudy"},
                "next_events": [{"summary": "Site meeting", "start": "2026-10-03T09:30:00+10:00"}],
                "parcels": [{"id": 1}],
                "brain": [{"title": "Pump curves", "action": "learned"}],
            })
        if path == "/siris/brain/map.html":
            return httpx.Response(200, text="<title>Siris Brain Map</title><canvas id=stage></canvas>")
        if path == "/siris/brain/unlink":
            body = json.loads(request.content)
            return httpx.Response(200, json={"action": "unlinked", **body})
        if path == "/siris/brain/autolink":
            return httpx.Response(200, json={"linked": [{"a": "A", "b": "B", "confidence": 88}], "deferred": 0})
        if path == "/siris/brain/note":
            title = request.url.params["title"]
            if title != "SirisOS":
                return httpx.Response(404, json={"detail": f"No note called {title!r}."})
            return httpx.Response(200, json={"title": "SirisOS", "path": "x", "links": ["SirisAI"], "backlinks": []})
        if path in ("/siris/brain/delete", "/siris/brain/restore", "/siris/brain/purge"):
            body = json.loads(request.content)
            if body["title"] == "Health":
                return httpx.Response(422, json={"detail": "Health is one of the hubs the brain is organised around, so it can't be deleted"})
            action = {"delete": "deleted", "restore": "restored", "purge": "purged"}[path.rsplit("/", 1)[1]]
            return httpx.Response(200, json={"action": action, **body})
        if path == "/siris/brain/deleted":
            return httpx.Response(200, json=[{"title": "Old Router", "type": "note", "path": "Notes/Old Router.md",
                                              "date": "2026-10-16", "linked_from": ["Home Lab"], "restorable": True}])
        if path == "/siris/memory" and request.method == "GET":
            return httpx.Response(200, json=[{"id": 7, "position": 1, "content": "Brad prefers metric units",
                                              "created_at": "2026-10-01", "recall_count": 2, "last_recalled_at": None,
                                              "query": request.url.params.get("query"), "limit": request.url.params.get("limit")}])
        if path.startswith("/siris/memory/") and request.method == "DELETE":
            return httpx.Response(204) if path.endswith("/7") else httpx.Response(404, json={"detail": "Memory not found."})
        if path in ("/siris/brain/link", "/siris/brain/not-related"):
            body = json.loads(request.content)
            if body["b"] == "Nope":
                return httpx.Response(422, json={"detail": "No note called 'Nope'"})
            return httpx.Response(200, json={"action": "linked" if path.endswith("link") else "dismissed", **body})
        if path == "/siris/brain/today":
            return httpx.Response(200, json={"date": "2026-10-02", "items": [{"title": "Pump curves", "action": "learned"}]})
        if path == "/siris/brain/insights":
            days = int(request.url.params["days"])
            return httpx.Response(200, json={"date": "2026-10-03", "highlights": ["3 notes learned or updated this week."],
                                             "activity": [{"date": "2026-10-03", "notes": 1}] * days})
        if path == "/siris/brain/search":
            return httpx.Response(200, json=[{"title": "Pump curves", "path": "Notes/Pump curves.md", "q": request.url.params["q"]}])
        if path == "/siris/brain/capture":
            body = json.loads(request.content)
            self.captured.append(body)
            return httpx.Response(200, json={"saved": True, "title": body["text"][:10], "action": "created"})
        if path == "/siris/voice/transcribe":
            assert b'filename="memo.wav"' in request.content
            return httpx.Response(200, json={"text": "Check the pit lids on Monday"})
        if path == "/siris/conversations":
            return httpx.Response(200, json=[{"id": "c1", "limit": request.url.params["limit"]}])
        if path == "/siris/chat/stream":
            body = json.loads(request.content)
            events = [
                {"type": "status", "message": "Thinking"},
                {"type": "content", "delta": f"Echo: {body['prompt']}"},
                {"type": "final", "response": {"response": f"Echo: {body['prompt']}", "conversation_id": "c9"}},
            ]
            payload = "".join(f"data: {json.dumps(e)}\n\n" for e in events)
            return httpx.Response(200, content=payload.encode(), headers={"content-type": "text/event-stream"})
        return httpx.Response(404, json={"detail": "Not Found"})


@pytest.fixture
def apps(monkeypatch):
    fake = FakeApps()
    monkeypatch.setattr(service, "transport", httpx.MockTransport(fake))
    reset_hub(ENV)
    yield fake
    reset_hub({})


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _by_id(payload: dict) -> dict:
    return {a["id"]: a for a in payload["apps"]}


def test_hub_requires_login(client, apps):
    assert client.get("/api/v1/hub/apps").status_code == 401
    assert client.get("/api/v1/brain/today").status_code == 401
    assert client.get("/api/v1/brain/insights").status_code == 401


def test_all_configured_apps_report_ok(client, apps):
    apps_ = _by_id(client.get("/api/v1/hub/apps", headers=AUTH).json())
    assert list(apps_)[:2] == ["sirisai", "second-brain"]
    assert "apd-pm" not in apps_  # SirisPM was removed from SirisOS (1.3)
    for app_id in ("sirisai", "second-brain", "reviewer", "archive", "sirisdrone", "sirislearn"):
        assert apps_[app_id]["status"]["state"] == "ok", (app_id, apps_[app_id]["status"])
    assert apps_["sirislearn"]["status"]["version"] == "1.0"
    assert apps_["second-brain"]["launch_url"] == "https://siris.local/brain"
    # GVW Timesheets, Helmarr, Neo Server and JEFIT were removed from SirisOS (1.31).
    assert not {"gvw", "helmarr", "neo-server", "jefit"} & set(apps_)


def test_unconfigured_apps_never_call_out(client, monkeypatch):
    fake = FakeApps()
    monkeypatch.setattr(service, "transport", httpx.MockTransport(fake))
    reset_hub({"ARCHIVE_URL": "http://archive:8091"})  # no API key
    apps_ = _by_id(client.get("/api/v1/hub/apps?widgets=true", headers=AUTH).json())
    assert {a["status"]["state"] for a in apps_.values()} == {"unconfigured"}
    assert "ARCHIVE_API_KEY" in apps_["archive"]["status"]["detail"]
    assert fake.calls == []
    reset_hub({})


def test_one_dead_app_only_blanks_its_own_tile(client, apps):
    apps.down.add("archive")
    apps_ = _by_id(client.get("/api/v1/hub/apps?widgets=true", headers=AUTH).json())
    assert apps_["archive"]["status"]["state"] == "down"
    assert apps_["archive"]["widget"] is None
    assert apps_["reviewer"]["status"]["state"] == "ok"
    assert apps_["sirisai"]["widget"]["title"] == "Today"


def test_bad_credentials_are_degraded_not_down(client, monkeypatch):
    monkeypatch.setattr(service, "transport", httpx.MockTransport(FakeApps()))
    reset_hub({**ENV, "SIRISAI_API_KEY": "wrong"})
    apps_ = _by_id(client.get("/api/v1/hub/apps", headers=AUTH).json())
    assert apps_["sirisai"]["status"]["state"] == "degraded"
    assert "Unauthorised" in apps_["sirisai"]["status"]["detail"]
    reset_hub({})


def test_widgets_are_normalised(client, apps):
    widgets = {w["app_id"]: w for w in client.get("/api/v1/hub/widgets", headers=AUTH).json()["widgets"]}

    today = widgets["sirisai"]
    assert {"label": "Weather", "value": "18° Partly cloudy", "tone": "neutral"} in today["metrics"]
    assert today["items"][0]["title"] == "Site meeting"

    archive = {m["label"]: m["value"] for m in widgets["archive"]["metrics"]}
    assert archive == {"Needs review": "3", "Unassigned": "7", "Media": "12,034", "Assets": "41"}

    reviews = widgets["reviewer"]
    assert reviews["items"][0]["tone"] == "critical"
    assert reviews["items"][0]["url"] == "http://reviewer:8082/#/review/r1"
    assert {"label": "In progress", "value": "1", "tone": "neutral"} in reviews["metrics"]

    assert widgets["second-brain"]["items"][0]["title"] == "Pump curves"

    drone = {m["label"]: m for m in widgets["sirisdrone"]["metrics"]}
    assert (drone["Photos"]["value"], drone["Videos"]["value"]) == ("2", "1")
    assert drone["Exporting"] == {"label": "Exporting", "value": "1", "tone": "warning"}
    assert drone["NAS"]["tone"] == "good"
    assert widgets["sirisdrone"]["items"][0] == {"title": "Exporting DJI_0435.MP4", "subtitle": "running · 42%", "url": None, "tone": "neutral"}


def test_sirislearn_widget(client, apps):
    widgets = {w["app_id"]: w for w in client.get("/api/v1/hub/widgets", headers=AUTH).json()["widgets"]}
    learn = widgets["sirislearn"]
    metrics = {m["label"]: m for m in learn["metrics"]}
    assert metrics["Streak"] == {"label": "Streak", "value": "12 days", "tone": "good"}
    assert metrics["Today"]["value"] == "60/50 XP" and metrics["Today"]["tone"] == "good"
    assert (metrics["Level"]["value"], metrics["Courses"]["value"]) == ("9", "2")
    assert learn["items"][0] == {"title": "Next: Refrigerants", "subtitle": "Heat pumps · 3/8 lessons", "url": "https://learn.local/lesson/l2", "tone": "neutral"}
    assert learn["items"][1]["title"] == "Unlocked Week warrior" and learn["items"][1]["url"] == "https://learn.local/awards"


def test_sirislearn_streak_at_risk_goes_to_the_inbox(client, apps, tmp_path, monkeypatch):
    from app.attention import service as attention

    monkeypatch.setenv("SIRISOS_ATTENTION_STATE_PATH", str(tmp_path / "attention.json"))
    apps_ = list(_by_id(client.get("/api/v1/hub/apps?widgets=true", headers=AUTH).json()).values())
    assert not [i for i in attention.own_items(apps_) if i["source"] == "sirislearn"]

    apps.learn_at_risk = True
    apps_ = list(_by_id(client.get("/api/v1/hub/apps?widgets=true&fresh=true", headers=AUTH).json()).values())
    learn = next(a for a in apps_ if a["id"] == "sirislearn")
    assert learn["widget"]["items"][0]["title"] == "Your 12-day streak ends at midnight"
    assert {m["label"]: m["tone"] for m in learn["widget"]["metrics"]}["Streak"] == "warning"
    [item] = [i for i in attention.own_items(apps_) if i["source"] == "sirislearn"]
    assert item["title"] == "Your 12-day learning streak ends at midnight"
    assert item["url"] == "https://learn.local/lesson/l2" and item["key"].startswith("sirislearn:streak:")


def test_sirislearn_needs_its_hub_key(client, monkeypatch):
    monkeypatch.setattr(service, "transport", httpx.MockTransport(FakeApps()))
    reset_hub({"SIRISLEARN_URL": "http://learn:8100"})
    status = _by_id(client.get("/api/v1/hub/apps", headers=AUTH).json())["sirislearn"]["status"]
    assert status["state"] == "unconfigured" and "SIRISLEARN_HUB_KEY" in status["detail"]
    reset_hub({"SIRISLEARN_URL": "http://learn:8100", "SIRISLEARN_HUB_KEY": "wrong"})
    status = _by_id(client.get("/api/v1/hub/apps", headers=AUTH).json())["sirislearn"]["status"]
    assert status["state"] == "degraded"
    reset_hub({})


def test_sirisdrone_sends_basic_auth_when_set(client, monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"output_roots": []})

    monkeypatch.setattr(service, "transport", httpx.MockTransport(handler))
    reset_hub({"SIRISDRONE_URL": "http://drone:8096", "SIRISDRONE_USERNAME": "brad", "SIRISDRONE_PASSWORD": "pw"})
    apps_ = _by_id(client.get("/api/v1/hub/apps", headers=AUTH).json())
    assert apps_["sirisdrone"]["status"]["state"] == "ok"
    assert seen and all(h == httpx.BasicAuth("brad", "pw")._auth_header for h in seen)
    reset_hub({})


def test_status_is_cached_until_fresh_requested(client, apps):
    client.get("/api/v1/hub/apps", headers=AUTH)
    first = len(apps.calls)
    client.get("/api/v1/hub/apps", headers=AUTH)
    assert len(apps.calls) == first
    client.get("/api/v1/hub/apps?fresh=true", headers=AUTH)
    assert len(apps.calls) > first


def test_unknown_app_is_404(client, apps):
    assert client.get("/api/v1/hub/apps/nope", headers=AUTH).status_code == 404


def test_reviewer_without_llm_is_degraded(client, monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"ok": True, "llm_provider": "none", "llm_available": False})

    monkeypatch.setattr(service, "transport", httpx.MockTransport(handler))
    reset_hub({"REVIEWER_URL": "http://reviewer:8082", "REVIEWER_USERNAME": "u", "REVIEWER_PASSWORD": "p"})
    body = client.get("/api/v1/hub/apps/reviewer", headers=AUTH).json()
    assert body["status"]["state"] == "degraded"
    assert "Deterministic checks only" in body["status"]["detail"]
    reset_hub({})


def test_brain_proxies(client, apps):
    assert client.get("/api/v1/brain/search?q=pumps", headers=AUTH).json()[0]["q"] == "pumps"
    assert client.get("/api/v1/brain/today", headers=AUTH).json()["items"][0]["title"] == "Pump curves"
    insights = client.get("/api/v1/brain/insights?days=14", headers=AUTH).json()
    assert insights["highlights"] == ["3 notes learned or updated this week."] and len(insights["activity"]) == 14
    assert len(client.get("/api/v1/brain/insights", headers=AUTH).json()["activity"]) == 30
    assert client.get("/api/v1/brain/insights?days=2", headers=AUTH).status_code == 422
    saved = client.post("/api/v1/brain/capture", headers=AUTH, json={"text": "Remember the pump curves"})
    assert saved.json()["saved"] is True
    assert client.post("/api/v1/brain/capture", headers=AUTH, json={"text": " "}).status_code == 422
    # No photo: the field isn't sent at all (older SirisAI versions don't know it).
    assert "image" not in apps.captured[-1]
    photo = "data:image/jpeg;base64,/9j/4A=="
    assert client.post("/api/v1/brain/capture", headers=AUTH, json={"image": photo}).json()["saved"] is True
    assert apps.captured[-1]["image"] == photo
    memo = client.post("/api/v1/assistant/voice/transcribe", headers=AUTH, files={"file": ("memo.wav", b"RIFF....", "audio/wav")})
    assert memo.json() == {"text": "Check the pit lids on Monday"}
    mind_map = client.get("/api/v1/brain/map.html", headers=AUTH)
    assert mind_map.headers["content-type"].startswith("text/html")
    assert "Siris Brain Map" in mind_map.text


def test_assistant_proxies(client, apps):
    assert client.get("/api/v1/assistant/conversations?limit=5", headers=AUTH).json() == [{"id": "c1", "limit": "5"}]
    assert client.get("/api/v1/assistant/hud", headers=AUTH).json()["weather"]["temperature_c"] == 17.6


def test_chat_stream_relays_sirisai_events(client, apps):
    with client.stream("POST", "/api/v1/assistant/chat/stream", headers=AUTH, json={"prompt": "hello"}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert [e["type"] for e in events] == ["status", "content", "final"]
    assert events[-1]["response"]["conversation_id"] == "c9"


def test_voice_status_and_converse_relay(client, apps):
    assert client.get("/api/v1/assistant/voice", headers=AUTH).json() == {"stt": True, "tts": False}

    def events(response):
        return [json.loads(line) for line in response.text.splitlines() if line.strip()]

    spoken = client.post(
        "/api/v1/assistant/voice/converse",
        headers=AUTH,
        files={"file": ("turn.wav", b"RIFF....WAVE", "audio/wav")},
        data={"conversation_id": "v0"},
    )
    assert spoken.status_code == 200
    assert spoken.headers["content-type"].startswith("application/x-ndjson")
    assert [e["type"] for e in events(spoken)] == ["transcript", "sentence", "final"]
    assert events(spoken)[0]["text"] == "a recording"

    typed = client.post("/api/v1/assistant/voice/converse", headers=AUTH, data={"text": "hi", "synthesize": "false"})
    assert events(typed)[0]["text"] == "typed"
    assert client.post("/api/v1/assistant/voice/converse", headers=AUTH, data={"text": " "}).status_code == 422


def test_assistant_unconfigured_is_503(client):
    reset_hub({})
    response = client.get("/api/v1/brain/today", headers=AUTH)
    assert response.status_code == 503
    assert "SIRISAI_URL" in response.json()["detail"]


def test_sirisai_auth_failure_surfaces_as_bad_gateway(client, monkeypatch):
    monkeypatch.setattr(service, "transport", httpx.MockTransport(FakeApps()))
    reset_hub({**ENV, "SIRISAI_API_KEY": "wrong"})
    response = client.get("/api/v1/brain/today", headers=AUTH)
    assert response.status_code == 502
    reset_hub({})


def test_check_cli_reports_each_app_and_fails_on_problems(apps):
    from app.hub import check

    lines, healthy = asyncio.run(check.run(ENV))
    text = "\n".join(lines)
    assert "✓ SirisAI" in text and "widget ok" in text
    assert healthy is True

    apps.down.add("drone")
    lines, healthy = asyncio.run(check.run(ENV))
    assert healthy is False
    assert any(line.startswith("✗ SirisDrone") for line in lines)


def test_bare_public_domains_become_https_links(client):
    from app.hub.connectors.base import with_scheme

    assert with_scheme("pm.example.org") == "https://pm.example.org"
    assert with_scheme("https://pm.example.org/") == "https://pm.example.org"
    assert with_scheme("http://10.0.0.5:8080") == "http://10.0.0.5:8080"
    assert with_scheme("shortcuts://") == "shortcuts://"
    assert with_scheme("") == ""

    reset_hub({**ENV, "ARCHIVE_PUBLIC_URL": "archive.example.org", "SIRISAI_PUBLIC_URL": "siris.example.org"})
    apps = {a["id"]: a for a in client.get("/api/v1/hub/apps", headers=AUTH).json()["apps"]}
    assert apps["archive"]["launch_url"] == "https://archive.example.org"
    assert apps["second-brain"]["launch_url"] == "https://siris.example.org/brain"
    reset_hub({})


def test_brain_link_and_not_related_proxies(client, apps):
    linked = client.post("/api/v1/brain/link", headers=AUTH, json={"a": "Pump curves", "b": "Pumps"})
    assert linked.json() == {"action": "linked", "a": "Pump curves", "b": "Pumps"}
    dismissed = client.post("/api/v1/brain/not-related", headers=AUTH, json={"a": "Finances", "b": "Health"})
    assert dismissed.json()["action"] == "dismissed"
    missing = client.post("/api/v1/brain/link", headers=AUTH, json={"a": "Pumps", "b": "Nope"})
    assert missing.status_code == 422 and "No note called 'Nope'" in missing.json()["detail"]
    assert client.post("/api/v1/brain/link", headers=AUTH, json={"a": "", "b": "x"}).status_code == 422
    assert client.post("/api/v1/brain/link", json={"a": "a", "b": "b"}).status_code == 401


def test_cmp_capabilities_is_not_part_of_the_hub(client, monkeypatch):
    # Work-only app, removed from SirisOS on request: even leftover CMP_* settings
    # in .env must not bring the tile back.
    monkeypatch.setattr(service, "transport", httpx.MockTransport(FakeApps()))
    reset_hub({**ENV, "CMP_URL": "http://cmp:8093", "CMP_EMAIL": "b@example.com", "CMP_PASSWORD": "pw"})
    ids = {a["id"] for a in client.get("/api/v1/hub/apps", headers=AUTH).json()["apps"]}
    assert "cmp" not in ids
    reset_hub({})


def test_brain_unlink_autolink_and_note_proxies(client, apps):
    r = client.post("/api/v1/brain/unlink", headers=AUTH, json={"a": "SirisOS", "b": "Apple Health"})
    assert r.json() == {"action": "unlinked", "a": "SirisOS", "b": "Apple Health"}
    assert client.post("/api/v1/brain/unlink", headers=AUTH, json={"a": "", "b": "x"}).status_code == 422
    assert client.post("/api/v1/brain/autolink", headers=AUTH).json()["linked"][0]["confidence"] == 88
    assert client.get("/api/v1/brain/note?title=SirisOS", headers=AUTH).json()["links"] == ["SirisAI"]
    assert client.get("/api/v1/brain/note?title=Nope", headers=AUTH).status_code == 404
    assert client.post("/api/v1/brain/autolink").status_code == 401


def test_brain_delete_restore_purge_and_deleted_proxies(client, apps):
    deleted = client.post("/api/v1/brain/delete", headers=AUTH, json={"title": "Old Router"})
    assert deleted.json() == {"action": "deleted", "title": "Old Router", "permanent": False}
    forever = client.post("/api/v1/brain/delete", headers=AUTH, json={"title": "Spare Pi", "permanent": True})
    assert forever.json()["permanent"] is True
    assert client.post("/api/v1/brain/restore", headers=AUTH, json={"title": "Old Router"}).json()["action"] == "restored"
    assert client.post("/api/v1/brain/purge", headers=AUTH, json={"title": "Old Router"}).json()["action"] == "purged"
    assert client.get("/api/v1/brain/deleted", headers=AUTH).json()[0]["title"] == "Old Router"
    hub = client.post("/api/v1/brain/delete", headers=AUTH, json={"title": "Health"})
    assert hub.status_code == 422 and "hubs" in hub.json()["detail"]
    assert client.post("/api/v1/brain/delete", headers=AUTH, json={"title": ""}).status_code == 422
    assert client.post("/api/v1/brain/delete", json={"title": "x"}).status_code == 401


def test_memories_list_and_delete_proxies(client, apps):
    listed = client.get("/api/v1/memories?query=units&limit=5", headers=AUTH).json()
    assert listed[0]["content"] == "Brad prefers metric units"
    assert listed[0]["query"] == "units" and listed[0]["limit"] == "5"
    assert client.get("/api/v1/memories", headers=AUTH).json()[0]["query"] is None  # no empty query sent
    assert client.delete("/api/v1/memories/7", headers=AUTH).status_code == 204
    missing = client.delete("/api/v1/memories/8", headers=AUTH)
    assert missing.status_code == 404 and "Memory not found" in missing.json()["detail"]
    assert client.delete("/api/v1/memories/7").status_code == 401
