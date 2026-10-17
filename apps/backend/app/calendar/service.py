"""Calendar events for a date range, read from SirisAI (its hub route
/siris/hub/v1/calendar), which merges every connected calendar. Used by the
week view and by "log this as CPD" suggestions."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from app.hub.connectors.sirisai import SirisAIConnector
from app.hub.service import Hub, shared_client

MAX_DAYS = 62


async def events(hub: Hub, start: date, end: date) -> dict[str, Any]:
    """{start, end, events, guest_mode, unavailable}. `events` is None when
    SirisAI isn't connected, is too old to have the route, failed, or guest
    mode is on; it never raises."""
    base: dict[str, Any] = {"start": start.isoformat(), "end": end.isoformat(), "events": None, "guest_mode": False, "unavailable": True}
    connector = hub.get("sirisai")
    if not isinstance(connector, SirisAIConnector) or not connector.configured:
        return base
    try:
        response = await shared_client().get(f"{connector.base_url}/siris/hub/v1/calendar", headers=connector.headers(),
                                             params={"start": start.isoformat(), "end": end.isoformat()}, timeout=20.0)
        if response.status_code >= 400:
            return base
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return base
    return {**base, "events": body.get("events"), "guest_mode": bool(body.get("guest_mode")), "unavailable": bool(body.get("unavailable"))}
