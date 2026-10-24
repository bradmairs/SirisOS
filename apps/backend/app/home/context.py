"""The part of the day, for the adaptive Home (3.1).

- morning   the brief and today's top 3 first
- work      weekdays: tasks and the next meeting first
- weekend   Saturday and Sunday daytime: home and tasks
- evening   the wrap-up
- night     tomorrow's top 3, quietly

When each starts, and which sections lead in it, is the schedule (app/home/schedule.py):
by default weekdays are morning 5:00, work 8:30, evening 16:30, night 23:00, and
weekends morning 5:00, daytime 10:00, evening 17:00, night 23:00.

`home` comes from SirisAI's last presence check (None when it isn't set up).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.brief.service import zone
from app.hub import sirisai_api
from app.home import schedule
from app.hub.service import Hub
from app.wrapup import service as wrapup


def phase(at: datetime) -> str:
    return schedule.phase(at)


async def current(hub: Hub, now: datetime | None = None) -> dict[str, Any]:
    at = (now or datetime.now(zone())).astimezone(zone())
    presence = await sirisai_api.get(hub, "/siris/hub/v1/presence", timeout=5.0)
    day = at.date()
    tomorrow_top3 = (wrapup.saved(day) or {}).get("top3") or []
    plan = schedule.load()
    current_phase = schedule.phase(at, plan)
    return {
        "phase": current_phase,
        # Which Home sections lead now, in order (set in Times of day).
        "sections": plan.sections[current_phase],
        "local_time": at.isoformat(timespec="minutes"),
        "home": (presence or {}).get("home"),
        "wrapped_up": wrapup.saved(day) is not None,
        "top3": wrapup.top3_for(day),
        "tomorrow_top3": tomorrow_top3,
    }
