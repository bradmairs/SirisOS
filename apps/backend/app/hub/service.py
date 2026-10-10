"""Runs connectors concurrently with per-connector timeouts and a short
cache, so the home screen is one fast call and one dead app only blanks
its own tile (ADR 106)."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Awaitable, Callable, Mapping

import httpx

from app.hub.connectors import build_connectors
from app.hub.connectors.base import AppStatus, Connector, ConnectorError

logger = logging.getLogger(__name__)

# Tests swap this for an httpx.MockTransport.
transport: httpx.AsyncBaseTransport | None = None

# How long a cached status/widget may be served while a refresh runs in the
# background (stale-while-revalidate). Past this, callers wait for fresh data.
STALE_FOR_SECONDS = 300.0


def _verify() -> bool:
    return os.getenv("SIRISOS_HUB_VERIFY_SSL", "true").lower() not in ("0", "false", "no")


def make_client(timeout: float | httpx.Timeout = 6.0) -> httpx.AsyncClient:
    """A dedicated client, for callers that own its lifetime (e.g. a long SSE relay)."""
    return httpx.AsyncClient(timeout=timeout, transport=transport, verify=_verify(), follow_redirects=False)


_shared: tuple[Any, Any, httpx.AsyncClient] | None = None


def shared_client() -> httpx.AsyncClient:
    """One pooled, keep-alive client per event loop: connections to the other
    apps are reused across requests instead of re-opened every poll."""
    global _shared
    loop = asyncio.get_running_loop()
    if _shared is None or _shared[0] is not loop or _shared[1] is not transport or _shared[2].is_closed:
        client = httpx.AsyncClient(
            timeout=6.0,
            transport=transport,
            verify=_verify(),
            follow_redirects=False,
            limits=httpx.Limits(max_connections=40, max_keepalive_connections=20, keepalive_expiry=60),
        )
        _shared = (loop, transport, client)
    return _shared[2]


class Hub:
    def __init__(self, env: Mapping[str, str], timeout: float = 5.0, ttl: float = 20.0, stale_for: float = STALE_FOR_SECONDS) -> None:
        self.connectors: list[Connector] = build_connectors(env)
        self.by_id = {c.id: c for c in self.connectors}
        self.timeout = timeout
        self.ttl = ttl
        self.stale_for = stale_for
        # key -> (fetched_at, value)
        self._cache: dict[tuple[str, str], tuple[float, Any]] = {}
        # key -> in-flight fetch, so concurrent callers share one upstream call.
        self._inflight: dict[tuple[str, str], asyncio.Future] = {}

    def get(self, app_id: str) -> Connector | None:
        return self.by_id.get(app_id)

    def _refresh(self, key: tuple[str, str], make: Callable[[], Awaitable[Any]]) -> asyncio.Future:
        pending = self._inflight.get(key)
        if pending is not None and not pending.done() and pending.get_loop() is asyncio.get_running_loop():
            return pending

        async def run() -> Any:
            try:
                value = await make()
                self._cache[key] = (time.monotonic(), value)
                return value
            finally:
                self._inflight.pop(key, None)

        task = asyncio.ensure_future(run())
        self._inflight[key] = task
        return task

    async def _cached(self, key: tuple[str, str], fresh: bool, make: Callable[[], Awaitable[Any]]) -> Any:
        hit = self._cache.get(key)
        if hit and not fresh:
            age = time.monotonic() - hit[0]
            if age < self.ttl:
                return hit[1]
            if age < self.stale_for:
                # Answer now with what we have; the refresh lands for the next poll.
                self._refresh(key, make)
                return hit[1]
        return await asyncio.shield(self._refresh(key, make))

    async def status(self, connector: Connector, client: httpx.AsyncClient | None = None, fresh: bool = False) -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            try:
                result = await asyncio.wait_for(connector.status(client or shared_client()), self.timeout)
            except asyncio.TimeoutError:
                result = AppStatus(state="down", detail="Timed out")
            except Exception as exc:  # never let one app break the page
                logger.warning("Hub status for %s failed", connector.id, exc_info=True)
                result = AppStatus(state="down", detail=f"Error: {type(exc).__name__}")
            return result.to_dict()

        return await self._cached((connector.id, "status"), fresh, run)

    async def widget(self, connector: Connector, client: httpx.AsyncClient | None = None, fresh: bool = False) -> dict[str, Any] | None:
        if connector.launch_only or not connector.configured:
            return None

        async def run() -> dict[str, Any] | None:
            try:
                widget = await asyncio.wait_for(connector.widget(client or shared_client()), self.timeout)
            except ConnectorError as exc:
                return {"error": str(exc)}
            except asyncio.TimeoutError:
                return {"error": "Timed out"}
            except NotImplementedError:
                return None
            except Exception as exc:
                logger.warning("Hub widget for %s failed", connector.id, exc_info=True)
                return {"error": f"Unavailable: {type(exc).__name__}"}
            return widget.to_dict() if widget else None

        return await self._cached((connector.id, "widget"), fresh, run)

    async def app(self, connector: Connector, client: httpx.AsyncClient | None = None, fresh: bool = False, with_widget: bool = False) -> dict[str, Any]:
        if not with_widget:
            return {**connector.describe(), "status": await self.status(connector, client, fresh)}
        # Status and widget in parallel: one round trip per app, not two.
        status, widget = await asyncio.gather(self.status(connector, client, fresh), self.widget(connector, client, fresh))
        return {**connector.describe(), "status": status, "widget": widget if status["state"] in ("ok", "degraded") else None}

    async def apps(self, fresh: bool = False, with_widgets: bool = False) -> list[dict[str, Any]]:
        return list(await asyncio.gather(*(self.app(c, None, fresh, with_widgets) for c in self.connectors)))


_hub: Hub | None = None


def get_hub() -> Hub:
    global _hub
    if _hub is None:
        _hub = Hub(os.environ)
    return _hub


def reset_hub(env: Mapping[str, str] | None = None, **kwargs: Any) -> Hub:
    global _hub
    from app.hub import guest

    guest.reset()
    _hub = Hub(os.environ if env is None else env, **kwargs)
    return _hub
