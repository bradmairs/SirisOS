"""The Health section (5.7). See service.py and scores.py.

    GET /api/v1/health          readiness, sleep, activity and load, vitals
    GET /api/v1/health/today    just today's readiness (Home, the brief)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.health import service
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/health", tags=["health"], dependencies=[Depends(require_user)])


@router.get("")
async def get_health(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.overview(hub)


@router.get("/today")
async def get_today(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return {"readiness": await service.readiness(hub)}
