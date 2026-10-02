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


def make_client(timeout: float = 6.0) -> httpx.AsyncClient:
    verify = os.getenv("SIRISOS_HUB_VERIFY_SSL", "true").lower() not in ("0", "false", "no")
    return httpx.AsyncClient(timeout=timeout, transport=transport, verify=verify, follow_redirects=False)


class Hub:
    def __init__(self, env: Mapping[str, str], timeout: float = 5.0, ttl: float = 20.0) -> None:
        self.connectors: list[Connector] = build_connectors(env)
        self.by_id = {c.id: c for c in self.connectors}
        self.timeout = timeout
        self.ttl = ttl
        self._cache: dict[tuple[str, str], tuple[float, Any]] = {}

    def get(self, app_id: str) -> Connector | None:
        return self.by_id.get(app_id)

    async def _cached(self, key: tuple[str, str], fresh: bool, make: Callable[[], Awaitable[Any]]) -> Any:
        hit = self._cache.get(key)
        if hit and not fresh and hit[0] > time.monotonic():
            return hit[1]
        value = await make()
        self._cache[key] = (time.monotonic() + self.ttl, value)
        return value

    async def status(self, connector: Connector, client: httpx.AsyncClient, fresh: bool = False) -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            try:
                result = await asyncio.wait_for(connector.status(client), self.timeout)
            except asyncio.TimeoutError:
                result = AppStatus(state="down", detail="Timed out")
            except Exception as exc:  # never let one app break the page
                logger.warning("Hub status for %s failed", connector.id, exc_info=True)
                result = AppStatus(state="down", detail=f"Error: {type(exc).__name__}")
            return result.to_dict()

        return await self._cached((connector.id, "status"), fresh, run)

    async def widget(self, connector: Connector, client: httpx.AsyncClient, fresh: bool = False) -> dict[str, Any] | None:
        if connector.launch_only or not connector.configured:
            return None

        async def run() -> dict[str, Any] | None:
            try:
                widget = await asyncio.wait_for(connector.widget(client), self.timeout)
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

    async def app(self, connector: Connector, client: httpx.AsyncClient, fresh: bool = False, with_widget: bool = False) -> dict[str, Any]:
        out = {**connector.describe(), "status": await self.status(connector, client, fresh)}
        if with_widget:
            out["widget"] = await self.widget(connector, client, fresh) if out["status"]["state"] in ("ok", "degraded") else None
        return out

    async def apps(self, fresh: bool = False, with_widgets: bool = False) -> list[dict[str, Any]]:
        async with make_client() as client:
            return list(
                await asyncio.gather(*(self.app(c, client, fresh, with_widgets) for c in self.connectors))
            )


_hub: Hub | None = None


def get_hub() -> Hub:
    global _hub
    if _hub is None:
        _hub = Hub(os.environ)
    return _hub


def reset_hub(env: Mapping[str, str] | None = None, **kwargs: Any) -> Hub:
    global _hub
    _hub = Hub(os.environ if env is None else env, **kwargs)
    return _hub
