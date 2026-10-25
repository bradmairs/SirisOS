"""Tasks API (2.9).

    GET    /api/v1/tasks                  the list, grouped: overdue, today, week, later, someday
    POST   /api/v1/tasks                  {title, due?, time?, repeat?, notes?} or {text: "remind me to…"}
    PATCH  /api/v1/tasks/{id}             change a SirisOS task
    DELETE /api/v1/tasks/{id}             remove a SirisOS task
    POST   /api/v1/tasks/{id}/done        tick it (in its note, for Siris tasks; cancels a reminder)
    POST   /api/v1/tasks/{id}/snooze      {until: "tomorrow" | "weekend" | "next-week" | YYYY-MM-DD}
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import require_user
from app.hub import sirisai_api
from app.hub.service import Hub, get_hub
from app.tasks import service, store

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"], dependencies=[Depends(require_user)])


class NewTask(BaseModel):
    text: str | None = Field(default=None, max_length=400, description="Free text like 'remind me to pay rego on Friday'.")
    title: str | None = Field(default=None, max_length=300)
    due: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    repeat: store.Repeat = "none"
    notes: str = Field(default="", max_length=2000)
    area: Literal["work", "personal"] | None = None


class Change(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    due: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    repeat: store.Repeat | None = None
    notes: str | None = Field(default=None, max_length=2000)
    area: Literal["work", "personal"] | None = None


class Snooze(BaseModel):
    until: str = Field(pattern=r"^(tomorrow|weekend|next-week|\d{4}-\d{2}-\d{2})$")


class Done(BaseModel):
    note: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=500)


@router.get("")
async def list_tasks(hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    return await service.collect(hub)


@router.post("")
def add_task(body: NewTask) -> dict[str, Any]:
    if body.text and body.text.strip():
        task = service.parse(body.text)
        task.area = body.area
    elif body.title and body.title.strip():
        task = store.Task(title=body.title.strip(), due=body.due, time=body.time, repeat=body.repeat, notes=body.notes, area=body.area)
    else:
        raise HTTPException(status_code=422, detail="Give the task a title.")
    if task.repeat != "none" and not task.due:
        task.due = service.today().isoformat()
    return service.add(task).model_dump()


@router.patch("/{task_id}")
def change_task(task_id: str, body: Change) -> dict[str, Any]:
    try:
        return service.update(task_id, body.model_dump(exclude_unset=True)).model_dump()
    except service.NotFound:
        raise HTTPException(status_code=404, detail="Only tasks added in SirisOS can be edited here.") from None


@router.delete("/{task_id}")
def delete_task(task_id: str) -> dict[str, Any]:
    try:
        service.delete(task_id)
    except service.NotFound:
        raise HTTPException(status_code=404, detail="No such task.") from None
    return {"removed": True}


@router.post("/{task_id}/done")
async def complete_task(task_id: str, body: Done | None = None, hub: Hub = Depends(get_hub)) -> dict[str, Any]:
    try:
        return await service.complete(hub, task_id, note=body.note if body else None, title=body.title if body else None)
    except service.NotFound:
        raise HTTPException(status_code=404, detail="No such task.") from None
    except sirisai_api.SirisAIError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None


@router.post("/{task_id}/snooze")
def snooze_task(task_id: str, body: Snooze) -> dict[str, Any]:
    try:
        return service.snooze(task_id, service.snooze_target(body.until))
    except service.NotFound:
        raise HTTPException(status_code=404, detail="No such task.") from None
