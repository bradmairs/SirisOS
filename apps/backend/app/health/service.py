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


async def workouts(hub: Hub, days: int = 42) -> list[dict[str, Any]]:
    body = await sirisai_api.get(hub, "/siris/hub/v1/health/workouts", params={"days": days})
    return list((body or {}).get("workouts") or [])


async def tool(hub: Hub, name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Run one of SirisAI's health tools (a quick log, a goal), confirmed by the tap that asked."""
    body = await sirisai_api.post(hub, f"/siris/tools/{name}/run", json={"arguments": arguments or {}, "confirmed": True})
    return ((body or {}).get("tool_call") or {}).get("result")
