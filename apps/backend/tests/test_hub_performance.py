"""Hub latency behaviour: request coalescing, stale-while-revalidate, and
status + widget fetched in parallel."""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from app.hub import service
from app.hub.service import Hub

ENV = {"GVW_URL": "http://gvw:8092", "ARCHIVE_URL": "http://archive:8091", "ARCHIVE_API_KEY": "k"}


class SlowApps:
    def __init__(self, delay: float = 0.05) -> None:
        self.delay = delay
        self.calls: list[str] = []
        self.version = "1.0.0"

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(f"{request.url.host}{request.url.path}")
        await asyncio.sleep(self.delay)
        if request.url.host == "gvw":
            return httpx.Response(200, json={"status": "ok", "version": self.version})
        return httpx.Response(200, json={"status": "ok", "needsReview": 1, "totalMedia": 2, "unassignedMedia": 0, "totalAssets": 3, "lastScan": None})


@pytest.fixture
def apps(monkeypatch):
    fake = SlowApps()
    monkeypatch.setattr(service, "transport", httpx.MockTransport(fake))
    monkeypatch.setattr(service, "_shared", None)
    return fake


def test_concurrent_requests_share_one_upstream_call(apps):
    hub = Hub(ENV)
    gvw = hub.get("gvw")

    async def scenario():
        return await asyncio.gather(*(hub.status(gvw) for _ in range(10)))

    results = asyncio.run(scenario())
    assert {r["state"] for r in results} == {"ok"}
    assert apps.calls.count("gvw/healthz") == 1


def test_stale_value_is_served_instantly_and_refreshed_in_background(apps):
    hub = Hub(ENV, ttl=0.01, stale_for=60)
    gvw = hub.get("gvw")

    async def scenario():
        first = await hub.status(gvw)
        await asyncio.sleep(0.02)  # now stale
        apps.version = "2.0.0"
        started = time.perf_counter()
        stale = await hub.status(gvw)
        elapsed = time.perf_counter() - started
        await asyncio.sleep(apps.delay * 3)  # let the background refresh land
        return first, stale, elapsed, hub._cache[("gvw", "status")][1]

    first, stale, elapsed, refreshed = asyncio.run(scenario())
    assert first["version"] == stale["version"] == "1.0.0"
    assert elapsed < apps.delay  # didn't wait on the upstream
    assert refreshed["version"] == "2.0.0"


def test_too_stale_or_fresh_requests_wait_for_new_data(apps):
    hub = Hub(ENV, ttl=0.01, stale_for=0.02)
    gvw = hub.get("gvw")

    async def scenario():
        await hub.status(gvw)
        await asyncio.sleep(0.03)
        apps.version = "3.0.0"
        expired = await hub.status(gvw)
        apps.version = "4.0.0"
        forced = await hub.status(gvw, fresh=True)
        return expired, forced

    expired, forced = asyncio.run(scenario())
    assert expired["version"] == "3.0.0"
    assert forced["version"] == "4.0.0"


def test_status_and_widget_are_fetched_in_parallel(apps):
    apps.delay = 0.1
    hub = Hub(ENV)

    async def scenario():
        started = time.perf_counter()
        app = await hub.app(hub.get("archive"), with_widget=True)
        return app, time.perf_counter() - started

    app, elapsed = asyncio.run(scenario())
    assert app["status"]["state"] == "ok"
    assert app["widget"]["title"] == "Archive"
    assert elapsed < 0.18  # one round trip, not two sequential ones


def test_shared_client_is_reused_within_a_loop(apps):
    async def scenario():
        return service.shared_client() is service.shared_client()

    assert asyncio.run(scenario()) is True
