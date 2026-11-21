"""Hour-by-hour weather from SirisAI (7.3's /siris/hub/v1/forecast/hourly), shared by the weekend planner, the
garden reminder and the fuel suggestion (for where home is)."""

from __future__ import annotations

from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub


async def hourly(hub: Hub, days: int = 4, past_days: int = 0) -> dict[str, Any] | None:
    body = await sirisai_api.get(hub, "/siris/hub/v1/forecast/hourly", params={"days": days, "past_days": past_days}, timeout=15.0)
    if not isinstance(body, dict) or body.get("unavailable") or not isinstance(body.get("hours"), list):
        return None
    return body
