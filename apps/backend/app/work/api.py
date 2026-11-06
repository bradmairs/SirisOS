"""Work (7.2). See service.py.

    GET  /api/v1/work          the working day: hours, work tasks, to-dos in work notes, this week (done, focus),
                               work apps, recent work notes, the engineering project, CPD
    POST /api/v1/work/focus    {minutes}: focus time from the timer (7.4)
    POST /api/v1/work/todo-done   a work-note to-do ticked on the Work page, for the week's chart
    POST /api/v1/work/cpd      {title, hours, category, date?, provider?}: log CPD
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.brief.service import zone
from app.work import service

router = APIRouter(prefix="/api/v1/work", tags=["work"], dependencies=[Depends(require_user)])


@router.get("")
async def work(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.dashboard(hub, datetime.now(zone()))


class Focus(BaseModel):
    minutes: int = Field(ge=1, le=240)


@router.post("/focus")
def focus(body: Focus) -> dict[str, Any]:
    return {"today": service.add_focus(datetime.now(zone()).date(), body.minutes)}


@router.post("/todo-done")
def todo_done() -> dict[str, Any]:
    service.add_todo_done(datetime.now(zone()).date())
    return {"ok": True}


class CpdLog(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    hours: float = Field(gt=0, le=200)
    category: Literal["area", "risk", "business", "other"] = "area"
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    provider: str = Field(default="", max_length=120)


@router.post("/cpd")
def log_cpd(body: CpdLog) -> dict[str, Any]:
    from datetime import date as date_type

    day = date_type.fromisoformat(body.date) if body.date else datetime.now(zone()).date()
    return {"record": service.log_cpd(body.title, body.hours, body.category, day, body.provider), "cpd": service._cpd(day)}
