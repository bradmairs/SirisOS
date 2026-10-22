"""Evening wrap-up API (2.10).

    GET  /api/v1/wrapup                 today's done/open tasks, CPD-looking meetings, suggested top 3, what's saved
    POST /api/v1/wrapup                 {top3: [..3], journal}: save it (top 3 become tomorrow's tasks)
    POST /api/v1/wrapup/cpd/{key}       {title, hours}: log a meeting as CPD (a task to record it in EA tomorrow)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.tasks import service as tasks
from app.wrapup import service

router = APIRouter(prefix="/api/v1/wrapup", tags=["wrapup"], dependencies=[Depends(require_user)])


class WrapUp(BaseModel):
    top3: list[str] = Field(default_factory=list, max_length=3)
    journal: str = Field(default="", max_length=2000)


class LogCpd(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    hours: float = Field(gt=0, le=40)


@router.get("")
async def get_wrapup(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.overview(hub)


@router.post("")
async def save_wrapup(body: WrapUp, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.save(hub, tasks.today(), [t[:300] for t in body.top3], body.journal)


@router.post("/cpd/{key}")
def log_cpd(key: str, body: LogCpd) -> dict[str, Any]:
    return service.log_cpd(tasks.today(), key, body.title, body.hours)
