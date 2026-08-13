from datetime import date
import os
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException, Query

from pydantic import BaseModel

from app.services.ask_siris_service import AskSirisService
from app.services.coach_service import CoachService
from app.services.ollama_service import chat_client

router = APIRouter(prefix="/coach", tags=["coach"])
service = CoachService()
ask_siris_service = AskSirisService()

ASK_SIRIS_SYSTEM_PROMPT = (
    "You are Siris, a personal training coach assistant. Rephrase the given "
    "deterministic answer as one or two natural, conversational sentences. Use "
    "only the facts already stated in the answer -- do not add numbers, dates, "
    "exercises or claims that are not already there."
)

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


class TrainingLoadSummaryResponse(BaseModel):
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


class ExerciseImprovementResponse(BaseModel):
    exercise: str
    record_type: Literal["weight", "estimated_one_rep_max", "set_volume"]
    value: float
    previous_value: float


class WeeklyCoachReportResponse(BaseModel):
    week_start: date
    week_end: date
    headline: str
    training_load: TrainingLoadSummaryResponse
    running_distance_km: float
    running_distance_km_delta: float | None
    run_count: int
    run_count_delta: int | None
    gym_volume_kg: float
    gym_volume_kg_delta: float | None
    gym_session_count: int
    gym_session_count_delta: int | None
    improvements: list[ExerciseImprovementResponse]


def _response(report) -> WeeklyCoachReportResponse:
    return WeeklyCoachReportResponse(
        week_start=report.week_start,
        week_end=report.week_end,
        headline=report.headline,
        training_load=TrainingLoadSummaryResponse(**report.training_load.__dict__),
        running_distance_km=report.running_distance_km,
        running_distance_km_delta=report.running_distance_km_delta,
        run_count=report.run_count,
        run_count_delta=report.run_count_delta,
        gym_volume_kg=report.gym_volume_kg,
        gym_volume_kg_delta=report.gym_volume_kg_delta,
        gym_session_count=report.gym_session_count,
        gym_session_count_delta=report.gym_session_count_delta,
        improvements=[ExerciseImprovementResponse(**item.__dict__) for item in report.improvements],
    )


@router.get("/weekly-report", response_model=WeeklyCoachReportResponse)
async def weekly_report(
    authorization: Annotated[str | None, Header()] = None
) -> WeeklyCoachReportResponse:
    _authenticate(authorization)
    return _response(service.weekly_report())


class AskSirisResponse(BaseModel):
    question: str
    understood: bool
    answer: str
    facts: dict
    synthesized_answer: str | None
    suggestions: list[str]


@router.get("/ask", response_model=AskSirisResponse)
async def ask_siris(
    question: Annotated[str, Query(min_length=2, max_length=500)],
    authorization: Annotated[str | None, Header()] = None,
) -> AskSirisResponse:
    _authenticate(authorization)
    result = ask_siris_service.answer(question)
    synthesized_answer = (
        await chat_client.complete(system=ASK_SIRIS_SYSTEM_PROMPT, prompt=f"Question: {result.question}\n\nDeterministic answer: {result.answer}")
        if result.understood
        else None
    )
    return AskSirisResponse(
        question=result.question,
        understood=result.understood,
        answer=result.answer,
        facts=result.facts,
        synthesized_answer=synthesized_answer,
        suggestions=result.suggestions,
    )
