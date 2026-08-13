from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.services.gym_service import GymService
from app.services.running_service import RunningService

# Every achievement here is a concrete, evidence-backed milestone -- a real
# recorded fact crossing a real threshold -- never an arbitrary point total.
# "Kept understated" per the brainstorm's own instinct: no XP, no invented
# scoring. The brainstorm's "Climber" (1,000 m elevation in a month) is
# deliberately excluded -- RunRecord doesn't capture elevation, and this
# repo's convention is to decline rather than approximate when the data
# genuinely isn't there.

WEIGHT_CLUB_THRESHOLD_KG = 100.0
MILLION_KG_THRESHOLD_KG = 1_000_000.0
SUB_25_5K_SECONDS = 25 * 60
FIVE_K_TARGET_KM = 5.0
FIVE_K_TOLERANCE_KM = 0.5
CONSISTENCY_MIN_DAYS_PER_WEEK = 4
CONSISTENCY_STREAK_WEEKS = 8
PROGRESSIVE_STREAK_SESSIONS = 5

_MAJOR_LIFTS = {
    "bench": "Bench Press",
    "squat": "Squat",
    "deadlift": "Deadlift",
    "overhead press": "Overhead Press",
}


@dataclass(frozen=True)
class Achievement:
    id: str
    title: str
    description: str
    unlocked: bool
    achieved_date: date | None
    progress_label: str


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


