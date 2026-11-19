"""Work (7.2). See service.py.

    GET  /api/v1/work          the working day: hours, work tasks, to-dos in work notes, this week (done, focus),
                               work apps, recent work notes, the engineering project, CPD
    POST /api/v1/work/focus    {minutes}: focus time from the timer (7.4)
    POST /api/v1/work/todo-done   a work-note to-do ticked on the Work page, for the week's chart
    POST /api/v1/work/cpd      {title, hours, category, date?, provider?}: log CPD
    POST /api/v1/work/wrapup   {done, carry[], first, note, cpd?}: the end-of-work wrap-up (7.5)
    GET  /api/v1/work/timesheet?on=YYYY-MM-DD   the week's timesheet notes (9.8); POST {what, hours?, date?, code?};
         PATCH/DELETE /api/v1/work/timesheet/{id}
    PUT  /api/v1/work/settings {focus_min?, break_min?, apps? (link ids, or null for automatic), calculators?, career?} (8.21)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub.service import Hub, get_hub
from app.brief.service import zone
from app.work import service, timesheet

router = APIRouter(prefix="/api/v1/work", tags=["work"], dependencies=[Depends(require_user)])


@router.get("")
async def work(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.dashboard(hub, datetime.now(zone()))


class Focus(BaseModel):
    minutes: int = Field(ge=1, le=240)
    label: str | None = Field(default=None, max_length=200)  # 9.9: what it was for: onto the timesheet notes
    code: str | None = Field(default=None, max_length=40)


class WorkSettings(BaseModel):
    focus_min: int | None = Field(default=None, ge=5, le=180)
    break_min: int | None = Field(default=None, ge=1, le=60)
    apps: list[str] | None = Field(default=None, max_length=24)
    calculators: bool | None = None
    career: bool | None = None


@router.put("/settings")
def put_settings(body: WorkSettings) -> dict[str, Any]:
    changes = body.model_dump(exclude_unset=True)
    return service.save_settings({k: v for k, v in changes.items() if v is not None or k == "apps"})


@router.post("/focus")
def focus(body: Focus) -> dict[str, Any]:
    day = datetime.now(zone()).date()
    out: dict[str, Any] = {"today": service.add_focus(day, body.minutes)}
    if body.label and body.label.strip():
        out["timesheet"] = timesheet.add_time(body.label.strip(), body.minutes / 60, day, body.code or "")
    return out


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


class WrapCpd(BaseModel):
    title: str = Field(default="", max_length=200)
    hours: float = Field(default=0, ge=0, le=24)
    category: Literal["area", "risk", "business", "other"] = "area"


class WorkWrapUp(BaseModel):
    done: str = Field(default="", max_length=2000)
    carry: list[str] = Field(default_factory=list, max_length=30)
    first: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=2000)
    cpd: WrapCpd | None = None


@router.post("/wrapup")
async def wrap_up(body: WorkWrapUp, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    day = datetime.now(zone()).date()
    return await service.wrapup(hub, day, body.done, body.carry, body.first, body.note, body.cpd.model_dump() if body.cpd else None)


# -- Timesheet notes (9.8) -----------------------------------------------------------------------

class TimesheetIn(BaseModel):
    what: str = Field(min_length=1, max_length=200)
    hours: float | None = Field(default=None, gt=0, le=24)
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    code: str = Field(default="", max_length=40)


class TimesheetChange(BaseModel):
    what: str | None = Field(default=None, min_length=1, max_length=200)
    hours: float | None = Field(default=None, gt=0, le=24)
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    code: str | None = Field(default=None, max_length=40)


def _today():
    return datetime.now(zone()).date()


@router.get("/timesheet")
def get_timesheet(on: str | None = None) -> dict[str, Any]:
    from datetime import date as _date

    day = _date.fromisoformat(on) if on else _today()
    return {**timesheet.week(day), "recent_codes": timesheet.codes(), "today": _today().isoformat()}


@router.post("/timesheet")
def add_timesheet(body: TimesheetIn) -> dict[str, Any]:
    from datetime import date as _date

    day = _date.fromisoformat(body.date) if body.date else _today()
    try:
        entry = timesheet.add(body.what, body.hours, day, body.code)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return {"entry": entry, **timesheet.week(day)}


@router.patch("/timesheet/{entry_id}")
def change_timesheet(entry_id: str, body: TimesheetChange) -> dict[str, Any]:
    try:
        entry = timesheet.change(entry_id, **body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if entry is None:
        raise HTTPException(status_code=404, detail="No such entry.")
    from datetime import date as _date

    return {"entry": entry, **timesheet.week(_date.fromisoformat(entry["date"]))}


@router.delete("/timesheet/{entry_id}")
def delete_timesheet(entry_id: str) -> dict[str, Any]:
    if not timesheet.remove(entry_id):
        raise HTTPException(status_code=404, detail="No such entry.")
    return {"deleted": entry_id}
