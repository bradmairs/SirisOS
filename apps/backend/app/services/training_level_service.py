from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.services.gym_service import GymService
from app.services.running_service import RunningService

# Deliberately three dimensions, not the brainstorm's original four
# (Strength/Endurance/Consistency/Recovery). Strength now has a real basis
# (self-relative Strength Score, ADR 085) and Endurance/Consistency always
# did (ADR 074), but Recovery still doesn't: nobody has combined HRV
# baseline_ratio and resting-HR baseline_ratio into one number before, and
# doing so now would mean inventing a weighting between two different
# physiological signals rather than reusing an established one. ADR 074's
# own escape hatch -- "a future attempt has to either find a real basis...
# or explicitly accept the fabrication tradeoff" -- applies again: Recovery
# stays a named, deferred gap, not silently dropped.
CONSISTENCY_BASELINE_WEEKS = 8
CONSISTENCY_MIN_BASELINE_WEEKS = 2


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


@dataclass(frozen=True)
class TrainingLevelDimension:
    dimension: Literal["strength", "endurance", "consistency"]
    score: float | None
    detail: str


@dataclass(frozen=True)
class TrainingLevel:
    overall_score: float | None
    dimensions: list[TrainingLevelDimension]


class TrainingLevelService:
    def __init__(
        self,
        gym_service: GymService | None = None,
        running_service: RunningService | None = None,
    ) -> None:
        self._gym_service = gym_service or GymService()
        self._running_service = running_service or RunningService()

    def training_level(self, *, today: date | None = None) -> TrainingLevel:
        today = today or date.today()
        dimensions = [
            self._strength_dimension(),
            self._endurance_dimension(),
            self._consistency_dimension(today),
        ]
        scored = [item.score for item in dimensions if item.score is not None]
        overall = round(sum(scored) / len(scored), 1) if scored else None
        return TrainingLevel(overall_score=overall, dimensions=dimensions)

    def _strength_dimension(self) -> TrainingLevelDimension:
        # Reuses GymService.strength_score() exactly as computed there
        # (ADR 085) -- current e1RM versus each exercise's own all-time
        # peak, averaged by muscle group then by group. No new inference.
        strength = self._gym_service.strength_score()
        if strength.overall_score is None:
            return TrainingLevelDimension(
                dimension="strength",
                score=None,
                detail="Log and tag a few exercises to unlock this.",
            )
        return TrainingLevelDimension(
            dimension="strength",
            score=round(strength.overall_score * 100, 1),
            detail="Current lifts versus your own all-time peaks.",
        )

    def _endurance_dimension(self) -> TrainingLevelDimension:
        # RunRecord.fitness_score is already a 0-100 EWMA of the runner's
        # own effort_score history -- the most recent run's value is the
        # current reading.
        runs = self._running_service.list_runs()
        if not runs:
            return TrainingLevelDimension(
                dimension="endurance",
                score=None,
                detail="Log a run to unlock this.",
            )
        return TrainingLevelDimension(
            dimension="endurance",
            score=round(runs[0].fitness_score, 1),
            detail="Trend of your own recent running effort.",
        )

    def _consistency_dimension(self, today: date) -> TrainingLevelDimension:
        # Weekly-bucketed, same convention as AchievementService's own
        # consistency streak -- only fully-elapsed weeks count, so an
        # in-progress week can't look artificially bad just because it
        # hasn't finished yet. Self-relative: last full week's distinct
        # training days versus the athlete's own trailing average across
        # weeks that had any training (mirrors muscle_group_fatigue()'s
        # baseline, which likewise averages over historical sessions that
        # exist rather than zero-filling empty calendar gaps).
        training_dates = {workout.workout_date for workout in self._gym_service.list_workouts()} | {
            run.run_date for run in self._running_service.list_runs()
        }

        current_week_start = _week_start(today)
        days_by_week: dict[date, set[date]] = {}
        for day in training_dates:
            week_start = _week_start(day)
            if week_start >= current_week_start:
                continue
            days_by_week.setdefault(week_start, set()).add(day)

        last_full_week_start = current_week_start - timedelta(weeks=1)
        last_full_week_days = len(days_by_week.get(last_full_week_start, set()))

        baseline_cutoff = current_week_start - timedelta(weeks=CONSISTENCY_BASELINE_WEEKS + 1)
        baseline_counts = [
            len(days)
            for week, days in days_by_week.items()
            if baseline_cutoff <= week < last_full_week_start
        ]

        if len(baseline_counts) < CONSISTENCY_MIN_BASELINE_WEEKS:
            return TrainingLevelDimension(
                dimension="consistency",
                score=None,
                detail="Not enough weekly training history yet to compare against.",
            )

        baseline_average = sum(baseline_counts) / len(baseline_counts)
        ratio = (last_full_week_days / baseline_average) if baseline_average > 0 else (
            1.0 if last_full_week_days > 0 else 0.0
        )
        score = round(min(1.0, ratio) * 100, 1)
        day_word = "day" if last_full_week_days == 1 else "days"
        return TrainingLevelDimension(
            dimension="consistency",
            score=score,
            detail=(
                f"{last_full_week_days} training {day_word} last week, versus your own "
                f"{baseline_average:.1f}-day trailing average."
            ),
        )
