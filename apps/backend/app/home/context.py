"""The part of the day, for the adaptive Home (3.1).

- morning   5:00–9:59 every day: the brief and today's top 3 first
- work      10:00–16:59 on weekdays: tasks and the next meeting first
- weekend   10:00–16:59 on Saturday and Sunday: home and tasks
- evening   17:00–22:59: the wrap-up, then home controls
- night     23:00–4:59: tomorrow's top 3, quietly

`home` comes from SirisAI's last presence check (None when it isn't set up).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.brief.service import zone
from app.hub import sirisai_api
from app.hub.service import Hub
from app.wrapup import service as wrapup


def phase(at: datetime) -> str:
    h = at.hour
    if 5 <= h < 10:
        return "morning"
    if 10 <= h < 17:
        return "weekend" if at.weekday() >= 5 else "work"
    if 17 <= h < 23:
        return "evening"
    return "night"


async def current(hub: Hub, now: datetime | None = None) -> dict[str, Any]:
    at = (now or datetime.now(zone())).astimezone(zone())
    presence = await sirisai_api.get(hub, "/siris/hub/v1/presence", timeout=5.0)
    day = at.date()
    tomorrow_top3 = (wrapup.saved(day) or {}).get("top3") or []
    return {
        "phase": phase(at),
        "local_time": at.isoformat(timespec="minutes"),
        "home": (presence or {}).get("home"),
        "wrapped_up": wrapup.saved(day) is not None,
        "top3": wrapup.top3_for(day),
        "tomorrow_top3": tomorrow_top3,
    }
