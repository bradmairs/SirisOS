from typing import Annotated
import os

import jwt
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel

from app.services.synology_service import SynologyService
from app.services.time_series_history_service import history_service

router = APIRouter(prefix="/api/v1/homelab/synology", tags=["homelab"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
service = SynologyService()


class SynologyVolumeResponse(BaseModel):
    name: str
    path: str
    status: str
    size_bytes: int | None
    used_bytes: int | None
    used_percent: float | None


class SynologyDiskResponse(BaseModel):
    name: str
    model: str | None
    status: str
    temperature_c: float | None


class HyperBackupTaskResponse(BaseModel):
    task_id: str
    name: str
    state: str
    last_result: str | None
    last_finish_at: str | None
    next_run_at: str | None
    destination: str | None
    running: bool
    failed: bool


class SynologySnapshotResponse(BaseModel):
    configured: bool
    available: bool
    model: str | None
    dsm_version: str | None
    volumes: list[SynologyVolumeResponse]
    disks: list[SynologyDiskResponse]
    unhealthy_volumes: int
    unhealthy_disks: int
    highest_used_percent: float | None
    backup_api_available: bool
    backup_tasks: list[HyperBackupTaskResponse]
    running_backup_tasks: int
    failed_backup_tasks: int
    latest_backup_finish_at: str | None
    generated_at: str
    error: str | None = None


def _authenticate(authorization: Annotated[str | None, Header()] = None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            JWT_SECRET,
            algorithms=["HS256"],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc
    if payload.get("sub") != AUTH_USERNAME:
        raise HTTPException(status_code=401, detail="Invalid session user.")


def _record_synology_history(snapshot: object) -> None:
    if not getattr(snapshot, "available", False):
        return
    history_service.record_if_due(
        source="synology",
        metric="highest_used_percent",
        numeric_value=getattr(snapshot, "highest_used_percent", None),
        minimum_interval_seconds=300,
    )
    history_service.record_if_due(
        source="synology",
        metric="failed_backup_tasks",
        numeric_value=getattr(snapshot, "failed_backup_tasks", 0),
        minimum_interval_seconds=300,
    )
    history_service.record_if_due(
        source="synology",
        metric="running_backup_tasks",
        numeric_value=getattr(snapshot, "running_backup_tasks", 0),
        minimum_interval_seconds=300,
    )
    for volume in getattr(snapshot, "volumes", []):
        history_service.record_if_due(
            source="synology",
            metric="volume_used_percent",
            numeric_value=volume.used_percent,
            text_value=volume.status,
            dimensions={"volume": volume.name, "path": volume.path},
            minimum_interval_seconds=300,
        )
    for task in getattr(snapshot, "backup_tasks", []):
        dimensions = {"task_id": task.task_id, "task": task.name}
        history_service.record_if_due(
            source="synology_backup",
            metric="failed",
            numeric_value=1 if task.failed else 0,
            text_value=task.last_result or task.state,
            dimensions=dimensions,
            minimum_interval_seconds=300,
        )
        history_service.record_if_due(
            source="synology_backup",
            metric="running",
            numeric_value=1 if task.running else 0,
            text_value=task.state,
            dimensions=dimensions,
            minimum_interval_seconds=300,
        )


@router.get("", response_model=SynologySnapshotResponse)
async def synology_snapshot(
    background_tasks: BackgroundTasks,
    authorization: Annotated[str | None, Header()] = None,
) -> SynologySnapshotResponse:
    _authenticate(authorization)
    snapshot = await service.snapshot()
    background_tasks.add_task(_record_synology_history, snapshot)
    return SynologySnapshotResponse(
        configured=snapshot.configured,
        available=snapshot.available,
        model=snapshot.model,
        dsm_version=snapshot.dsm_version,
        volumes=[SynologyVolumeResponse(**item.__dict__) for item in snapshot.volumes],
        disks=[SynologyDiskResponse(**item.__dict__) for item in snapshot.disks],
        unhealthy_volumes=snapshot.unhealthy_volumes,
        unhealthy_disks=snapshot.unhealthy_disks,
        highest_used_percent=snapshot.highest_used_percent,
        backup_api_available=snapshot.backup_api_available,
        backup_tasks=[HyperBackupTaskResponse(**item.__dict__) for item in snapshot.backup_tasks],
        running_backup_tasks=snapshot.running_backup_tasks,
        failed_backup_tasks=snapshot.failed_backup_tasks,
        latest_backup_finish_at=snapshot.latest_backup_finish_at,
        generated_at=snapshot.generated_at,
        error=snapshot.error,
    )
