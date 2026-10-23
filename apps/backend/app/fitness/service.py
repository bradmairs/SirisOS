"""The fitness card (3.6): this week's runs, exercise and steps from SirisAI's
health data (the iPhone Health shortcut), against a weekly running goal you
set on the card (fitness.json)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store
from app.tasks import service as tasks


def _path():
    return json_store.data_path("SIRISOS_FITNESS_PATH", "fitness.json")


def goal() -> float | None:
    value = json_store.read(_path(), {}).get("weekly_km")
    return float(value) if value else None


def set_goal(km: float | None) -> float | None:
    json_store.write(_path(), {"weekly_km": km})
    return km


async def week(hub: Hub) -> dict[str, Any]:
    today = tasks.today()
    monday = today - timedelta(days=today.weekday())
    body = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": 7})
    if body is None or body.get("days") is None:
        return {"available": False, "guest_mode": bool((body or {}).get("guest_mode")), "goal_km": goal()}
    by_day = {d["date"]: d.get("metrics") or {} for d in body["days"]}
    days = []
    for i in range(7):
        day = (monday + timedelta(days=i)).isoformat()
        m = by_day.get(day, {})
        days.append({"date": day, "km": m.get("running_km") or 0, "exercise": m.get("exercise_minutes") or 0, "future": day > today.isoformat()})
    steps = [m["steps"] for d, m in by_day.items() if m.get("steps") and d >= monday.isoformat()]
    km = round(sum(d["km"] for d in days), 1)
    return {
        "available": True,
        "guest_mode": False,
        "goal_km": goal(),
        "km": km,
        "runs": sum(1 for d in days if d["km"] > 0),
        "exercise_minutes": round(sum(d["exercise"] for d in days)),
        "steps_avg": round(sum(steps) / len(steps)) if steps else None,
        "days": days,
    }
