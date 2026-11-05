"""Work (7.2). See service.py.

    GET /api/v1/work    the working day: hours, meetings, work tasks, work projects and their to-dos,
                        the engineering project, CPD
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.brief.service import zone
from app.work import service

router = APIRouter(prefix="/api/v1/work", tags=["work"], dependencies=[Depends(require_user)])


@router.get("")
async def work(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.dashboard(hub, datetime.now(zone()))
