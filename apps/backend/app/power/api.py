"""Power use (5.4). See service.py.

    GET /api/v1/power    SirisAI's power sensors and meters now, with today's kWh
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.power import service
from app.tasks import service as tasks

router = APIRouter(prefix="/api/v1/power", tags=["power"], dependencies=[Depends(require_user)])


@router.get("")
async def get_power(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    u = await service.usage(hub)
    today = tasks.today()
    day = service.load()["days"].get(today.isoformat()) or {}
    return {
        "available": u is not None,
        "configured": bool(u and u.get("configured")),
        "house_watts": (u or {}).get("house_watts"),
        "solar_watts": (u or {}).get("solar_watts"),
        "power": (u or {}).get("power") or [],
        "meters": (u or {}).get("meters") or [],
        "today_kwh": day.get("kwh"),
        "method": day.get("method"),
        "by_device": service.top_devices(day),
        "always_on": service.always_on(service.load()["days"], today, service.tariff()),
    }
