from datetime import date
import os
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Header, HTTPException, Query

from pydantic import BaseModel

from app.services.achievement_service import AchievementService
from app.services.ask_siris_service import AskSirisService
from app.services.coach_service import CoachService
from app.services.ollama_service import chat_client
from app.services.training_conflict_service import TrainingConflictService
from app.services.training_level_service import TrainingLevelService

router = APIRouter(prefix="/coach", tags=["coach"])
service = CoachService()
conflict_service = TrainingConflictService()
ask_siris_service = AskSirisService(training_conflict_service=conflict_service)
achievement_service = AchievementService()
training_level_service = TrainingLevelService()

ASK_SIRIS_SYSTEM_PROMPT = (
    "You are Siris, a personal training coach assistant. Rephrase the given "
    "deterministic answer as one or two natural, conversational sentences. Use "
    "only the facts already stated in the answer -- do not add numbers, dates, "
    "exercises or claims that are not already there."
)

WEEKLY_REPORT_SYSTEM_PROMPT = (
    "You are Siris, a personal training coach assistant. Rephrase the given "
    "deterministic weekly training summary as one or two natural, conversational "
    "sentences. Use only the facts already stated -- do not add numbers, dates, "
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
    synthesized_headline: str | None = None
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


def _response(report, *, synthesized_headline: str | None = None) -> WeeklyCoachReportResponse:
    return WeeklyCoachReportResponse(
        week_start=report.week_start,
        week_end=report.week_end,
        headline=report.headline,
        synthesized_headline=synthesized_headline,
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
    report = service.weekly_report()
    # Fail-open, same contract as Ask Siris (ADR 071/081): the deterministic
    # headline is always correct and always returned; this is an optional
    # rephrase on top, never a replacement source of facts. synthesized_headline
    # stays null whenever Ollama is unconfigured, unreachable, or returns
    # nothing usable -- the Flutter card falls back to `headline` in that case.
    synthesized_headline = await chat_client.complete(
        system=WEEKLY_REPORT_SYSTEM_PROMPT,
        prompt=f"Weekly training summary: {report.headline}",
    )
    return _response(report, synthesized_headline=synthesized_headline)


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


class TrainingConflictResponse(BaseModel):
    reference_date: date
    status: Literal["insufficient_data", "clear", "reduced_recovery", "conflict"]
    reasons: list[str]
    trained: bool
    session_summary: str | None
    guidance: str


@router.get("/conflict-check", response_model=TrainingConflictResponse)
async def conflict_check(
    authorization: Annotated[str | None, Header()] = None,
) -> TrainingConflictResponse:
    _authenticate(authorization)
    result = conflict_service.check()
    return TrainingConflictResponse(**result.__dict__)


class AchievementResponse(BaseModel):
    id: str
    title: str
    description: str
    unlocked: bool
    achieved_date: date | None
    progress_label: str


@router.get("/achievements", response_model=list[AchievementResponse])
async def achievements(
    authorization: Annotated[str | None, Header()] = None,
) -> list[AchievementResponse]:
    _authenticate(authorization)
    return [AchievementResponse(**item.__dict__) for item in achievement_service.list_achievements()]


class TrainingLevelDimensionResponse(BaseModel):
    dimension: Literal["strength", "endurance", "consistency"]
    score: float | None
    detail: str


class TrainingLevelResponse(BaseModel):
    overall_score: float | None
    dimensions: list[TrainingLevelDimensionResponse]


@router.get("/training-level", response_model=TrainingLevelResponse)
async def training_level(
    authorization: Annotated[str | None, Header()] = None,
) -> TrainingLevelResponse:
    _authenticate(authorization)
    result = training_level_service.training_level()
    return TrainingLevelResponse(
        overall_score=result.overall_score,
        dimensions=[TrainingLevelDimensionResponse(**item.__dict__) for item in result.dimensions],
    )
