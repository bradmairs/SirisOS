"""Fitness card API (3.6).

    GET /api/v1/fitness        this week's runs (Monday on), exercise, steps and the goal
    PUT /api/v1/fitness/goal   {weekly_km}: set (or clear, with null) the weekly running goal
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_user
from app.fitness import service
from app.hub.service import Hub, get_hub

router = APIRouter(prefix="/api/v1/fitness", tags=["fitness"], dependencies=[Depends(require_user)])


class Goal(BaseModel):
    weekly_km: float | None = Field(default=None, gt=0, le=500)


@router.get("")
async def get_fitness(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.week(hub)


@router.put("/goal")
def put_goal(body: Goal) -> dict[str, Any]:
    return {"goal_km": service.set_goal(body.weekly_km)}
