"""Search API (ADR 109): one box for SirisOS and every app connected to it."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.search import service

router = APIRouter(prefix="/api/v1", tags=["search"], dependencies=[Depends(require_user)])


@router.get("/search")
async def search(q: str = Query("", max_length=200), hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.search(hub, q)
