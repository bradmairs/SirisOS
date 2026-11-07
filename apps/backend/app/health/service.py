"""The Health section: since 5.8 everything comes from SirisAI (3.51), which
keeps every Apple Health metric, workouts and sleep, and works out readiness,
sleep, load, vitals, the weight trend, the getting-sick warning, insights and
tonight's bedtime (GET /siris/hub/v1/health/overview). SirisOS only shows
them, so chat, voice and SirisOS always agree. The old local store moves
across on first use (migrate.py)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.health import migrate
from app.hub import sirisai_api
from app.hub.service import Hub
from app.tasks import service as tasks


def _empty(guest: bool = False, sirisai: bool = False) -> dict[str, Any]:
    return {"today": tasks.today().isoformat(), "available": False, "guest_mode": guest,
            "sources": {"sirisai": sirisai, "health_auto_export": False, "days": 0, "imports": {}},
            "readiness": None, "sleep": None, "activity": None, "vitals": [], "weight": None, "getting_sick": None,
            "logged": None, "insights": [], "bedtime": None, "migrating": migrate.pending()}


async def overview(hub: Hub, on: date | None = None) -> dict[str, Any]:
    await migrate.ensure(hub)
    body = await sirisai_api.get(hub, "/siris/hub/v1/health/overview")
    if body is None:
        return _empty()
    if body.get("guest_mode"):
        return _empty(guest=True, sirisai=True)
    imports = (body.get("sources") or {}).get("imports") or {}
    body["sources"] = {"sirisai": True, "health_auto_export": "health_auto_export" in imports,
                       "days": (body.get("sources") or {}).get("days", 0), "imports": imports}
    body["migrating"] = migrate.pending()
    return body


async def readiness(hub: Hub, on: date | None = None) -> dict[str, Any] | None:
    return (await overview(hub)).get("readiness")


async def today(hub: Hub) -> dict[str, Any]:
    """Readiness (kept from the morning) and the day's energy so far (5.9)."""
    body = await overview(hub)
    return {"readiness": body.get("readiness"), "energy": body.get("energy")}


async def workouts(hub: Hub, days: int = 42) -> list[dict[str, Any]]:
    body = await sirisai_api.get(hub, "/siris/hub/v1/health/workouts", params={"days": days})
    return list((body or {}).get("workouts") or [])


async def weights(hub: Hub, days: int = 400) -> list[dict[str, Any]] | None:
    """Every day with a weight (7.91), oldest first, straight from the daily records: a quick read, unlike the
    overview, which works out 70 days of scores (and so misses a weigh-in older than that). None when SirisAI
    can't be reached or guest mode is on."""
    body = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": days}, timeout=8.0)
    if body is None or body.get("guest_mode"):
        return None
    out, level = [], None
    for d in body.get("days") or []:
        kg = (d.get("metrics") or {}).get("weight_kg")
        if isinstance(kg, (int, float)) and kg > 0:
            level = float(kg) if level is None else level + 0.1 * (float(kg) - level)  # the same smoothing as SirisAI's trend
            out.append({"date": d.get("date"), "weight": round(float(kg), 2), "trend": round(level, 2)})
    return out


async def tool(hub: Hub, name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Run one of SirisAI's health tools (a quick log, a goal), confirmed by the tap that asked."""
    body = await sirisai_api.post(hub, f"/siris/tools/{name}/run", json={"arguments": arguments or {}, "confirmed": True})
    return ((body or {}).get("tool_call") or {}).get("result")
