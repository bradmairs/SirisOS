from datetime import date, datetime
import os
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.activity import router as activity_router
from app.api.coach import router as coach_router
from app.api.gym import router as gym_router
from app.api.health import router as health_router
from app.api.intelligence import router as intelligence_router
from app.api.search import router as search_router
from app.api.training import router as training_router
from app.services.activity_service import ActivityService
from app.services.running_service import RunningService

router = APIRouter(prefix="/api/v1")
router.include_router(gym_router)
router.include_router(activity_router)
router.include_router(search_router)
router.include_router(intelligence_router)
router.include_router(health_router)
router.include_router(training_router)
router.include_router(coach_router)
service = RunningService()
service.initialise()
activity_service = ActivityService()
activity_service.initialise()

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")
JWT_ALGORITHM = "HS256"


def current_username(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            issuer="sirisos-api",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.") from exc
    username = payload.get("sub")
    if username != AUTH_USERNAME:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session user.")
    return AUTH_USERNAME


class RunCreateRequest(BaseModel):
    run_date: date
    run_type: Literal["outdoor", "treadmill"]
    distance_km: float = Field(gt=0, le=200)
    average_pace_seconds_per_km: int = Field(ge=120, le=1800)
    average_heart_rate: int = Field(ge=40, le=240)


class RunningPersonalRecordResponse(BaseModel):
    record_type: Literal["longest_run", "lowest_heart_rate_at_pace"]
    value: float
    previous_value: float | None
    run_date: date
    pace_seconds_per_km: int | None = None


class RunResponse(BaseModel):
    id: int
    run_date: date
    run_type: Literal["outdoor", "treadmill"]
    distance_km: float
    average_pace_seconds_per_km: int
    average_heart_rate: int
    effort_score: float
    fitness_score: float
    created_at: datetime
    new_records: list[RunningPersonalRecordResponse] = []


def to_response(record, new_records=()) -> RunResponse:
    return RunResponse(
        id=record.id,
        run_date=record.run_date,
        run_type=record.run_type,
        distance_km=record.distance_km,
        average_pace_seconds_per_km=record.average_pace_seconds_per_km,
        average_heart_rate=record.average_heart_rate,
        effort_score=record.effort_score,
        fitness_score=record.fitness_score,
        created_at=record.created_at,
        new_records=[RunningPersonalRecordResponse(**item.__dict__) for item in new_records],
    )


_RECORD_LABELS = {
    "longest_run": "longest run",
    "lowest_heart_rate_at_pace": "lowest heart rate at that pace",
}


def _record_message(record) -> str:
    label = _RECORD_LABELS[record.record_type]
    if record.record_type == "longest_run":
        if record.previous_value is None:
            return f"New {label}: {record.value:.2f} km."
        return f"New {label}: {record.value:.2f} km (previous {record.previous_value:.2f} km)."
    pace = _pace_label(record.pace_seconds_per_km) if record.pace_seconds_per_km else "that pace"
    if record.previous_value is None:
        return f"New {label} at {pace}: {record.value:.0f} bpm."
    return f"New {label} at {pace}: {record.value:.0f} bpm (previous {record.previous_value:.0f} bpm)."


def _pace_label(seconds_per_km: int) -> str:
    return f"{seconds_per_km // 60}:{seconds_per_km % 60:02d}/km"


@router.get("/running", response_model=list[RunResponse], tags=["running"])
async def list_runs(
    authorization: Annotated[str | None, Header()] = None,
) -> list[RunResponse]:
    current_username(authorization)
    return [to_response(item) for item in service.list_runs()]


@router.post("/running", response_model=RunResponse, status_code=status.HTTP_201_CREATED, tags=["running"])
async def create_run(
    payload: RunCreateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> RunResponse:
    username = current_username(authorization)
    record, new_records = service.create_run(
        run_date=payload.run_date,
        run_type=payload.run_type,
        distance_km=payload.distance_km,
        average_pace_seconds_per_km=payload.average_pace_seconds_per_km,
        average_heart_rate=payload.average_heart_rate,
    )
    activity_service.record(
        module="running",
        event_type="run_logged",
        title="Run logged",
        message=(
            f"{record.distance_km:.1f} km {record.run_type} run at "
            f"{_pace_label(record.average_pace_seconds_per_km)}. "
            f"Fitness score {record.fitness_score:.1f}."
        ),
        severity="success",
        user=username,
    )
    for personal_record in new_records:
        activity_service.record(
            module="running",
            event_type="personal_record",
            title="New running record",
            message=_record_message(personal_record),
            severity="success",
            user=username,
        )
    return to_response(record, new_records)
