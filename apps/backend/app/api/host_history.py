import os
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel

from app.services.host_history_service import HostHistoryService
from app.services.host_metrics_service import HostMetricsCollector

router = APIRouter(prefix="/api/v1/homelab/host", tags=["homelab"])
history_service = HostHistoryService()
history_service.initialise()
collector = HostMetricsCollector()

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
JWT_ALGORITHM = "HS256"


class HostHistorySampleResponse(BaseModel):
    sampled_at: str
    hostname: str | None
    cpu_percent: float | None
    memory_percent: float | None
    disk_percent: float | None
    load_1m: float | None


def _authenticate(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        ) from exc
    if payload.get("sub") != AUTH_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session user.",
        )
    return AUTH_USERNAME


@router.get("/history", response_model=list[HostHistorySampleResponse])
async def host_history(
    authorization: Annotated[str | None, Header()] = None,
    hours: int = Query(default=24, ge=1, le=720),
) -> list[HostHistorySampleResponse]:
    _authenticate(authorization)

    metrics = collector.collect()
    if metrics.available:
        history_service.record_if_due(
            hostname=metrics.hostname,
            cpu_percent=metrics.cpu_percent,
            memory_percent=metrics.memory_percent,
            disk_percent=metrics.disk_percent,
            load_1m=metrics.load_1m,
        )

    return [
        HostHistorySampleResponse(
            sampled_at=item.sampled_at.isoformat(),
            hostname=item.hostname,
            cpu_percent=item.cpu_percent,
            memory_percent=item.memory_percent,
            disk_percent=item.disk_percent,
            load_1m=item.load_1m,
        )
        for item in history_service.history(hours=hours)
    ]
