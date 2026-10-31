"""Home maintenance (5.2). See service.py.

    GET    /api/v1/maintenance                      jobs (with due state), appliances, summary
    POST   /api/v1/maintenance/jobs                 {title, room, every_days?, last_done?, appliance?, notes?, usage_entity?, usage_unit?, usage_every?}
    PATCH  /api/v1/maintenance/jobs/{id}            any of those
    POST   /api/v1/maintenance/jobs/{id}/done       {on?: YYYY-MM-DD}  (default today)
    POST   /api/v1/maintenance/jobs/{id}/snooze     a week on
    DELETE /api/v1/maintenance/jobs/{id}
    POST   /api/v1/maintenance/appliances           {name, room, device?, make?, model?, bought_on?, warranty_until?, manual_url?, notes?}
    PATCH  /api/v1/maintenance/appliances/{id}
    DELETE /api/v1/maintenance/appliances/{id}
    POST   /api/v1/maintenance/appliances/{id}/manual   upload (PDF or photo)
    GET    /api/v1/maintenance/appliances/{id}/manual
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from app.auth import require_user
from app.maintenance import service
from app.tasks import service as tasks

router = APIRouter(prefix="/api/v1/maintenance", tags=["maintenance"], dependencies=[Depends(require_user)])

DateStr = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class Usage(BaseModel):
    """Due by use (6.2): a Home Assistant meter (kWh) or power sensor (hours running)."""
    usage_entity: str | None = Field(default=None, max_length=120, pattern=r"^(sensor\.[a-z0-9_]+)?$")
    usage_unit: Literal["h", "kWh"] | None = None
    usage_every: float | None = Field(default=None, gt=0, le=1_000_000)


class NewJob(Usage):
    title: str = Field(min_length=1, max_length=160)
    room: str = Field(min_length=1, max_length=40)
    every_days: int | None = Field(default=None, ge=1, le=3650)
    last_done: str | None = DateStr
    appliance: str | None = Field(default=None, max_length=40)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _some_schedule(self) -> "NewJob":
        if not self.every_days and not (self.usage_entity and self.usage_unit and self.usage_every):
            raise ValueError("Say how often: every so many days, or by use (an entity, a unit and an amount).")
        return self


class JobChange(Usage):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    room: str | None = Field(default=None, min_length=1, max_length=40)
    every_days: int | None = Field(default=None, ge=1, le=3650)
    last_done: str | None = DateStr
    appliance: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)


class Done(BaseModel):
    on: str | None = DateStr


class NewAppliance(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    room: str = Field(min_length=1, max_length=40)
    device: str | None = Field(default=None, max_length=80)
    make: str = Field(default="", max_length=80)
    model: str = Field(default="", max_length=80)
    bought_on: str | None = DateStr
    warranty_until: str | None = DateStr
    manual_url: str = Field(default="", max_length=1000, pattern=r"^(https?://.*)?$")
    notes: str = Field(default="", max_length=2000)


class ApplianceChange(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    room: str | None = Field(default=None, min_length=1, max_length=40)
    device: str | None = Field(default=None, max_length=80)
    make: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    bought_on: str | None = DateStr
    warranty_until: str | None = DateStr
    manual_url: str | None = Field(default=None, max_length=1000, pattern=r"^(https?://.*)?$")
    notes: str | None = Field(default=None, max_length=2000)


def _today() -> date:
    return tasks.today()


def _view() -> dict[str, Any]:
    return service.overview(_today())


def _missing(kind: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"No such {kind}.")


@router.get("")
def get_all() -> dict[str, Any]:
    return _view()


@router.post("/jobs")
def add_job(body: NewJob) -> dict[str, Any]:
    doc = service.load()
    doc.jobs.append(service.Job.model_validate(body.model_dump()))
    service.save(doc)
    return _view()


@router.patch("/jobs/{job_id}")
def change_job(job_id: str, body: JobChange) -> dict[str, Any]:
    doc = service.load()
    try:
        job = service.find_job(doc, job_id)
    except LookupError:
        raise _missing("job") from None
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(job, k, v)
    if {"usage_entity", "usage_unit"} & body.model_fields_set:
        job.usage_now = job.usage_at_done = job.usage_sampled_at = None  # count afresh from the next sample
    if "last_done" in body.model_fields_set:
        job.snoozed_until = None
    service.save(doc)
    return _view()


@router.post("/jobs/{job_id}/done")
def job_done(job_id: str, body: Done | None = None) -> dict[str, Any]:
    on = date.fromisoformat(body.on) if body and body.on else _today()
    try:
        service.done(job_id, on)
    except LookupError:
        raise _missing("job") from None
    return _view()


@router.post("/jobs/{job_id}/snooze")
def job_snooze(job_id: str) -> dict[str, Any]:
    try:
        service.snooze(job_id, _today())
    except LookupError:
        raise _missing("job") from None
    return _view()


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str) -> dict[str, Any]:
    doc = service.load()
    if not any(j.id == job_id for j in doc.jobs):
        raise _missing("job")
    doc.jobs = [j for j in doc.jobs if j.id != job_id]
    service.save(doc)
    return _view()


@router.post("/appliances")
def add_appliance(body: NewAppliance) -> dict[str, Any]:
    doc = service.load()
    doc.appliances.append(service.Appliance.model_validate(body.model_dump()))
    service.save(doc)
    return _view()


@router.patch("/appliances/{appliance_id}")
def change_appliance(appliance_id: str, body: ApplianceChange) -> dict[str, Any]:
    doc = service.load()
    try:
        a = service.find_appliance(doc, appliance_id)
    except LookupError:
        raise _missing("appliance") from None
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    service.save(doc)
    return _view()


@router.delete("/appliances/{appliance_id}")
def delete_appliance(appliance_id: str) -> dict[str, Any]:
    try:
        service.remove_appliance(appliance_id)
    except LookupError:
        raise _missing("appliance") from None
    return _view()


@router.post("/appliances/{appliance_id}/manual")
async def upload_manual(appliance_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read(service.MAX_MANUAL_BYTES + 1)
    try:
        service.save_manual(appliance_id, file.filename or "manual.pdf", raw)
    except LookupError:
        raise _missing("appliance") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return _view()


@router.get("/appliances/{appliance_id}/manual")
def get_manual(appliance_id: str) -> FileResponse:
    try:
        a = service.find_appliance(service.load(), appliance_id)
    except LookupError:
        raise _missing("appliance") from None
    path = service.manuals_dir() / a.manual.stored if a.manual else None
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="No manual uploaded.")
    return FileResponse(path, filename=a.manual.filename)
