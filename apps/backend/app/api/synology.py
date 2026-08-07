from typing import Annotated
import os

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.synology_service import SynologyService

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


@router.get("", response_model=SynologySnapshotResponse)
async def synology_snapshot(
    authorization: Annotated[str | None, Header()] = None,
) -> SynologySnapshotResponse:
    _authenticate(authorization)
    snapshot = await service.snapshot()
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
