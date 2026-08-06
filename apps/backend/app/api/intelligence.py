from datetime import date
import os
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.gym_service import GymService
from app.services.rules_engine import RulesEngine
from app.services.running_service import RunningService

router = APIRouter(prefix="/intelligence", tags=["intelligence"])
rules_engine = RulesEngine()
running_service = RunningService()
gym_service = GymService()
running_service.initialise()
gym_service.initialise()

AUTH_USERNAME = os.getenv("SIRISOS_ADMIN_USERNAME", "brad")
JWT_SECRET = os.getenv("SIRISOS_JWT_SECRET", "change-this-development-secret")


class RecommendationResponse(BaseModel):
    rule_id: str
    module: str
    title: str
    message: str
    severity: Literal["info", "success", "warning", "critical"]
    priority: int


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


@router.get("/recommendations", response_model=list[RecommendationResponse])
async def recommendations(
    authorization: Annotated[str | None, Header()] = None,
) -> list[RecommendationResponse]:
    _authenticate(authorization)
    items = rules_engine.evaluate(
        today=date.today(),
        recent_runs=running_service.list_runs(),
        recent_workouts=gym_service.list_workouts(),
    )
    return [RecommendationResponse(**item.__dict__) for item in items]
