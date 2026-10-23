"""The year at a glance (4.1).

    GET /api/v1/trends    the last 12 months, month by month (see service.py)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.trends import service

router = APIRouter(prefix="/api/v1/trends", tags=["trends"], dependencies=[Depends(require_user)])


@router.get("")
async def get_trends(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.year(hub)
