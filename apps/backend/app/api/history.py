from __future__ import annotations

import json
import os
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from app.services.backup_analytics_service import backup_analytics_service
from app.services.time_series_history_service import history_service

router = APIRouter(prefix="/api/v1/history", tags=["history"])
AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")


class TimeSeriesObservationResponse(BaseModel):
    observed_at: str
    source: str
    metric: str
    dimensions: dict[str, str]
    numeric_value: float | None
    text_value: str | None


class TimeSeriesHistoryResponse(BaseModel):
    source: str
    metric: str
    hours: int
    observations: list[TimeSeriesObservationResponse]


class BackupTaskProtectionResponse(BaseModel):
    task_id: str
    task_name: str
    completions: int
    successes: int
    failures: int
    success_rate_percent: float | None
    last_finish_at: str | None
    last_result: str | None


class BackupProtectionResponse(BaseModel):
    days: int
    completions: int
    successes: int
    failures: int
    success_rate_percent: float | None
    last_finish_at: str | None
    last_failure_at: str | None
    protected: bool | None
    tasks: list[BackupTaskProtectionResponse]


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


@router.get("", response_model=TimeSeriesHistoryResponse)
async def time_series_history(
    source: Annotated[str, Query(min_length=1, max_length=96)],
    metric: Annotated[str, Query(min_length=1, max_length=128)],
    hours: Annotated[int, Query(ge=1, le=24 * 90)] = 24,
    limit: Annotated[int, Query(ge=1, le=5000)] = 720,
    dimensions: Annotated[str | None, Query(max_length=1000)] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> TimeSeriesHistoryResponse:
    _authenticate(authorization)
    parsed_dimensions: dict[str, object] | None = None
    if dimensions:
        try:
            decoded = json.loads(dimensions)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="dimensions must be valid JSON.") from exc
        if not isinstance(decoded, dict):
            raise HTTPException(status_code=400, detail="dimensions must be a JSON object.")
        parsed_dimensions = decoded

    observations = history_service.history(
        source=source,
        metric=metric,
        dimensions=parsed_dimensions,
        hours=hours,
        limit=limit,
    )
    return TimeSeriesHistoryResponse(
        source=source,
        metric=metric,
        hours=hours,
        observations=[
            TimeSeriesObservationResponse(
                observed_at=item.observed_at.isoformat(),
                source=item.source,
                metric=item.metric,
                dimensions=item.dimensions,
                numeric_value=item.numeric_value,
                text_value=item.text_value,
            )
            for item in observations
        ],
    )


@router.get("/backup-protection", response_model=BackupProtectionResponse)
async def backup_protection(
    days: Annotated[int, Query(ge=1, le=90)] = 30,
    authorization: Annotated[str | None, Header()] = None,
) -> BackupProtectionResponse:
    _authenticate(authorization)
    summary = backup_analytics_service.summary(days=days)
    return BackupProtectionResponse(
        days=summary.days,
        completions=summary.completions,
        successes=summary.successes,
        failures=summary.failures,
        success_rate_percent=summary.success_rate_percent,
        last_finish_at=summary.last_finish_at,
        last_failure_at=summary.last_failure_at,
        protected=summary.protected,
        tasks=[BackupTaskProtectionResponse(**item.__dict__) for item in summary.tasks],
    )
