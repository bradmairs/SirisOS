"""10.2: notifications that can wait come together in a morning and evening roundup."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

import httpx

from app.brief.service import zone
from app.hub import service as hub_service
from app.push import digest, notifier, store
from tests.test_hub import AUTH
from tests.test_push import Browser, data  # noqa: F401  (fixture: its own data folder)


def _at(h: int, m: int = 0, day: int = 19) -> datetime:
    return datetime(2026, 11, day, h, m, tzinfo=zone())


def test_urgent_and_timely_go_now_the_rest_waits(monkeypatch):
    browser = Browser()
    store.upsert(store.Subscription.model_validate(browser.subscription() | {"topics": ["inbox", "brief", "apps"]}))
    received: list[dict] = []

    def push_service(request: httpx.Request) -> httpx.Response:
        received.append(json.loads(browser.decrypt(request.content)))
        return httpx.Response(201)

    client = httpx.AsyncClient(transport=httpx.MockTransport(push_service))
    monkeypatch.setattr(notifier, "shared_client", lambda: client)
    batch = {"now": [
        notifier.message("inbox:ai:1", "inbox", "Front door left open", "", "/inbox", "high"),
        notifier.message("task:t1:2026-11-19T10:00", "inbox", "Call the plumber"),
        notifier.message("review:2026-11-19", "brief", "Your weekly review"),
        notifier.message("renewal:rego", "brief", "Car rego due in 14 days"),
    ]}

    async def collect(hub, now):
        return batch["now"]

    monkeypatch.setattr(notifier, "collect", collect)
    asyncio.run(notifier.run_once(hub_service.Hub({}), _at(10)))
    assert [r["title"] for r in received] == ["Front door left open", "Call the plumber"]
    assert digest.settings()["waiting"] == 2
    # Nothing more until the evening roundup; then one notification with both, and the queue is empty.
    asyncio.run(notifier.run_once(hub_service.Hub({}), _at(17, 59)))
    assert len(received) == 2
    asyncio.run(notifier.run_once(hub_service.Hub({}), _at(18, 0)))
    assert received[-1]["title"] == "Evening roundup: 2 things"
    assert received[-1]["body"] == "• Your weekly review\n• Car rego due in 14 days"
    assert digest.settings()["waiting"] == 0
    asyncio.run(notifier.run_once(hub_service.Hub({}), _at(18, 5)))
    assert len(received) == 3


def test_one_thing_waiting_is_sent_as_itself_and_off_means_straight_away():
    digest.hold([notifier.message("renewal:rego", "brief", "Car rego due in 14 days", "Renew online", "/life")], _at(6, 10))
    assert digest.due(_at(7, 0)) is None  # before the first roundup
    m = digest.due(_at(7, 30))
    assert m["title"] == "Car rego due in 14 days" and m["body"] == "Renew online" and m["key"] == "digest:2026-11-19 07:30"
    assert digest.due(_at(8, 0)) is None  # that roundup's been
    digest.change(on=False)
    now, later = digest.split([notifier.message("renewal:x", "brief", "x")])
    assert len(now) == 1 and later == []


def test_settings_by_api(client_auth=None):
    from fastapi.testclient import TestClient

    from app.entrypoint import app

    c = TestClient(app)
    assert c.get("/api/v1/push/digest", headers=AUTH).json()["times"] == ["07:30", "18:00"]
    r = c.put("/api/v1/push/digest", json={"times": ["12:00", "06:45", "bad"]}, headers=AUTH).json()
    assert r["times"] == ["06:45", "12:00"]
    assert c.put("/api/v1/push/digest", json={"times": ["nope"]}, headers=AUTH).status_code == 422
    assert c.put("/api/v1/push/digest", json={"on": False}, headers=AUTH).json()["on"] is False
