from datetime import date, datetime
import os
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.gym import router as gym_router
from app.services.activity_service import ActivityService
from app.services.running_service import RunningService

router = APIRouter(prefix="/api/v1")
router.include_router(gym_router)
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


def to_response(record) -> RunResponse:
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
    )


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
    record = service.create_run(
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
    return to_response(record)
