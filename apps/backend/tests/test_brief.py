"""Daily brief (ADR 108): news from the Second Brain's interests, the composed
brief, the auto-show window and dismissal, against mocked app HTTP."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app.brief import news, service
from app.brief.news import Story, Topic
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from tests.test_hub import AUTH

MEL = ZoneInfo("Australia/Melbourne")
NOW = datetime.now(timezone.utc)

PREFS = """---
type: resource
---
# Daily Briefing Preferences

## Topics, in order
1. AI and emerging technology
2. [[Self-hosting]] and home lab
3. Melbourne events worth knowing about

## Format
Short.
"""

OWNER = "Brad lives near [[Melbourne]]. Interests: [[Home Assistant]], [[Ollama]], [[Goulburn Valley Water]], [[Home]]."


def rss(*items: tuple[str, str, str | None]) -> str:
    """RSS 2.0 like Google News: (title, source, hours ago)."""
    body = []
    for i, (title, source, hours) in enumerate(items):
        when = (NOW - timedelta(hours=float(hours))).strftime("%a, %d %b %Y %H:%M:%S GMT") if hours else ""
        src = f'<source url="https://{source.lower()}.example">{source}</source>' if source else ""
        body.append(f"<item><title>{title}{' - ' + source if source else ''}</title>"
                    f"<link>https://news.example/{i}-{abs(hash(title))}</link><pubDate>{when}</pubDate>{src}</item>")
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{"".join(body)}</channel></rss>'


# -- news ---------------------------------------------------------------------


def test_topics_come_from_the_preferences_note_in_order() -> None:
    topics = news.topics_from_note(PREFS)
    assert [t.name for t in topics] == ["AI and emerging technology", "Self-hosting and home lab", "Melbourne events worth knowing about"]
    assert topics[0].weight > topics[1].weight > topics[2].weight
    assert "Anthropic" in topics[0].query and "homelab" in topics[1].query and "Melbourne events" in topics[2].query


def test_topics_fall_back_to_defaults_without_a_note() -> None:
    assert [t.name for t in news.topics_from_note(None)] == news.DEFAULT_TOPICS
    assert [t.name for t in news.topics_from_note("# Notes\nNo topics here.")] == news.DEFAULT_TOPICS
    # A topic with no hint is searched as written.
    assert news.topics_from_note("## Topics\n- Murray cod fishing\n")[0].query == "Murray cod fishing"


def test_vocabulary_is_linked_interests_and_hot_tags_minus_generic_areas() -> None:
    vocab = news.vocabulary(PREFS, OWNER, extra=["home-assistant", "ai"])
    assert {"home assistant", "ollama", "goulburn valley water", "melbourne", "self-hosting"} <= vocab
    assert "home" not in vocab and "ai" not in vocab  # too generic / too short


def test_parse_feed_cleans_titles_and_dates_and_skips_junk() -> None:
    xml = rss(("Ollama ships a new model", "The Verge", "2"), ("Plain headline - ABC News", "", "1")).replace(
        "</channel>", "<item><title>No link</title></item><item><title>x</title><link>javascript:alert(1)</link></item></channel>")
    stories = news.parse_feed(xml, "AI")
    assert [(s.title, s.source) for s in stories] == [("Ollama ships a new model", "The Verge"), ("Plain headline", "ABC News")]
    assert stories[0].published and stories[0].published.endswith("+00:00")
    assert news.parse_feed("<rss><channel><item>", "AI") == []


def test_rank_prefers_brads_interests_then_priority_then_freshness() -> None:
    topics = [Topic("AI", "q", 1.0), Topic("Home lab", "q", 0.92)]
    stories = [
        Story("Generic AI story", "u1", "s", (NOW - timedelta(hours=1)).isoformat(), "AI"),
        Story("Home Assistant adds local voice with Ollama", "u2", "s", (NOW - timedelta(hours=20)).isoformat(), "Home lab"),
        Story("Older generic AI story", "u3", "s", (NOW - timedelta(hours=23)).isoformat(), "AI"),
    ]
    ranked = news.rank(stories, topics, {"home assistant", "ollama"}, now=NOW)
    assert [s.url for s in ranked] == ["u2", "u1", "u3"]
    assert ranked[0].matches == ["home assistant", "ollama"]


def test_pick_groups_in_topic_order_without_repeats() -> None:
    topics = [Topic("AI", "q", 1.0), Topic("Home lab", "q", 0.9)]
    stories = [Story(f"AI {i}", f"a{i}", "s", None, "AI") for i in range(5)]
    stories += [Story("AI 0", "dup", "s", None, "Home lab"), Story("Docker 29", "d", "s", None, "Home lab"),
                Story("Big national story", "t", "ABC", None, "Top stories"), Story("AI 1", "t2", "ABC", None, "Top stories")]
    groups = news.pick(stories, topics, per_topic=3)
    assert [g["topic"] for g in groups] == ["AI", "Home lab", "Top stories"]
    assert [s["url"] for s in groups[0]["stories"]] == ["a0", "a1", "a2"]
    assert [s["url"] for s in groups[1]["stories"]] == ["d"]
    assert [s["url"] for s in groups[2]["stories"]] == ["t"]


@pytest.mark.anyio
async def test_news_service_fetches_ranks_caches_and_survives_outages() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if request.url.host == "www.abc.net.au":
            return httpx.Response(200, text=rss(("Big national story", "", "3")))
        q = request.url.params["q"]
        if "homelab" in q:
            return httpx.Response(500)
        if "Melbourne events" in q:
            return httpx.Response(200, content=b"x" * (news.MAX_FEED_BYTES + 10))
        return httpx.Response(200, text=rss(("Anthropic releases Claude update", "Reuters", "2"), ("Ollama gets faster", "Ars", "5")))

    notes = {news.PREFERENCES_NOTE: PREFS, news.OWNER_NOTE: OWNER}

    async def load(title: str) -> str | None:
        return notes.get(title)

    svc = news.NewsService()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await svc.stories(client, load, ["ollama"])
        assert result["feeds_total"] == 4 and result["feeds_failed"] == 2  # 500 and the oversized feed
        assert result["interests_from"] == news.PREFERENCES_NOTE
        ai = result["topics"][0]
        assert ai["topic"] == "AI and emerging technology"
        assert ai["stories"][0]["title"] == "Ollama gets faster" and ai["stories"][0]["matches"] == ["ollama"]
        assert result["topics"][-1]["topic"] == "Top stories"

        n = len(calls)
        await svc.stories(client, load, ["ollama"])
        assert len(calls) == n  # cached
        await svc.stories(client, load, ["ollama"], fresh=True)
        assert len(calls) == 2 * n

        # A total outage isn't cached, so the next look tries again.
        down = news.NewsService()
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as dead:
            out = await down.stories(dead, load, [])
            assert out["topics"] == [] and out["feeds_failed"] == out["feeds_total"]
            assert down._cache is None


# -- window and dismissal -------------------------------------------------------


@pytest.fixture
def state(tmp_path, monkeypatch):
    path = tmp_path / "brief-state.json"
    monkeypatch.setenv("SIRISOS_BRIEF_STATE_PATH", str(path))
    monkeypatch.delenv("SIRISOS_BRIEF_FROM_HOUR", raising=False)
    monkeypatch.delenv("SIRISOS_BRIEF_UNTIL_HOUR", raising=False)
    return path


def test_status_shows_only_in_the_morning_window(state) -> None:
    day = datetime(2026, 10, 8, tzinfo=MEL)
    assert service.status(day.replace(hour=3, minute=59))["show"] is False
    assert service.status(day.replace(hour=4))["show"] is True
    assert service.status(day.replace(hour=8, minute=59))["show"] is True
    assert service.status(day.replace(hour=9))["show"] is False
    assert service.status(day.replace(hour=7)) | {} == {
        "date": "2026-10-08", "show": True, "dismissed_today": False, "from": "04:00", "until": "09:00"}


def test_window_is_configurable_and_bad_values_fall_back(state, monkeypatch) -> None:
    monkeypatch.setenv("SIRISOS_BRIEF_FROM_HOUR", "6")
    monkeypatch.setenv("SIRISOS_BRIEF_UNTIL_HOUR", "eleven")
    assert service.window() == (6, 9)


def test_dismissal_lasts_for_the_day_only(state) -> None:
    service.dismiss("2026-10-08")
    assert json.loads(state.read_text()) == {"dismissed": "2026-10-08"}
    assert service.status(datetime(2026, 10, 8, 7, tzinfo=MEL))["show"] is False
    assert service.status(datetime(2026, 10, 8, 7, tzinfo=MEL))["dismissed_today"] is True
    assert service.status(datetime(2026, 10, 9, 7, tzinfo=MEL))["show"] is True
    state.write_text("not json")
    assert service.status(datetime(2026, 10, 8, 7, tzinfo=MEL))["show"] is True


# -- compose --------------------------------------------------------------------


def test_compose_writes_the_headline_from_every_source(state) -> None:
    at = datetime(2026, 10, 8, 6, 30, tzinfo=MEL)
    parts = {
        "hud": {"weather": {"temperature_c": 9.4, "conditions": "Clear"},
                "parcels": [{"label": "Bunnings order", "status_text": "out for delivery"}],
                "car": {"summary": "Car at 18%.", "low_battery": True}},
        "forecast": [{"high_c": 21.4, "low_c": 8, "conditions": "Showers", "rain_chance_percent": 70}],
        "calendar": [{"summary": "School pickup", "start": "2026-10-08", "calendar": "iCloud Family"},
                     {"summary": "Site meeting", "start": "2026-10-08T09:30:00+11:00", "location": "Shepparton", "calendar": "Gmail"},
                     {"summary": "The Bear S04E01", "start": "2026-10-08T20:00:00+11:00", "calendar": "Sonarr"}],
        "todo": [{"name": "Shopping", "items": [{"summary": "Milk"}, {"summary": ""}]}],
        "email": [{"from": "Jane Smith <jane@x.com>", "subject": "Pump quote", "important": True},
                  {"from": "news@x.com", "subject": "Newsletter", "important": False}],
        "health": {"metrics": {"sleep_hours": {"latest": 6.25}}, "notes": ["Resting heart rate is up."]},
        "insights": {"summary": {"inbox": 3}, "overdue_tasks": [{"task": "Send RFI", "note": "Pump station", "days_late": 2}],
                     "deadlines": [{"title": "Outfall", "days_left": 0}, {"title": "Later", "days_left": 30}],
                     "auto_linked": [{"a": "A", "b": "B"}], "pending_auto_links": 2, "suggested_links": [{}],
                     "highlights": ["3 notes this week."]},
        "apps": [{"id": "apd-pm", "name": "Project Management", "status": {"state": "ok"},
                  "widget": {"items": [{"title": "Submit RFI", "subtitle": "2 days overdue", "tone": "critical"},
                                       {"title": "Report", "subtitle": "in 10 days", "tone": "neutral"}]}},
                 {"id": "archive", "name": "Engineering Archive", "status": {"state": "down", "detail": "timeout"}}],
        "news": {"topics": [{"topic": "AI", "stories": []}]},
    }
    brief = service.compose(at, "brad", parts, ["email"])
    assert brief["greeting"] == "Good morning, Brad" and brief["weekday"] == "Thursday"
    assert brief["headline"] == [
        "21° today, showers, 70% chance of rain: take a jacket.",
        "2 things on today, starting with Site meeting at 9:30 am.",
        "3 tasks overdue or due today, starting with Send RFI.",
        "1 important email, from Jane Smith.",
        "Engineering Archive needs a look (down).",
        "3 things waiting in the Second Brain inbox.",
    ]
    assert [e["title"] for e in brief["schedule"]] == ["School pickup", "Site meeting"]  # no Sonarr
    assert [e["calendar"] for e in brief["schedule"]] == ["iCloud Family", "Gmail"]
    assert [t["source"] for t in brief["tasks"]] == ["Second Brain", "Second Brain", "Project Management"]
    assert brief["todo"] == ["Milk"]
    assert brief["email"] == {"unread": 2, "important": [{"from": "Jane Smith", "subject": "Pump quote"}]}
    assert brief["health"] == ["Slept 6.2 h", "Resting heart rate is up."]
    assert brief["home"] == ["Parcel: Bunnings order out for delivery", "Car at 18%. Low and not plugged in."]
    assert brief["brain"] == {"inbox": 3, "auto_linked": 1, "pending_links": 2, "unsure_links": 1, "highlights": ["3 notes this week."]}
    assert brief["unavailable"] == ["email"]


def test_compose_copes_with_nothing(state) -> None:
    brief = service.compose(datetime(2026, 10, 8, 4, 30, tzinfo=MEL), "brad", {}, ["SirisAI"])
    assert brief["greeting"] == "Good night, Brad"
    assert brief["headline"] == ["Nothing on the calendar today."]
    assert brief["email"] is None and brief["news"] == {"topics": []}


# -- API --------------------------------------------------------------------------


class FakeSirisAI:
    def __init__(self) -> None:
        self.tools: dict[str, int] = {}
        self.missing = {"calendar_upcoming_events"}
        self.broken: set[str] = set()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == "news.google.com":
            return httpx.Response(200, text=rss(("Home Assistant 2026.10 released", "HA blog", "4")))
        if host == "www.abc.net.au":
            return httpx.Response(200, text=rss(("National story", "", "1")))
        if host != "sirisai":
            return httpx.Response(404)
        assert request.headers["authorization"] == "Bearer ai-key"
        if path.startswith("/siris/tools/"):
            name = path.split("/")[3]
            self.tools[name] = self.tools.get(name, 0) + 1
            assert name != "daily_briefing"  # it clears SirisAI's notification queue
            if name in self.missing:
                return httpx.Response(404, json={"detail": f"Unknown tool: {name}"})
            if name in self.broken:
                return httpx.Response(502, json={"detail": "failed"})
            args = json.loads(request.content)["arguments"]
            result = {
                "weather_forecast": [{"high_c": 19, "conditions": "Sunny", "rain_chance_percent": 5}],
                "home_assistant_get_calendar_events": [{"summary": "Dentist", "start": {"dateTime": "2026-10-08T10:00:00+11:00"}}],
                "home_assistant_get_todo_items": [{"items": [{"summary": "Bins out"}]}],
                "email_list_unread": [{"from": "Bob <b@x>", "subject": "Hi", "important": True}],
                "health_summary": {"metrics": {}, "notes": []},
            }[name]
            if name == "email_list_unread":
                assert args == {"since_days": 1}
            return httpx.Response(200, json={"tool_call": {"name": name, "arguments": args, "result": result}})
        if path == "/siris/hud/summary":
            return httpx.Response(200, json={"weather": {"temperature_c": 12, "conditions": "Clear"}})
        if path == "/siris/brain/insights":
            return httpx.Response(200, json={"summary": {"inbox": 1}, "topics": [{"tag": "home-assistant", "notes": 4}]})
        if path == "/siris/brain/note":
            body = {news.PREFERENCES_NOTE: PREFS, news.OWNER_NOTE: OWNER}.get(request.url.params["title"])
            return httpx.Response(200, json={"title": "x", "body": body}) if body else httpx.Response(404)
        if path == "/siris/status":
            return httpx.Response(200, json={"llm_provider": "ollama"})
        return httpx.Response(404)


@pytest.fixture
def ai(monkeypatch, state):
    fake = FakeSirisAI()
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(fake))
    monkeypatch.setattr(service, "brief_service", service.BriefService())
    monkeypatch.setattr(service, "news_service", news.NewsService())
    reset_hub({"SIRISAI_URL": "http://sirisai:8000", "SIRISAI_API_KEY": "ai-key"})
    yield fake
    reset_hub({})


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_brief_requires_login(client, ai) -> None:
    assert client.get("/api/v1/brief").status_code == 401
    assert client.get("/api/v1/brief/status").status_code == 401
    assert client.post("/api/v1/brief/dismiss").status_code == 401


def test_brief_gathers_every_source_and_falls_back_to_home_assistant_calendar(client, ai) -> None:
    r = client.get("/api/v1/brief", headers=AUTH)
    assert r.status_code == 200
    brief = r.json()
    assert brief["greeting"].endswith(", Brad")
    assert brief["schedule"][0]["title"] == "Dentist" and brief["schedule"][0]["time"] == "10:00 am"
    assert brief["todo"] == ["Bins out"] and brief["email"]["important"][0]["from"] == "Bob"
    assert brief["weather"]["today"]["conditions"] == "Sunny" and brief["brain"]["inbox"] == 1
    assert brief["news"]["interests_from"] == news.PREFERENCES_NOTE
    first = brief["news"]["topics"][0]["stories"][0]
    assert first["title"] == "Home Assistant 2026.10 released" and "home assistant" in first["matches"]
    assert brief["unavailable"] == []
    assert ai.tools["calendar_upcoming_events"] == 1 and ai.tools["home_assistant_get_calendar_events"] == 1

    # Cached for ten minutes; ?fresh=true rebuilds.
    client.get("/api/v1/brief", headers=AUTH)
    assert ai.tools["weather_forecast"] == 1
    client.get("/api/v1/brief?fresh=true", headers=AUTH)
    assert ai.tools["weather_forecast"] == 2


def test_a_broken_source_blanks_only_its_section(client, ai) -> None:
    ai.broken = {"email_list_unread"}
    ai.missing |= {"health_summary"}  # not configured: just absent, not "unavailable"
    brief = client.get("/api/v1/brief", headers=AUTH).json()
    assert brief["unavailable"] == ["email"] and brief["email"] is None
    assert brief["health"] == [] and brief["schedule"][0]["title"] == "Dentist"


def test_brief_without_sirisai_still_answers(client, monkeypatch, state) -> None:
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(lambda r: httpx.Response(503)))
    monkeypatch.setattr(service, "brief_service", service.BriefService())
    monkeypatch.setattr(service, "news_service", news.NewsService())
    reset_hub({})
    brief = client.get("/api/v1/brief", headers=AUTH).json()
    assert "SirisAI" in brief["unavailable"] and "news" in brief["unavailable"]
    assert brief["news"]["interests_from"].startswith("default topics")
    reset_hub({})


def test_status_and_dismiss_endpoints(client, ai, monkeypatch) -> None:
    monkeypatch.setattr(service, "now_local", lambda: datetime(2026, 10, 8, 7, 15, tzinfo=MEL))
    assert client.get("/api/v1/brief/status", headers=AUTH).json()["show"] is True
    after = client.post("/api/v1/brief/dismiss", headers=AUTH).json()
    assert after["show"] is False and after["dismissed_today"] is True
    assert client.get("/api/v1/brief/status", headers=AUTH).json()["show"] is False
