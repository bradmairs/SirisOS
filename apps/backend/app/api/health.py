import os
import secrets
from datetime import datetime
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel

from app.services.health_ingest_service import HealthIngestService
from app.services.health_mcp_service import HealthMcpService

router = APIRouter(prefix="/health", tags=["health"])
service = HealthMcpService()
ingest_service = HealthIngestService()
ingest_service.initialise()

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
HEALTH_INGEST_TOKEN = os.getenv("SIRISOS_HEALTH_INGEST_TOKEN", "").strip()


class HealthMetricResponse(BaseModel):
    name: str
    value: float | str | None
    unit: str | None
    date: str | None


class HealthSnapshotResponse(BaseModel):
    available: bool
    endpoint_configured: bool
    tools: list[str]
    metrics: list[HealthMetricResponse]
    error: str | None = None


class HealthIngestResponse(BaseModel):
    accepted: bool
    metric_samples_received: int
    workouts_received: int
    error: str | None = None


class HealthIngestStatusResponse(BaseModel):
    configured: bool
    last_sync: datetime | None
    records_received: int
    last_error: str | None = None


def _authenticate_ingest(authorization: Annotated[str | None, Header()] = None) -> None:
    if not HEALTH_INGEST_TOKEN:
        raise HTTPException(status_code=401, detail="Health ingest token is not configured.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, HEALTH_INGEST_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid ingest token.")


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


@router.get("/snapshot", response_model=HealthSnapshotResponse)
async def health_snapshot(
    authorization: Annotated[str | None, Header()] = None,
) -> HealthSnapshotResponse:
    _authenticate(authorization)
    snapshot = service.snapshot()
    return HealthSnapshotResponse(
        available=snapshot.available,
        endpoint_configured=snapshot.endpoint_configured,
        tools=snapshot.tools,
        metrics=[HealthMetricResponse(**item.__dict__) for item in snapshot.metrics],
        error=snapshot.error,
    )


@router.post("/ingest", response_model=HealthIngestResponse, status_code=202)
async def ingest_health_data(
    payload: Annotated[dict[str, Any], Body()],
    authorization: Annotated[str | None, Header()] = None,
    automation_id: Annotated[str | None, Header(alias="automation-id")] = None,
    automation_name: Annotated[str | None, Header(alias="automation-name")] = None,
    session_id: Annotated[str | None, Header(alias="session-id")] = None,
) -> HealthIngestResponse:
    """Unattended push target for Health Auto Export's REST API automations."""
    _authenticate_ingest(authorization)
    result = ingest_service.ingest(
        payload,
        automation_id=automation_id,
        automation_name=automation_name,
        session_id=session_id,
    )
    return HealthIngestResponse(
        accepted=result.accepted,
        metric_samples_received=result.metric_samples_received,
        workouts_received=result.workouts_received,
        error=result.error,
    )


@router.get("/status", response_model=HealthIngestStatusResponse)
async def health_ingest_status(
    authorization: Annotated[str | None, Header()] = None,
) -> HealthIngestStatusResponse:
    _authenticate(authorization)
    status = ingest_service.status()
    return HealthIngestStatusResponse(
        configured=bool(HEALTH_INGEST_TOKEN),
        last_sync=status.last_sync,
        records_received=status.records_received,
        last_error=status.last_error,
    )
