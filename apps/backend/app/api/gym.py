from datetime import date, datetime
import os
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.services.gym_service import GymService

router = APIRouter(prefix="/api/v1/gym", tags=["gym"])
service = GymService()
service.initialise()

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")


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


class WorkoutSetCreate(BaseModel):
    exercise: str = Field(min_length=1, max_length=120)
    weight_kg: float = Field(ge=0, le=1000)
    reps: int = Field(ge=1, le=500)
    rir: int | None = Field(default=None, ge=0, le=10)


class WorkoutCreate(BaseModel):
    workout_date: date
    name: str = Field(min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)
    sets: list[WorkoutSetCreate] = Field(min_length=1, max_length=100)


class WorkoutSetResponse(BaseModel):
    id: int
    exercise: str
    weight_kg: float
    reps: int
    rir: int | None
    volume_kg: float


class WorkoutResponse(BaseModel):
    id: int
    workout_date: date
    name: str
    notes: str | None
    total_volume_kg: float
    set_count: int
    created_at: datetime
    sets: list[WorkoutSetResponse]


def _response(workout) -> WorkoutResponse:
    return WorkoutResponse(
        id=workout.id,
        workout_date=workout.workout_date,
        name=workout.name,
        notes=workout.notes,
        total_volume_kg=workout.total_volume_kg,
        set_count=len(workout.sets),
        created_at=workout.created_at,
        sets=[
            WorkoutSetResponse(
                id=item.id,
                exercise=item.exercise,
                weight_kg=item.weight_kg,
                reps=item.reps,
                rir=item.rir,
                volume_kg=item.volume_kg,
            )
            for item in workout.sets
        ],
    )


@router.get("/workouts", response_model=list[WorkoutResponse])
async def list_workouts(authorization: Annotated[str | None, Header()] = None) -> list[WorkoutResponse]:
    _authenticate(authorization)
    return [_response(item) for item in service.list_workouts()]


@router.post("/workouts", response_model=WorkoutResponse, status_code=status.HTTP_201_CREATED)
async def create_workout(payload: WorkoutCreate, authorization: Annotated[str | None, Header()] = None) -> WorkoutResponse:
    _authenticate(authorization)
    workout = service.create_workout(
        workout_date=payload.workout_date,
        name=payload.name,
        notes=payload.notes,
        sets=[item.model_dump() for item in payload.sets],
    )
    return _response(workout)
