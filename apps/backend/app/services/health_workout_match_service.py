from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.services.gym_service import GymService
from app.services.health_ingest_service import HealthIngestService
from app.services.running_service import RunningService

UNLOGGED_WORKOUTS_DEFAULT_LOOKBACK_DAYS = 30

# Deliberately narrow matching: SirisOS only logs two activity categories
# (gym sessions, runs), so only Apple Health workout types that clearly map
# to one of those are ever flagged. A watch-tracked walk, swim, yoga or HIIT
# session has nowhere to be "logged" in this app yet, so treating it as
# missing would be misleading, not helpful -- same reasoning that kept
# muscle-group tagging athlete-assigned rather than keyword-guessed (ADR 083).
_RUN_TYPE_KEYWORDS = ("run",)
_STRENGTH_TYPE_KEYWORDS = ("strength",)


def _match_category(workout_type: str) -> Literal["running", "strength"] | None:
    lowered = workout_type.lower()
    if any(keyword in lowered for keyword in _RUN_TYPE_KEYWORDS):
        return "running"
    if any(keyword in lowered for keyword in _STRENGTH_TYPE_KEYWORDS):
        return "strength"
    return None


@dataclass(frozen=True)
class UnloggedHealthWorkout:
    external_id: str
    workout_type: str
    category: Literal["running", "strength"]
    start_date: date
    duration_seconds: float | None
    distance_m: float | None


class HealthWorkoutMatchService:
    def __init__(
        self,
        health_service: HealthIngestService | None = None,
        gym_service: GymService | None = None,
        running_service: RunningService | None = None,
    ) -> None:
        self._health_service = health_service or HealthIngestService()
        self._gym_service = gym_service or GymService()
        self._running_service = running_service or RunningService()

    def list_unlogged_workouts(
        self,
        *,
        lookback_days: int = UNLOGGED_WORKOUTS_DEFAULT_LOOKBACK_DAYS,
        today: date | None = None,
    ) -> list[UnloggedHealthWorkout]:
        today = today or date.today()
        since = today - timedelta(days=lookback_days)
        health_workouts = self._health_service.list_workouts(since=since)
        if not health_workouts:
            return []

        # Matched by same local calendar date only -- no time-of-day or
        # duration/distance closeness check. A same-day match is the
        # deterministic signal already used elsewhere in this app
        # (TrainingConflictService's own session-logged-today check); trying
        # to match more precisely would mean guessing which of several same-day
        # sets/runs corresponds to which Health entry, with no reliable basis.
        run_dates = {run.run_date for run in self._running_service.list_runs()}
        gym_dates = {workout.workout_date for workout in self._gym_service.list_workouts()}

        unlogged: list[UnloggedHealthWorkout] = []
        for workout in health_workouts:
            category = _match_category(workout.workout_type)
            if category is None:
                continue
            logged_dates = run_dates if category == "running" else gym_dates
            if workout.start_date in logged_dates:
                continue
            unlogged.append(
                UnloggedHealthWorkout(
                    external_id=workout.external_id,
                    workout_type=workout.workout_type,
                    category=category,
                    start_date=workout.start_date,
                    duration_seconds=workout.duration_seconds,
                    distance_m=workout.distance_m,
                )
            )
        return unlogged
