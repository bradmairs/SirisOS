from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.services.coach_service import CoachService
from app.services.gym_service import GymService
from app.services.running_service import RunningService

EXAMPLE_QUESTIONS = [
    "What's my best 5K this year?",
    "How much has my bench press improved since 2026-01-01?",
    "Which exercise has improved the most?",
    "When did I last deadlift 140 kg?",
    "How many leg workouts have I done this month?",
    "How's my training going this week?",
]

# Ask Siris v1 is deliberately a small, fixed set of recognized question
# patterns (not an NLU/ML classifier) -- each handler either confidently
# answers from real data or declines, so it never guesses. Questions this
# repo genuinely can't answer yet (muscle-group strength -- no exercise
# taxonomy exists; sleep/recovery correlation -- the Health summary API
# doesn't exist yet) fall through to the "not understood" response with
# suggestions, rather than being half-answered.


@dataclass(frozen=True)
class AskSirisAnswer:
    question: str
    understood: bool
    answer: str
    facts: dict[str, object]
    synthesized_answer: str | None = None
    suggestions: list[str] = field(default_factory=list)


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _period_start(question: str, today: date) -> tuple[date | None, str]:
    lowered = question.lower()
    if "this week" in lowered:
        return _week_start(today), "this week"
    if "this month" in lowered:
        return today.replace(day=1), "this month"
    if "this year" in lowered:
        return today.replace(month=1, day=1), "this year"
    match = re.search(r"since (\d{4}-\d{2}-\d{2})", lowered)
    if match:
        since = date.fromisoformat(match.group(1))
        return since, f"since {since.isoformat()}"
    return None, "all time"


def _find_exercise(question: str, exercise_names: list[str]) -> str | None:
    lowered = question.lower()
    matches = [name for name in exercise_names if name.lower() in lowered]
    if not matches:
        return None
    return max(matches, key=len)


