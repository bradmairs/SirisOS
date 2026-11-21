"""10.6: smarter notifications: seen in the app, still true, in the app now, one device, asleep or busy,
home things at home, learning what's ignored, a daily cap and replacing on the lock screen."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.brief.service import zone
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import get_hub, reset_hub
from app.push import digest, notifier, smart, store
from tests.test_hub import AUTH, ENV
from tests.test_push import Browser

PHONE, MAC = "https://push.example.com/send/phone", "https://push.example.com/send/mac"
NOON = datetime(2026, 11, 24, 12, 0, tzinfo=zone())  # a Tuesday


@pytest.fixture
def world(monkeypatch, tmp_path):
    for env, name in (("SUBSCRIPTIONS", "subs"), ("SENT", "sent"), ("HEALTH", "health")):
        monkeypatch.setenv(f"SIRISOS_PUSH_{env}_PATH", str(tmp_path / f"push-{name}.json"))
    phone, mac = Browser(), Browser()
    store.upsert(store.Subscription.model_validate(phone.subscription(PHONE) | {"label": "iPhone"}))
    store.upsert(store.Subscription.model_validate(mac.subscription(MAC) | {"label": "Mac"}))
    state = {"got": [], "inbox": [], "home": True, "events": [], "bed": "22:30", "wake": "06:40", "now": NOON, "msgs": []}
    who = {PHONE: phone, MAC: mac}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.url.host == "push.example.com":
            state["got"].append((url.rsplit("/", 1)[1], json.loads(who[url].decrypt(request.content))))
            return httpx.Response(201)
        path = request.url.path
        if path == "/siris/hub/v1/health/overview":
            return httpx.Response(200, json={"bedtime": {"bedtime": state["bed"]}, "sleep": {"last_night": {"end": f"2026-11-24T{state['wake']}:00+11:00"}}})
        if path == "/siris/hub/v1/calendar":
            return httpx.Response(200, json={"events": state["events"]})
        if path == "/siris/hub/v1/presence":
            return httpx.Response(200, json={"home": state["home"]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(hub_service, "transport", transport)
    client = httpx.AsyncClient(transport=transport)
    monkeypatch.setattr(notifier, "shared_client", lambda: client)
    monkeypatch.setattr(notifier, "test_mode", lambda: False)
    monkeypatch.setattr(notifier, "check_in", lambda now: asyncio.sleep(0, 0))
    reset_hub(ENV)

    async def collect(hub, now):
        return list(state["msgs"])

    async def inbox(hub):
        return {"items": [{"id": i} for i in state["inbox"]]}

    monkeypatch.setattr(notifier, "collect", collect)
    from app.attention import service as attention

    monkeypatch.setattr(attention, "inbox", inbox)

    def run(at: datetime | None = None) -> list[tuple[str, dict]]:
        before = len(state["got"])
        asyncio.run(notifier.run_once(get_hub(), at or state["now"]))
        return state["got"][before:]

    return TestClient(app), state, run


def titles(got: list[tuple[str, dict]]) -> list[str]:
    """Until the app has told SirisOS which device you use, every device gets it: the titles, once each."""
    return list(dict.fromkeys(p["title"] for _, p in got))


def msg(key: str, title: str = "Something", urgency: str = "normal", topic: str = "brief") -> dict:
    return notifier.message(key, topic, title, "", "/", urgency)


def test_seen_in_the_app_is_not_sent_and_seen_ones_are_dropped_from_the_roundup(world):
    c, state, run = world
    assert c.post("/api/v1/push/seen", json={"keys": ["bins:2026-11-25"]}, headers=AUTH).json() == {"seen": 1}
    state["msgs"] = [msg("bins:2026-11-25", "Bins out tonight")]
    assert run() == []
    assert "bins:2026-11-25" in store.sent()  # not tried again
    # A roundup item seen before the roundup goes is left out of it.
    state["msgs"] = [msg("weekend:2026-11-28", "Your weekend outside"), msg("recap:2026-10", "October in short")]
    assert run() == []  # both wait for 18:00
    assert len(digest.load()["held"]) == 2
    c.post("/api/v1/push/seen", json={"keys": ["recap:2026-10"]}, headers=AUTH)
    state["msgs"] = []
    got = run(NOON.replace(hour=18, minute=1))
    assert titles(got) == ["Your weekend outside"]


def test_held_inbox_items_already_dealt_with_are_dropped(world):
    c, state, run = world
    state["inbox"] = ["a1", "a2"]
    state["msgs"] = [msg("inbox:a1", "Disk nearly full", topic="apps"), msg("inbox:a2", "New device", topic="apps")]
    run()
    state["inbox"], state["msgs"] = ["a2"], []
    got = run(NOON.replace(hour=18, minute=1))
    assert titles(got) == ["New device"]


def test_using_the_app_shows_a_banner_instead_of_a_push(world):
    c, state, run = world
    r = c.post("/api/v1/push/active", json={"device": "mac-1", "endpoint": MAC, "label": "Mac"}, headers=AUTH).json()
    assert r == {"inapp": []}
    state["msgs"] = [msg("task:t1", "Call the plumber")]
    smart.heartbeat("mac-1", MAC, "Mac", None, NOON)
    assert run() == []
    banners = c.post("/api/v1/push/active", json={"device": "mac-1", "endpoint": MAC}, headers=AUTH).json()["inapp"]
    assert [b["title"] for b in banners] == ["Call the plumber"]
    c.post("/api/v1/push/seen", json={"keys": ["task:t1"]}, headers=AUTH)
    assert c.post("/api/v1/push/active", json={"device": "mac-1"}, headers=AUTH).json()["inapp"] == []
    # Urgent still pushes, to every device.
    state["msgs"] = [msg("inbox:x", "Plex is down", "high", "apps")]
    assert sorted(d for d, _ in run()) == ["mac", "phone"]


def test_one_device_the_one_used_last(world):
    c, state, run = world
    smart.heartbeat("phone-1", PHONE, "iPhone", None, NOON - timedelta(hours=2))
    smart.heartbeat("mac-1", MAC, "Mac", None, NOON - timedelta(hours=1))
    state["msgs"] = [msg("task:t2", "Timesheet")]
    assert [d for d, _ in run()] == ["mac"]


def test_asleep_waits_for_the_morning_and_chosen_times_still_come(world):
    c, state, run = world
    night = NOON.replace(hour=23, minute=15)
    state["msgs"] = [msg("weekend:2026-11-28", "Your weekend outside"), msg("task:t3", "Take the bins out", topic="brief")]
    got = run(night)
    assert titles(got) == ["Take the bins out"]  # a task at its time
    state["msgs"] = []
    assert run(night.replace(hour=23, minute=59)) == []
    got = run((night + timedelta(days=1)).replace(hour=7, minute=31))
    assert titles(got) == ["Your weekend outside"]  # the morning roundup


def test_meetings_and_focus_blocks_hold_until_they_end(world):
    c, state, run = world
    state["events"] = [{"title": "Design review", "start": "2026-11-24T11:30:00+11:00", "end": "2026-11-24T12:30:00+11:00"}]
    state["inbox"] = ["n1"]
    state["msgs"] = [msg("inbox:n1", "New device on IoT", topic="apps")]
    digest.change(on=False)  # straight away, unless busy
    assert run() == []
    state["msgs"] = []
    assert run(NOON.replace(minute=20)) == []
    got = run(NOON.replace(minute=31))
    assert titles(got) == ["New device on IoT"]
    # A focus block in the app does the same.
    c.post("/api/v1/push/active", json={"device": "phone-1", "focus_until": (NOON + timedelta(minutes=50)).isoformat()}, headers=AUTH)
    assert smart.busy_until(smart.load(), {"events": []}, NOON + timedelta(minutes=10)) is not None


def test_home_things_wait_until_someones_home(world):
    c, state, run = world
    state["home"] = False
    state["msgs"] = [msg("bins:2026-11-25", "Bins out tonight")]
    assert run(NOON.replace(hour=19)) == []
    state["msgs"], state["home"] = [], True
    doc = smart.load()
    doc["context"]["at"] = "2000-01-01T00:00:00+00:00"  # presence is asked again
    smart.save(doc)
    got = run(NOON.replace(hour=19, minute=40))
    assert titles(got) == ["Bins out tonight"]


def test_ignored_kinds_move_to_the_roundup_and_can_be_set(world):
    c, state, run = world
    digest.change(on=False)
    for i in range(5):
        state["msgs"] = [msg(f"catchup:2026-10-{i + 1:02d}", "Catch up with Sam?")]
        run(NOON.replace(hour=9) + timedelta(days=i))
    smart.tick(NOON + timedelta(days=6))
    rep = c.get("/api/v1/push/smart", headers=AUTH).json()
    row = next(r for r in rep["kinds"] if r["kind"] == "catchup")
    assert row["demoted"] and row["effective"] == "roundup" and row["label"] == "Catch-ups"
    # Opening one counts.
    state["msgs"] = [msg("weekend:2026-11-28", "Your weekend outside")]
    run()
    assert TestClient(app).post("/api/v1/push/act/opened", json={"key": "weekend:2026-11-28"}).json() == {"counted": True}
    assert TestClient(app).post("/api/v1/push/act/opened", json={"key": "never:sent"}).json() == {"counted": False}
    rep = c.put("/api/v1/push/smart/kinds/weekend", json={"mode": "off"}, headers=AUTH).json()
    assert next(r for r in rep["kinds"] if r["kind"] == "weekend")["mode"] == "off"
    state["msgs"] = [msg("weekend:2026-12-05", "Your weekend outside")]
    assert run() == []
    assert c.put("/api/v1/push/smart/kinds/weekend", json={"mode": "loud"}, headers=AUTH).status_code == 422


def test_a_daily_cap_and_newer_ones_replace_older_ones(world):
    c, state, run = world
    digest.change(on=False)
    c.put("/api/v1/push/smart", json={"cap": 2}, headers=AUTH)
    state["msgs"] = [msg("weekend:a", "One"), msg("netdev:b", "Two"), msg("recap:c", "Three"), msg("task:d", "Four")]
    got = run()
    assert set(titles(got)) == {"One", "Two", "Four"}
    assert [m["title"] for m in digest.load()["held"]] == ["Three"]
    tags = {p["title"]: p["tag"] for _, p in got}
    assert tags == {"One": "kind:weekend", "Two": "kind:netdev", "Four": "task:d"}
