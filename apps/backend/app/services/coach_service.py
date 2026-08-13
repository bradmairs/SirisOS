from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.services.gym_service import GymService, Workout
from app.services.running_service import RunningService
from app.services.training_load_service import TrainingLoadService, WeeklyTrainingLoad


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


@dataclass(frozen=True)
class ExerciseImprovement:
    exercise: str
    record_type: Literal["weight", "estimated_one_rep_max", "set_volume"]
    value: float
    previous_value: float


@dataclass(frozen=True)
class WeeklyCoachReport:
    week_start: date
    week_end: date
    headline: str
    training_load: WeeklyTrainingLoad
    running_distance_km: float
    running_distance_km_delta: float | None
    run_count: int
    run_count_delta: int | None
    gym_volume_kg: float
    gym_volume_kg_delta: float | None
    gym_session_count: int
    gym_session_count_delta: int | None
    improvements: list[ExerciseImprovement]


def _weekly_improvements(
    workouts: list[Workout], week_start: date, week_end: date
) -> list[ExerciseImprovement]:
    # Retroactive version of the same independent-per-record-type comparison
    # ADR 067's create_workout() does at save time -- this week's best set per
    # exercise vs every set logged strictly before this week. An exercise
    # logged for the first time ever this week has nothing prior to beat, so
    # (matching ADR 067) it isn't counted as an improvement.
    this_week: dict[str, list] = {}
    prior: dict[str, list] = {}
    display_names: dict[str, str] = {}
    for workout in workouts:
        for item in workout.sets:
            key = item.exercise.strip().casefold()
            display_names.setdefault(key, item.exercise.strip())
            if week_start <= workout.workout_date <= week_end:
                this_week.setdefault(key, []).append(item)
            elif workout.workout_date < week_start:
                prior.setdefault(key, []).append(item)

    improvements: list[ExerciseImprovement] = []
    for key, this_week_sets in this_week.items():
        prior_sets = prior.get(key)
        if not prior_sets:
            continue
        exercise = display_names[key]
        checks = (
            ("weight", max(s.weight_kg for s in this_week_sets), max(s.weight_kg for s in prior_sets)),
            (
                "estimated_one_rep_max",
                max(s.estimated_one_rep_max_kg for s in this_week_sets),
                max(s.estimated_one_rep_max_kg for s in prior_sets),
            ),
            ("set_volume", max(s.volume_kg for s in this_week_sets), max(s.volume_kg for s in prior_sets)),
        )
        for record_type, current_best, prior_best in checks:
            if current_best > prior_best:
                improvements.append(
                    ExerciseImprovement(
                        exercise=exercise,
                        record_type=record_type,  # type: ignore[arg-type]
                        value=current_best,
                        previous_value=prior_best,
                    )
                )
    return improvements


def _headline(training_load: WeeklyTrainingLoad, improvements: list[ExerciseImprovement]) -> str:
    if not improvements:
        return training_load.assessment
    names = ", ".join(sorted({item.exercise for item in improvements}))
    return f"New best on {names}. {training_load.assessment}"


class CoachService:
    def __init__(
        self,
        running_service: RunningService | None = None,
        gym_service: GymService | None = None,
        training_load_service: TrainingLoadService | None = None,
    ) -> None:
        self._running_service = running_service or RunningService()
        self._gym_service = gym_service or GymService()
        self._training_load_service = training_load_service or TrainingLoadService(
            running_service=self._running_service, gym_service=self._gym_service
        )

    def weekly_report(self, *, reference_date: date | None = None) -> WeeklyCoachReport:
        anchor = reference_date or date.today()
        week_start = _week_start(anchor)
        week_end = week_start + timedelta(days=6)
        previous_week_start = week_start - timedelta(weeks=1)
        previous_week_end = previous_week_start + timedelta(days=6)

        runs = self._running_service.list_runs()
        workouts = self._gym_service.list_workouts()

        running_distance_km = round(
            sum(run.distance_km for run in runs if week_start <= run.run_date <= week_end), 1
        )
        run_count = sum(1 for run in runs if week_start <= run.run_date <= week_end)
        has_prior_runs = any(run.run_date < week_start for run in runs)
        previous_running_distance_km = sum(
            run.distance_km for run in runs if previous_week_start <= run.run_date <= previous_week_end
        )
        previous_run_count = sum(
            1 for run in runs if previous_week_start <= run.run_date <= previous_week_end
        )

        gym_volume_kg = round(
            sum(
                workout.total_volume_kg
                for workout in workouts
                if week_start <= workout.workout_date <= week_end
            ),
            1,
        )
        gym_session_count = sum(
            1 for workout in workouts if week_start <= workout.workout_date <= week_end
        )
        has_prior_workouts = any(workout.workout_date < week_start for workout in workouts)
        previous_gym_volume_kg = sum(
            workout.total_volume_kg
            for workout in workouts
            if previous_week_start <= workout.workout_date <= previous_week_end
        )
        previous_gym_session_count = sum(
            1
            for workout in workouts
            if previous_week_start <= workout.workout_date <= previous_week_end
        )

        training_load = self._training_load_service.weekly_load(reference_date=anchor)
        improvements = _weekly_improvements(workouts, week_start, week_end)

        return WeeklyCoachReport(
            week_start=week_start,
            week_end=week_end,
            headline=_headline(training_load, improvements),
            training_load=training_load,
            running_distance_km=running_distance_km,
            running_distance_km_delta=(
                round(running_distance_km - previous_running_distance_km, 1) if has_prior_runs else None
            ),
            run_count=run_count,
            run_count_delta=(run_count - previous_run_count) if has_prior_runs else None,
            gym_volume_kg=gym_volume_kg,
            gym_volume_kg_delta=(
                round(gym_volume_kg - previous_gym_volume_kg, 1) if has_prior_workouts else None
            ),
            gym_session_count=gym_session_count,
            gym_session_count_delta=(
                (gym_session_count - previous_gym_session_count) if has_prior_workouts else None
            ),
            improvements=improvements,
        )
