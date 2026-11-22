"""Goals that steer themselves (11.3).

Each yearly goal gets a projected finish at its pace so far ("on pace for 1,100 km of 1,200"). One that's behind gets a
small, concrete step for this week, sized to close the gap over the weeks left ("run 24 km this week: 3 runs of 8"),
a slot in today's plan when there's room, and a Monday-evening notification if it's still slipping.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from app.hub.service import Hub


def project(g: dict[str, Any], today: date) -> dict[str, Any]:
    """Pace so far, projected to the 31st of December."""
    year = int(g.get("year") or today.year)
    start, end = date(year, 1, 1), date(year, 12, 31)
    elapsed = max(1, (min(today, end) - start).days + 1)
    left_days = max(0, (end - today).days)
    weeks_left = max(1, math.ceil(left_days / 7))
    value, target = g.get("value"), g.get("target")
    if g.get("kind") == "done" or value is None or not target:
        return {"projected": None, "projected_percent": None, "weekly": None, "weeks_left": weeks_left}
    projected = value + value / elapsed * left_days
    need = max(0.0, target - value)
    return {"projected": round(projected, 1), "projected_percent": min(999, round(projected / target * 100)),
            "weekly": round(need / weeks_left, 1) if need else 0, "weeks_left": weeks_left}


def step(g: dict[str, Any], p: dict[str, Any]) -> dict[str, Any] | None:
    """A small step for this week, for a goal that's behind."""
    if g.get("state") != "behind":
        return None
    kind, w, unit = g.get("kind"), p.get("weekly") or 0, g.get("unit") or ""
    if kind == "running_km" and w:
        runs = max(1, min(4, math.ceil(w / 8)))
        return {"text": f"Run {w:g} km this week: {runs} run{'s' if runs > 1 else ''} of about {w / runs:.0f} km.", "today": f"Run about {w / runs:.0f} km", "minutes": max(30, round(w / runs * 6))}
    if kind == "cpd_hours" and w:
        return {"text": f"Log {w:g} h of CPD this week: a webinar, a course module or technical reading.", "today": "CPD: a webinar or reading", "minutes": 60}
    if kind == "journal_days":
        return {"text": f"Write in the journal {min(7, math.ceil(w or 4)):g} days this week, even a line.", "today": "A few lines in the journal", "minutes": 10}
    if kind == "tasks_done" and w:
        return {"text": f"Clear {math.ceil(w)} tasks this week: start with the quick ones.", "today": None, "minutes": 0}
    if kind == "chartered_ready":
        return {"text": "Spend an hour on the Chartered application this week: one competency's claim.", "today": "Chartered application: one claim", "minutes": 60}
    if kind == "lift":
        return {"text": f"Train {g.get('exercise') or 'the lift'} twice this week, adding a little weight when the reps are there.", "today": None, "minutes": 0}
    if kind == "count" and w:
        return {"text": f"{w:g} more {unit or 'of it'} this week to get back on pace.", "today": f"{g['title']}: a step", "minutes": 30}
    return None


async def overview(hub: Hub, today: date) -> dict[str, Any]:
    from app.goals import service as goals

    ov = await goals.overview(hub, today.year, today)
    out = []
    for g in ov["goals"]:
        p = project({**g, "year": ov["year"]}, today)
        out.append({"id": g["id"], "title": g["title"], "state": g["state"], "value": g["value"], "target": g.get("target"),
                    "unit": g.get("unit") or "", **p, "step": step(g, p)})
    return {"year": ov["year"], "through_year": ov["through_year"], "goals": out,
            "behind": [g for g in out if g["state"] == "behind"]}


async def step_for_today(hub: Hub, day: date) -> dict[str, Any] | None:
    """The most-behind goal's step, as a block for today's plan (None if nothing's behind or it doesn't fit a day)."""
    try:
        ov = await overview(hub, day)
    except Exception:  # noqa: BLE001 - goals unavailable: plan without one
        return None
    candidates = [g for g in ov["behind"] if g["step"] and g["step"].get("today")]
    if not candidates:
        return None
    g = min(candidates, key=lambda x: x.get("projected_percent") or 0)
    return {"goal": g["title"], "step": g["step"]["today"], "minutes": g["step"]["minutes"] or 30}


async def push_message(hub: Hub, local_now: datetime) -> list[dict[str, Any]]:
    """Monday 6pm, once a week: the goal that's slipping most, with this week's step."""
    from app.push import store

    key = f"goal-steer:{local_now.strftime('%G-W%V')}"
    if local_now.weekday() != 0 or local_now.hour != 18 or key in store.sent():
        return []
    ov = await overview(hub, local_now.date())
    slipping = [g for g in ov["behind"] if g["step"]]
    if not slipping:
        return []
    g = min(slipping, key=lambda x: x.get("projected_percent") or 0)
    pace = f"On pace for {g['projected']:,.0f} of {g['target']:,.0f}{(' ' + g['unit']) if g['unit'] else ''}. " if g.get("projected") is not None else ""
    return [{"key": key, "topic": "brief", "title": f"{g['title']}: a step this week", "body": pace + g["step"]["text"], "url": "/year", "urgency": "normal"}]
