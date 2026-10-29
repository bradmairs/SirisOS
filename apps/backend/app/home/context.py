"""The part of the day, for the adaptive Home (3.1, 4.9).

- morning   get out the door: top 3, the first event (and when to leave), today's weather
- work      weekdays: the next meeting, top 3, work tasks
- weekend   Saturday and Sunday daytime: what's on, the weather, life admin
- evening   switch off: the wrap-up, personal tasks, fitness, home (and welcome home)
- winddown  calm: tomorrow at a glance, what the brain learned, a capture box
- night     the clock and tomorrow's first event

When each starts, and what it shows, is the schedule (app/home/schedule.py): by default
weekdays are morning 5:00, work 8:30, evening 16:30, wind down 20:00, night 23:00, and
weekends morning 5:00, daytime 10:00, evening 17:00, wind down 20:00, night 23:00.

`home` and `home_since` come from SirisAI's presence check (None when it isn't set up);
today's and tomorrow's events and weather from its calendar and forecast.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from app.brief.service import zone
from app.hub import sirisai_api
from app.home import schedule
from app.hub.service import Hub
from app.wrapup import service as wrapup


def phase(at: datetime) -> str:
    return schedule.phase(at)


def _events(raw: Any) -> list[dict[str, Any]]:
    """Today's and tomorrow's events, soonest first: what the cards and Coming up need."""
    out = []
    for e in (raw or {}).get("events") or []:
        if isinstance(e, dict) and e.get("start"):
            out.append({"title": e.get("title") or "Event", "start": e["start"], "end": e.get("end"),
                        "all_day": bool(e.get("all_day")), "location": e.get("location") or None})
    return sorted(out, key=lambda e: (e["start"][:10], not e["all_day"], e["start"]))


async def current(hub: Hub, now: datetime | None = None) -> dict[str, Any]:
    at = (now or datetime.now(zone())).astimezone(zone())
    day = at.date()
    presence, calendar, forecast = await asyncio.gather(
        sirisai_api.get(hub, "/siris/hub/v1/presence", timeout=5.0),
        sirisai_api.get(hub, "/siris/hub/v1/calendar", params={"start": day.isoformat(), "end": (day + timedelta(days=2)).isoformat()}, timeout=8.0),
        sirisai_api.get(hub, "/siris/hub/v1/forecast", params={"days": 2}, timeout=8.0),
    )
    tomorrow_top3 = (wrapup.saved(day) or {}).get("top3") or []
    plan = schedule.load()
    current_phase = schedule.phase(at, plan)
    days = (forecast or {}).get("days") or []
    return {
        "phase": current_phase,
        # Which Home sections lead now, in order, and the widgets left out (set in Times of day).
        "sections": plan.sections[current_phase],
        "hidden": plan.hidden[current_phase],
        "leave_minutes": plan.leave_minutes,
        # The phone tab bar's last two buttons for now: "auto", or the screen you picked.
        "dock": plan.dock[current_phase].model_dump(),
        "local_time": at.isoformat(timespec="minutes"),
        "home": (presence or {}).get("home"),
        # When you got home (or left): null until SirisAI has seen a change.
        "home_since": (presence or {}).get("since"),
        "wrapped_up": wrapup.saved(day) is not None,
        "top3": wrapup.top3_for(day),
        "tomorrow_top3": tomorrow_top3,
        "events": None if calendar is None or calendar.get("guest_mode") else _events(calendar),
        "weather_today": days[0] if len(days) > 0 else None,
        "weather_tomorrow": days[1] if len(days) > 1 else None,
    }