class AchievementService:
    def __init__(
        self,
        running_service: RunningService | None = None,
        gym_service: GymService | None = None,
    ) -> None:
        self._running_service = running_service or RunningService()
        self._gym_service = gym_service or GymService()

    def list_achievements(self, *, today: date | None = None) -> list[Achievement]:
        today = today or date.today()
        exercises = self._gym_service.list_exercises()
        workouts = self._gym_service.list_workouts()
        runs = self._running_service.list_runs()

        achievements: list[Achievement] = []
        for token, label in _MAJOR_LIFTS.items():
            achievements.append(self._weight_club(token, label, exercises))
        achievements.append(self._million_kg_club(workouts))
        achievements.append(self._sub_25_5k(runs))
        achievements.append(self._consistency_streak(workouts, runs, today))
        achievements.append(self._progressive_streak(exercises))
        return achievements

    @staticmethod
    def _weight_club(token: str, label: str, exercises) -> Achievement:
        matches = [item for item in exercises if token in item.exercise.casefold()]
        best_weight = max((item.best_weight_kg for item in matches), default=0.0)
        unlocked = best_weight >= WEIGHT_CLUB_THRESHOLD_KG

        achieved_date: date | None = None
        if unlocked:
            crossing_points = [
                point
                for item in matches
                for point in item.history
                if point.weight_kg >= WEIGHT_CLUB_THRESHOLD_KG
            ]
            achieved_date = min(point.workout_date for point in crossing_points)

        progress_label = (
            f"{best_weight:g} / {WEIGHT_CLUB_THRESHOLD_KG:g} kg"
            if not unlocked
            else f"{best_weight:g} kg"
        )
        return Achievement(
            id=f"{token.replace(' ', '_')}_100_club",
            title=f"{label} 100 Club",
            description=f"Lift {WEIGHT_CLUB_THRESHOLD_KG:g} kg or more on {label}.",
            unlocked=unlocked,
            achieved_date=achieved_date,
            progress_label=progress_label,
        )

    @staticmethod
    def _million_kg_club(workouts) -> Achievement:
        ordered = sorted(workouts, key=lambda workout: workout.workout_date)
        total = 0.0
        achieved_date: date | None = None
        for workout in ordered:
            total += workout.total_volume_kg
            if achieved_date is None and total >= MILLION_KG_THRESHOLD_KG:
                achieved_date = workout.workout_date
        unlocked = total >= MILLION_KG_THRESHOLD_KG
        progress_label = (
            f"{total:,.0f} kg"
            if unlocked
            else f"{total:,.0f} / {MILLION_KG_THRESHOLD_KG:,.0f} kg"
        )
        return Achievement(
            id="million_kilo_club",
            title="Million Kilo Club",
            description=f"Lift {MILLION_KG_THRESHOLD_KG:,.0f} kg of total lifetime volume.",
            unlocked=unlocked,
            achieved_date=achieved_date,
            progress_label=progress_label,
        )

    @staticmethod
    def _sub_25_5k(runs) -> Achievement:
        candidates = [
            run for run in runs if abs(run.distance_km - FIVE_K_TARGET_KM) <= FIVE_K_TOLERANCE_KM
        ]
        qualifying = sorted(
            (
                run
                for run in candidates
                if run.distance_km * run.average_pace_seconds_per_km < SUB_25_5K_SECONDS
            ),
            key=lambda run: run.run_date,
        )
        unlocked = bool(qualifying)
        if unlocked:
            best_seconds = int(round(qualifying[0].distance_km * qualifying[0].average_pace_seconds_per_km))
            progress_label = f"{best_seconds // 60}:{best_seconds % 60:02d}"
        elif candidates:
            fastest = min(candidates, key=lambda run: run.distance_km * run.average_pace_seconds_per_km)
            seconds = int(round(fastest.distance_km * fastest.average_pace_seconds_per_km))
            progress_label = f"Best 5K {seconds // 60}:{seconds % 60:02d} (need under 25:00)"
        else:
            progress_label = "No 5K runs logged yet"
        return Achievement(
            id="sub_25_5k",
            title="Sub-25",
            description="Run a 5K in under 25 minutes.",
            unlocked=unlocked,
            achieved_date=qualifying[0].run_date if unlocked else None,
            progress_label=progress_label,
        )

    @staticmethod
    def _consistency_streak(workouts, runs, today: date) -> Achievement:
        # Only fully-elapsed weeks count -- the current (in-progress) week is
        # excluded so it can neither falsely break nor falsely complete a
        # streak before it's actually over.
        training_dates = {workout.workout_date for workout in workouts} | {run.run_date for run in runs}
        current_week_start = _week_start(today)
        days_by_week: dict[date, set[date]] = {}
        for day in training_dates:
            week_start = _week_start(day)
            if week_start >= current_week_start:
                continue
            days_by_week.setdefault(week_start, set()).add(day)

        qualifying_weeks = sorted(
            week for week, days in days_by_week.items() if len(days) >= CONSISTENCY_MIN_DAYS_PER_WEEK
        )

        best_streak = 0
        streak = 0
        previous_week: date | None = None
        streak_end_week: date | None = None
        best_streak_end_week: date | None = None
        for week in qualifying_weeks:
            if previous_week is not None and week == previous_week + timedelta(weeks=1):
                streak += 1
            else:
                streak = 1
            streak_end_week = week
            if streak > best_streak:
                best_streak = streak
                best_streak_end_week = streak_end_week
            previous_week = week

        unlocked = best_streak >= CONSISTENCY_STREAK_WEEKS
        achieved_date = None
        if unlocked and best_streak_end_week is not None:
            achieved_date = best_streak_end_week + timedelta(days=6)
        progress_label = (
            f"{best_streak} weeks"
            if unlocked
            else f"{best_streak} / {CONSISTENCY_STREAK_WEEKS} consecutive weeks"
        )
        return Achievement(
            id="consistency_streak",
            title="Consistency",
            description=(
                f"Train {CONSISTENCY_MIN_DAYS_PER_WEEK}+ days a week for "
                f"{CONSISTENCY_STREAK_WEEKS} consecutive weeks."
            ),
            unlocked=unlocked,
            achieved_date=achieved_date,
            progress_label=progress_label,
        )

    @staticmethod
    def _progressive_streak(exercises) -> Achievement:
        # achieved_date is the first time ANY exercise's streak reached the
        # threshold -- not the date of whichever session the longest streak
        # happens to end on later -- matching the "first crossing" semantics
        # the other achievements use. progress_label separately shows
        # whichever exercise currently has the longest streak, since that's
        # the more useful "how am I doing" number to display.
        best_overall_streak = 0
        best_overall_exercise: str | None = None
        earliest_unlock_date: date | None = None

        for summary in exercises:
            sessions: dict[int, tuple[date, float]] = {}
            for point in summary.history:
                current = sessions.get(point.workout_id)
                if current is None or point.weight_kg > current[1]:
                    sessions[point.workout_id] = (point.workout_date, point.weight_kg)
            ordered = sorted(sessions.values(), key=lambda item: item[0])

            streak = 1 if ordered else 0
            best_for_exercise = streak
            first_crossing_date: date | None = None
            for index in range(1, len(ordered)):
                if ordered[index][1] > ordered[index - 1][1]:
                    streak += 1
                else:
                    streak = 1
                best_for_exercise = max(best_for_exercise, streak)
                if first_crossing_date is None and streak >= PROGRESSIVE_STREAK_SESSIONS:
                    first_crossing_date = ordered[index][0]

            if best_for_exercise > best_overall_streak:
                best_overall_streak = best_for_exercise
                best_overall_exercise = summary.exercise
            if first_crossing_date is not None and (
                earliest_unlock_date is None or first_crossing_date < earliest_unlock_date
            ):
                earliest_unlock_date = first_crossing_date

        unlocked = best_overall_streak >= PROGRESSIVE_STREAK_SESSIONS
        progress_label = (
            f"{best_overall_streak} sessions on {best_overall_exercise}"
            if unlocked and best_overall_exercise
            else f"{best_overall_streak} / {PROGRESSIVE_STREAK_SESSIONS} sessions"
            + (f" on {best_overall_exercise}" if best_overall_exercise else "")
        )
        return Achievement(
            id="progressive_streak",
            title="Progressive",
            description=f"Improve an exercise across {PROGRESSIVE_STREAK_SESSIONS} consecutive sessions.",
            unlocked=unlocked,
            achieved_date=earliest_unlock_date if unlocked else None,
            progress_label=progress_label,
        )
