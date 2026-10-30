"""The setup checklist (5.6). See service.py.

    GET /api/v1/setup    every check, live: on, off or problem, with the fix
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.setup import service

router = APIRouter(prefix="/api/v1/setup", tags=["setup"], dependencies=[Depends(require_user)])


@router.get("")
async def get_checklist(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.checklist(hub)
