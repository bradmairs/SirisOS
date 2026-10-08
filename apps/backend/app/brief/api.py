"""Daily brief API (ADR 108): the brief itself, whether it should open by
itself right now, and dismissing it for the day."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.auth import require_user
from app.brief import service
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/brief", tags=["brief"], dependencies=[Depends(require_user)])


@router.get("")
async def get_brief(
    fresh: bool = Query(False, description="Rebuild instead of serving the 10-minute cache."),
    hub: Hub = Depends(get_hub),
    user: str = Depends(require_user),
) -> dict[str, Any]:
    return await service.brief_service.build(hub, user, fresh=fresh)


@router.get("/status")
def get_status() -> dict[str, Any]:
    return service.status()


@router.post("/dismiss")
def dismiss() -> dict[str, Any]:
    return service.dismiss()
