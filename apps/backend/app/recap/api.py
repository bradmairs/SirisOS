"""The month in short (10.2). See service.py.

    GET  /api/v1/recap?month=YYYY-MM   last month (or that month): money, health, work and habits, the text filed in Siris
    POST /api/v1/recap/{month}/seen    take it off Home
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_user
from app.brief.service import zone
from app.hub.service import Hub, get_hub
from app.recap import service

router = APIRouter(prefix="/api/v1/recap", tags=["recap"], dependencies=[Depends(require_user)])
_MONTH = re.compile(r"20\d\d-(0[1-9]|1[0-2])")


def _today() -> date:
    return datetime.now(zone()).date()


@router.get("")
async def get_recap(month: str | None = None, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    if month and not _MONTH.fullmatch(month):
        raise HTTPException(status_code=422, detail="Month as YYYY-MM.")
    return await service.view(hub, _today(), month)


@router.post("/{month}/seen")
def mark_seen(month: str) -> dict[str, Any]:
    if not _MONTH.fullmatch(month):
        raise HTTPException(status_code=422, detail="Month as YYYY-MM.")
    service.seen(month)
    return {"seen": True}
