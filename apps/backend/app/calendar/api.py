"""GET /api/v1/calendar?start=YYYY-MM-DD&end=YYYY-MM-DD (end exclusive, up to 62 days)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_user
from app.calendar import service
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"], dependencies=[Depends(require_user)])


@router.get("")
async def get_calendar(start: date = Query(), end: date = Query(), hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    if end <= start or (end - start).days > service.MAX_DAYS:
        raise HTTPException(status_code=422, detail=f"end must be after start, and at most {service.MAX_DAYS} days later.")
    return await service.events(hub, start, end)
