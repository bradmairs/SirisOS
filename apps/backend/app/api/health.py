import logging
import os
import secrets
from datetime import date, datetime
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Body, Header, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger("sirisos.health_ingest_auth")

from app.services.gym_service import GymService
from app.services.health_ingest_service import HealthIngestService
from app.services.health_workout_match_service import HealthWorkoutMatchService
from app.services.running_service import RunningService

router = APIRouter(prefix="/health", tags=["health"])
ingest_service = HealthIngestService()
ingest_service.initialise()
_workout_match_gym_service = GymService()
_workout_match_gym_service.initialise()
_workout_match_running_service = RunningService()
_workout_match_running_service.initialise()
workout_match_service = HealthWorkoutMatchService(
    health_service=ingest_service,
    gym_service=_workout_match_gym_service,
    running_service=_workout_match_running_service,
)

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


class HealthMetricSummaryResponse(BaseModel):
    metric_type: str
    unit: str | None
    latest_value: float
    latest_timestamp: datetime
    baseline_average: float | None
    baseline_ratio: float | None
    baseline_sample_count: int


class DailyMetricPointResponse(BaseModel):
    day: date
    value: float
    unit: str | None
    sample_count: int


class UnloggedHealthWorkoutResponse(BaseModel):
    external_id: str
    workout_type: str
    category: str
    start_date: date
    duration_seconds: float | None
    distance_m: float | None


def _authenticate_ingest(authorization: Annotated[str | None, Header()] = None) -> None:
    """Accepts either the unattended ingest token (for automations that can't log
    in, e.g. a Shortcuts push) or a normal SirisOS session JWT (the native app's
    HealthKit sync, which is already logged in and shouldn't need a second secret)."""
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning(
            "ingest auth rejected: missing/malformed header (present=%s, prefix_ok=%s)",
            authorization is not None,
            bool(authorization and authorization.startswith("Bearer ")),
        )
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = authorization.removeprefix("Bearer ").strip()
    if HEALTH_INGEST_TOKEN and secrets.compare_digest(token, HEALTH_INGEST_TOKEN):
        return
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], issuer="sirisos-api")
    except jwt.PyJWTError as exc:
        logger.warning("ingest auth rejected: jwt decode failed: %r (token_len=%d)", exc, len(token))
        raise HTTPException(status_code=401, detail="Invalid ingest credentials.") from None
    if payload.get("sub") != AUTH_USERNAME:
        logger.warning("ingest auth rejected: sub=%r != AUTH_USERNAME=%r", payload.get("sub"), AUTH_USERNAME)
        raise HTTPException(status_code=401, detail="Invalid session user.")


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
    snapshot = ingest_service.snapshot()
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


@router.get("/summary", response_model=list[HealthMetricSummaryResponse])
async def health_summary(
    baseline_days: Annotated[int, Query(ge=1, le=90)] = 14,
    authorization: Annotated[str | None, Header()] = None,
) -> list[HealthMetricSummaryResponse]:
    _authenticate(authorization)
    return [
        HealthMetricSummaryResponse(**item.__dict__)
        for item in ingest_service.summary(baseline_days=baseline_days)
    ]


@router.get("/metrics/{metric_type}/history", response_model=list[DailyMetricPointResponse])
async def health_metric_history(
    metric_type: str,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    authorization: Annotated[str | None, Header()] = None,
) -> list[DailyMetricPointResponse]:
    _authenticate(authorization)
    return [
        DailyMetricPointResponse(**item.__dict__)
        for item in ingest_service.daily_history(metric_type, days=days)
    ]


@router.get("/unlogged-workouts", response_model=list[UnloggedHealthWorkoutResponse])
async def unlogged_workouts(
    days: Annotated[int, Query(ge=1, le=90)] = 30,
    authorization: Annotated[str | None, Header()] = None,
) -> list[UnloggedHealthWorkoutResponse]:
    _authenticate(authorization)
    return [
        UnloggedHealthWorkoutResponse(**item.__dict__)
        for item in workout_match_service.list_unlogged_workouts(lookback_days=days)
    ]
