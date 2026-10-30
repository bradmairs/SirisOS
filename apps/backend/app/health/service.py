"""The Health section (5.7): SirisOS's own health store (ingest.py, from
Health Auto Export) merged with SirisAI's health history, scored
(scores.py). The readiness score also goes in the morning brief and decides
how hard the training plan's day should be."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.health import ingest, scores
from app.hub import sirisai_api
from app.hub.service import Hub
from app.tasks import service as tasks


async def days(hub: Hub, n: int = 70) -> tuple[scores.Days, bool]:
    """Day -> metrics: SirisAI's history, with SirisOS's richer store on top. (days, sirisai answered)"""
    body = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": n})
    out: scores.Days = {}
    for d in (body or {}).get("days") or []:
        if d.get("date") and d.get("metrics"):
            out[str(d["date"])] = {k: float(v) for k, v in d["metrics"].items() if isinstance(v, (int, float))}
    first = (tasks.today() - timedelta(days=n)).isoformat()
    for d, m in ingest.load()["metrics"].items():
        if d >= first:
            out[d] = {**out.get(d, {}), **m}
    return out, body is not None


async def overview(hub: Hub, on: date | None = None) -> dict[str, Any]:
    on = on or tasks.today()
    data, sirisai = await days(hub)
    store = ingest.load()
    today = data.get(on.isoformat()) or {}
    workouts = [{"date": d, **w} for d in sorted(store["workouts"], reverse=True)[:21] for w in store["workouts"][d]]
    return {
        "today": on.isoformat(),
        "available": bool(data),
        "sources": {"sirisai": sirisai, "health_auto_export": bool(store["metrics"]), "days": len(data)},
        "readiness": scores.readiness(data, on),
        "sleep": scores.sleep(data, store["sleep"], on),
        "activity": {
            "steps": today.get("steps"), "active_energy_kcal": today.get("active_energy_kcal"),
            "exercise_minutes": today.get("exercise_minutes"), "stand_hours": today.get("stand_hours"),
            "load": scores.load(data, on),
            "exercise_series": scores.series(data, "exercise_minutes", on, 28),
            "steps_series": scores.series(data, "steps", on, 14),
            "workouts": workouts[:12],
        },
        "vitals": scores.vitals(data, on),
    }


async def readiness(hub: Hub, on: date | None = None) -> dict[str, Any] | None:
    on = on or tasks.today()
    data, _ = await days(hub, 40)
    return scores.readiness(data, on)
