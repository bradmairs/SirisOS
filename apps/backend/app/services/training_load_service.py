from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.services.gym_service import GymService, Workout
from app.services.running_service import RunningService, RunRecord

TRAINING_LOAD_BASELINE_WEEKS = 8
MIN_BASELINE_WEEKS = 2


@dataclass(frozen=True)
class WeeklyTrainingLoad:
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


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


class TrainingLoadService:
    def __init__(
        self,
        running_service: RunningService | None = None,
        gym_service: GymService | None = None,
    ) -> None:
        self._running_service = running_service or RunningService()
        self._gym_service = gym_service or GymService()

    def weekly_load(self, *, reference_date: date | None = None) -> WeeklyTrainingLoad:
        return self.recent_weekly_loads(weeks=1, reference_date=reference_date)[0]

    def recent_weekly_loads(
        self, *, weeks: int = 1, reference_date: date | None = None
    ) -> list[WeeklyTrainingLoad]:
        anchor = reference_date or date.today()
        current_week_start = _week_start(anchor)
        runs = self._running_service.list_runs()
        workouts = self._gym_service.list_workouts()

        week_starts = [
            current_week_start - timedelta(weeks=offset) for offset in range(weeks - 1, -1, -1)
        ]
        return [self._load_for_week(week_start, runs, workouts) for week_start in week_starts]

    def _load_for_week(
        self, week_start: date, runs: list[RunRecord], workouts: list[Workout]
    ) -> WeeklyTrainingLoad:
        week_end = week_start + timedelta(days=6)

        running_load = round(
            sum(run.effort_score for run in runs if week_start <= run.run_date <= week_end), 1
        )
        gym_load = round(
            sum(
                workout.total_volume_kg
                for workout in workouts
                if week_start <= workout.workout_date <= week_end
            ),
            1,
        )

        running_baseline, running_ratio = self._baseline_and_ratio(
            records=runs,
            date_of=lambda record: record.run_date,
            value_of=lambda record: record.effort_score,
            week_start=week_start,
        )
        gym_baseline, gym_ratio = self._baseline_and_ratio(
            records=workouts,
            date_of=lambda record: record.workout_date,
            value_of=lambda record: record.total_volume_kg,
            week_start=week_start,
        )

        ratios = [ratio for ratio in (running_ratio, gym_ratio) if ratio is not None]
        combined_index = round(sum(ratios), 1) if ratios else None

        return WeeklyTrainingLoad(
            week_start=week_start,
            week_end=week_end,
            running_load=running_load,
            running_baseline=running_baseline,
            running_ratio=running_ratio,
            gym_load=gym_load,
            gym_baseline=gym_baseline,
            gym_ratio=gym_ratio,
            combined_index=combined_index,
            assessment=self._assessment(combined_index),
        )

    @staticmethod
    def _baseline_and_ratio(
        *,
        records: list,
        date_of,
        value_of,
        week_start: date,
    ) -> tuple[float | None, float | None]:
        # Baseline is the trailing TRAINING_LOAD_BASELINE_WEEKS full weeks before
        # week_start, restricted to weeks that could actually contain data (on or
        # after the modality's first-ever record) -- otherwise a new runner's or
        # lifter's early weeks would be diluted by "zero" weeks that predate them
        # ever training at all, understating their baseline and overstating their
        # ratio. Requires at least MIN_BASELINE_WEEKS qualifying weeks; otherwise
        # there isn't enough personal history yet to say what's "typical".
        if not records:
            return None, None

        earliest_week_start = _week_start(min(date_of(record) for record in records))

        qualifying_week_starts: list[date] = []
        for offset in range(1, TRAINING_LOAD_BASELINE_WEEKS + 1):
            candidate = week_start - timedelta(weeks=offset)
            if candidate < earliest_week_start:
                break
            qualifying_week_starts.append(candidate)

        if len(qualifying_week_starts) < MIN_BASELINE_WEEKS:
            return None, None

        baseline_values = []
        for candidate_start in qualifying_week_starts:
            candidate_end = candidate_start + timedelta(days=6)
            baseline_values.append(
                sum(
                    value_of(record)
                    for record in records
                    if candidate_start <= date_of(record) <= candidate_end
                )
            )
        baseline_average = sum(baseline_values) / len(baseline_values)

        if baseline_average <= 0:
            return round(baseline_average, 1), None

        week_end = week_start + timedelta(days=6)
        current_value = sum(
            value_of(record) for record in records if week_start <= date_of(record) <= week_end
        )
        ratio = round((current_value / baseline_average) * 100, 1)
        return round(baseline_average, 1), ratio

    @staticmethod
    def _assessment(combined_index: float | None) -> str:
        if combined_index is None:
            return "Not enough training history yet to compare this week."
        if combined_index < 70:
            return "Lighter than your typical week."
        if combined_index > 130:
            return "Heavier than your typical week."
        return "A typical week for you."
