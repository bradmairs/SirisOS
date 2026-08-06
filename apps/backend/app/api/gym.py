from datetime import date, datetime
import os
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.services.activity_service import ActivityService
from app.services.gym_service import GymService

router = APIRouter(prefix="/gym", tags=["gym"])
service = GymService()
service.initialise()
activity_service = ActivityService()
activity_service.initialise()

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")


def _authenticate(authorization: Annotated[str | None, Header()] = None) -> str:
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
    return AUTH_USERNAME


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


class ExerciseHistoryPointResponse(BaseModel):
    workout_date: date
    workout_name: str
    weight_kg: float
    reps: int
    rir: int | None
    volume_kg: float
    estimated_one_rep_max_kg: float


class ExerciseSummaryResponse(BaseModel):
    exercise: str
    set_count: int
    workout_count: int
    latest_date: date
    latest_weight_kg: float
    latest_reps: int
    best_weight_kg: float
    best_estimated_one_rep_max_kg: float
    best_set_volume_kg: float
    history: list[ExerciseHistoryPointResponse]


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


def _exercise_response(item) -> ExerciseSummaryResponse:
    return ExerciseSummaryResponse(
        exercise=item.exercise,
        set_count=item.set_count,
        workout_count=item.workout_count,
        latest_date=item.latest_date,
        latest_weight_kg=item.latest_weight_kg,
        latest_reps=item.latest_reps,
        best_weight_kg=item.best_weight_kg,
        best_estimated_one_rep_max_kg=item.best_estimated_one_rep_max_kg,
        best_set_volume_kg=item.best_set_volume_kg,
        history=[ExerciseHistoryPointResponse(**point.__dict__) for point in item.history],
    )


@router.get("/workouts", response_model=list[WorkoutResponse])
async def list_workouts(authorization: Annotated[str | None, Header()] = None) -> list[WorkoutResponse]:
    _authenticate(authorization)
    return [_response(item) for item in service.list_workouts()]


@router.post("/workouts", response_model=WorkoutResponse, status_code=status.HTTP_201_CREATED)
async def create_workout(payload: WorkoutCreate, authorization: Annotated[str | None, Header()] = None) -> WorkoutResponse:
    username = _authenticate(authorization)
    workout = service.create_workout(
        workout_date=payload.workout_date,
        name=payload.name,
        notes=payload.notes,
        sets=[item.model_dump() for item in payload.sets],
    )
    activity_service.record(
        module="gym",
        event_type="workout_logged",
        title="Workout logged",
        message=(
            f"{workout.name}: {len(workout.sets)} sets and "
            f"{workout.total_volume_kg:,.0f} kg total volume."
        ),
        severity="success",
        user=username,
    )
    return _response(workout)


@router.get("/exercises", response_model=list[ExerciseSummaryResponse])
async def list_exercises(authorization: Annotated[str | None, Header()] = None) -> list[ExerciseSummaryResponse]:
    _authenticate(authorization)
    return [_exercise_response(item) for item in service.list_exercises()]


@router.get("/exercises/{exercise_name}", response_model=ExerciseSummaryResponse)
async def exercise_detail(exercise_name: str, authorization: Annotated[str | None, Header()] = None) -> ExerciseSummaryResponse:
    _authenticate(authorization)
    item = service.get_exercise(exercise_name)
    if item is None:
        raise HTTPException(status_code=404, detail="Exercise not found.")
    return _exercise_response(item)