def _find_weight_kg(question: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*kg", question.lower())
    return float(match.group(1)) if match else None


def _find_distance_km(question: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*k(?:m|ilomet)?\b", question.lower())
    return float(match.group(1)) if match else None


class AskSirisService:
    def __init__(
        self,
        running_service: RunningService | None = None,
        gym_service: GymService | None = None,
        coach_service: CoachService | None = None,
    ) -> None:
        self._running_service = running_service or RunningService()
        self._gym_service = gym_service or GymService()
        self._coach_service = coach_service or CoachService(
            running_service=self._running_service, gym_service=self._gym_service
        )

    def answer(self, question: str, *, today: date | None = None) -> AskSirisAnswer:
        today = today or date.today()
        handlers = (
            self._last_time_at_weight,
            self._exercise_progress,
            self._most_improved_exercise,
            self._best_distance,
            self._training_counts,
            self._weekly_summary,
        )
        for handler in handlers:
            result = handler(question, today)
            if result is not None:
                return result

        return AskSirisAnswer(
            question=question,
            understood=False,
            answer=(
                "I don't recognise that question yet. I can answer questions like "
                "the examples below -- ask me one of those, or phrase it similarly."
            ),
            facts={},
            suggestions=list(EXAMPLE_QUESTIONS),
        )

    def _exercise_names(self) -> list[str]:
        return [item.exercise for item in self._gym_service.list_exercises()]

    def _last_time_at_weight(self, question: str, today: date) -> AskSirisAnswer | None:
        lowered = question.lower()
        if "last" not in lowered:
            return None
        weight = _find_weight_kg(question)
        exercise = _find_exercise(question, self._exercise_names())
        if weight is None or exercise is None:
            return None

        summary = self._gym_service.get_exercise(exercise)
        if summary is None:
            return None
        matching = [point for point in summary.history if point.weight_kg >= weight]
        if not matching:
            return AskSirisAnswer(
                question=question,
                understood=True,
                answer=(
                    f"You haven't lifted {weight:g} kg on {exercise} yet. "
                    f"Your best so far is {summary.best_weight_kg:g} kg."
                ),
                facts={"exercise": exercise, "best_weight_kg": summary.best_weight_kg},
            )
        latest = max(matching, key=lambda point: point.workout_date)
        return AskSirisAnswer(
            question=question,
            understood=True,
            answer=(
                f"You last lifted {weight:g} kg or more on {exercise} on "
                f"{latest.workout_date.isoformat()} ({latest.weight_kg:g} kg x {latest.reps})."
            ),
            facts={
                "exercise": exercise,
                "workout_date": latest.workout_date.isoformat(),
                "weight_kg": latest.weight_kg,
                "reps": latest.reps,
            },
        )

    def _exercise_progress(self, question: str, today: date) -> AskSirisAnswer | None:
        lowered = question.lower()
        if not any(word in lowered for word in ("improv", "progress", "max", "1rm", "personal record", " pr ")):
            return None
        exercise = _find_exercise(question, self._exercise_names())
        if exercise is None:
            return None

        summary = self._gym_service.get_exercise(exercise)
        if summary is None or not summary.history:
            return None

        since, period_label = _period_start(question, today)
        if since is not None:
            baseline_points = [point for point in summary.history if point.workout_date < since]
            if not baseline_points:
                return AskSirisAnswer(
                    question=question,
                    understood=True,
                    answer=f"You don't have any {exercise} sets logged before {since.isoformat()} to compare against.",
                    facts={"exercise": exercise},
                )
            baseline_e1rm = max(point.estimated_one_rep_max_kg for point in baseline_points)
            delta = round(summary.best_estimated_one_rep_max_kg - baseline_e1rm, 1)
            direction = "up" if delta > 0 else "down" if delta < 0 else "unchanged for"
            return AskSirisAnswer(
                question=question,
                understood=True,
                answer=(
                    f"Your {exercise} estimated 1RM is {direction} {abs(delta):g} kg {period_label} -- "
                    f"from {baseline_e1rm:g} kg to {summary.best_estimated_one_rep_max_kg:g} kg."
                ),
                facts={
                    "exercise": exercise,
                    "baseline_estimated_one_rep_max_kg": baseline_e1rm,
                    "current_estimated_one_rep_max_kg": summary.best_estimated_one_rep_max_kg,
                    "delta_kg": delta,
                },
            )

        return AskSirisAnswer(
            question=question,
            understood=True,
            answer=(
                f"Your best {exercise} is {summary.best_weight_kg:g} kg "
                f"(estimated 1RM {summary.best_estimated_one_rep_max_kg:g} kg), "
                f"last logged on {summary.latest_date.isoformat()}."
            ),
            facts={
                "exercise": exercise,
                "best_weight_kg": summary.best_weight_kg,
                "best_estimated_one_rep_max_kg": summary.best_estimated_one_rep_max_kg,
                "latest_date": summary.latest_date.isoformat(),
            },
        )

    def _most_improved_exercise(self, question: str, today: date) -> AskSirisAnswer | None:
        lowered = question.lower()
        if "most improved" not in lowered and "improved the most" not in lowered:
            return None

        window_start = today - timedelta(days=90)
        best_exercise: str | None = None
        best_delta = 0.0
        for summary in self._gym_service.list_exercises():
            window_points = [point for point in summary.history if point.workout_date >= window_start]
            baseline_points = [point for point in summary.history if point.workout_date < window_start]
            if not window_points or not baseline_points:
                continue
            current = max(point.estimated_one_rep_max_kg for point in window_points)
            baseline = max(point.estimated_one_rep_max_kg for point in baseline_points)
            delta = current - baseline
            if delta > best_delta:
                best_delta = delta
                best_exercise = summary.exercise

        if best_exercise is None:
            return AskSirisAnswer(
                question=question,
                understood=True,
                answer="No exercise has a clear improvement over the last 90 days yet.",
                facts={},
            )
        return AskSirisAnswer(
            question=question,
            understood=True,
            answer=(
                f"{best_exercise} has improved the most over the last 90 days -- "
                f"estimated 1RM up {round(best_delta, 1):g} kg."
            ),
            facts={"exercise": best_exercise, "delta_kg": round(best_delta, 1)},
        )

    def _best_distance(self, question: str, today: date) -> AskSirisAnswer | None:
        lowered = question.lower()
        if not any(word in lowered for word in ("best", "fastest")):
            return None
        target_km = _find_distance_km(question)
        if target_km is None:
            return None

        since, period_label = _period_start(question, today)
        tolerance_km = max(0.5, target_km * 0.1)
        candidates = [
            run
            for run in self._running_service.list_runs()
            if abs(run.distance_km - target_km) <= tolerance_km
            and (since is None or run.run_date >= since)
            and run.run_date <= today
        ]
        if not candidates:
            return AskSirisAnswer(
                question=question,
                understood=True,
                answer=f"No runs close to {target_km:g} km logged {period_label}.",
                facts={"target_km": target_km},
            )
        best = min(candidates, key=lambda run: run.average_pace_seconds_per_km)
        pace = best.average_pace_seconds_per_km
        pace_label = f"{pace // 60}:{pace % 60:02d}/km"
        return AskSirisAnswer(
            question=question,
            understood=True,
            answer=(
                f"Your best {target_km:g} km run {period_label} was on {best.run_date.isoformat()} "
                f"at {pace_label} ({best.distance_km:g} km)."
            ),
            facts={
                "run_date": best.run_date.isoformat(),
                "distance_km": best.distance_km,
                "average_pace_seconds_per_km": pace,
            },
        )

    def _training_counts(self, question: str, today: date) -> AskSirisAnswer | None:
        lowered = question.lower()
        if "how many" not in lowered:
            return None
        if not any(word in lowered for word in ("workout", "run", "session", "trained", "train")):
            return None

        since, period_label = _period_start(question, today)
        is_running = "run" in lowered and "workout" not in lowered

        if is_running:
            runs = self._running_service.list_runs()
            count = sum(
                1 for run in runs if (since is None or run.run_date >= since) and run.run_date <= today
            )
            return AskSirisAnswer(
                question=question,
                understood=True,
                answer=f"You've logged {count} run{'s' if count != 1 else ''} {period_label}.",
                facts={"count": count, "period": period_label},
            )

        workouts = self._gym_service.list_workouts()
        name_filter = next(
            (word for word in ("leg", "push", "pull", "upper", "lower", "full body") if word in lowered),
            None,
        )
        filtered = [
            workout
            for workout in workouts
            if (since is None or workout.workout_date >= since)
            and workout.workout_date <= today
            and (name_filter is None or name_filter in workout.name.lower())
        ]
        label = f"{name_filter} " if name_filter else ""
        return AskSirisAnswer(
            question=question,
            understood=True,
            answer=f"You've logged {len(filtered)} {label}workout{'s' if len(filtered) != 1 else ''} {period_label}.",
            facts={"count": len(filtered), "period": period_label, "filter": name_filter},
        )

    def _weekly_summary(self, question: str, today: date) -> AskSirisAnswer | None:
        lowered = question.lower()
        if not any(
            phrase in lowered
            for phrase in ("training going", "training this week", "how am i doing", "this week's training")
        ):
            return None

        report = self._coach_service.weekly_report(reference_date=today)
        return AskSirisAnswer(
            question=question,
            understood=True,
            answer=report.headline,
            facts={
                "running_distance_km": report.running_distance_km,
                "gym_volume_kg": report.gym_volume_kg,
                "combined_index": report.training_load.combined_index,
            },
        )
