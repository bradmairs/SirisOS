"""Weekly review API (3.5).

    GET  /api/v1/review          this week's numbers, quiet projects, next week's crunch points, what's saved
    POST /api/v1/review          {focus}: what matters next week (saved to Siris)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.review import service
from app.tasks import service as tasks

router = APIRouter(prefix="/api/v1/review", tags=["review"], dependencies=[Depends(require_user)])


class Focus(BaseModel):
    focus: str = Field(default="", max_length=4000)


@router.get("")
async def get_review(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.overview(hub)


@router.post("")
async def save_review(body: Focus, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.save(hub, tasks.today(), body.focus)
