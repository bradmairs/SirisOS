"""GET /api/v1/week?start=YYYY-MM-DD: the week (Monday to Sunday) holding that date; this week by default."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.week import service

router = APIRouter(prefix="/api/v1/week", tags=["week"], dependencies=[Depends(require_user)])


@router.get("")
async def get_week(start: date | None = Query(None), hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.week(hub, start or date.today())
