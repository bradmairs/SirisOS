from datetime import date
import os
from typing import Annotated

import jwt
from fastapi import APIRouter, Header, HTTPException, Query

from pydantic import BaseModel

from app.services.training_load_service import TrainingLoadService

router = APIRouter(prefix="/training", tags=["training"])
service = TrainingLoadService()

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


class WeeklyTrainingLoadResponse(BaseModel):
    week_start: date
    week_end: date
    running_load: float
    running_baseline: float | None
    running_ratio: float | None
    gym_load: float
    gym_baseline: float | None
    gym_ratio: float | None
    combined_index: float | None
    assessment: str


def _response(item) -> WeeklyTrainingLoadResponse:
    return WeeklyTrainingLoadResponse(**item.__dict__)


@router.get("/weekly-load", response_model=WeeklyTrainingLoadResponse)
async def weekly_load(authorization: Annotated[str | None, Header()] = None) -> WeeklyTrainingLoadResponse:
    _authenticate(authorization)
    return _response(service.weekly_load())


@router.get("/weekly-load/history", response_model=list[WeeklyTrainingLoadResponse])
async def weekly_load_history(
    weeks: Annotated[int, Query(ge=1, le=12)] = 8,
    authorization: Annotated[str | None, Header()] = None,
) -> list[WeeklyTrainingLoadResponse]:
    _authenticate(authorization)
    return [_response(item) for item in service.recent_weekly_loads(weeks=weeks)]
