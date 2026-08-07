from datetime import datetime
import os
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.storage_service import StorageService

router = APIRouter(prefix="/api/v1/homelab/storage", tags=["homelab"])

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
storage_service = StorageService()


class StorageVolumeResponse(BaseModel):
    mountpoint: str
    device: str
    filesystem: str
    size_bytes: int
    available_bytes: int
    used_bytes: int
    used_percent: float


class StorageSnapshotResponse(BaseModel):
    available: bool
    volumes: list[StorageVolumeResponse]
    total_bytes: int
    used_bytes: int
    available_bytes: int
    highest_used_percent: float | None
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


@router.get("", response_model=StorageSnapshotResponse)
async def storage_snapshot(
    authorization: Annotated[str | None, Header()] = None,
) -> StorageSnapshotResponse:
    _authenticate(authorization)
    snapshot = storage_service.snapshot()
    return StorageSnapshotResponse(
        available=snapshot.available,
        volumes=[StorageVolumeResponse(**volume.__dict__) for volume in snapshot.volumes],
        total_bytes=snapshot.total_bytes,
        used_bytes=snapshot.used_bytes,
        available_bytes=snapshot.available_bytes,
        highest_used_percent=snapshot.highest_used_percent,
        generated_at=datetime.now().astimezone().isoformat(),
        error=snapshot.error,
    )
