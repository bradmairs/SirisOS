import uuid
from datetime import date

from app.services.gym_service import GymService


def _unique_exercise(label: str) -> str:
    return f"{label} {uuid.uuid4().hex[:8]}"


def _service() -> GymService:
    service = GymService()
    service.initialise()
    return service


def test_no_prior_sets_returns_no_data() -> None:
    service = _service()
    suggestion = service.suggest_progressive_overload(_unique_exercise("Never Logged"))
    assert suggestion.status == "no_data"
    assert suggestion.suggested_weight_kg is None


def test_comfortable_session_at_or_above_target_suggests_progress() -> None:
    service = _service()
    exercise = _unique_exercise("Bench Press")
    service.create_workout(
        workout_date=date(2026, 1, 1),
        name="Push",
        notes=None,
        sets=[
            {"exercise": exercise, "weight_kg": 80, "reps": 8, "rir": 2},
            {"exercise": exercise, "weight_kg": 80, "reps": 8, "rir": 2},
            {"exercise": exercise, "weight_kg": 80, "reps": 9, "rir": 3},
        ],
    )

    suggestion = service.suggest_progressive_overload(exercise)

    assert suggestion.status == "progress"
    assert suggestion.suggested_weight_kg == 82.5
    assert suggestion.suggested_reps == 8
    assert "82.5" in suggestion.rationale


def test_struggled_session_with_dropping_reps_suggests_repeat() -> None:
    service = _service()
    exercise = _unique_exercise("Bench Press Struggle")
    service.create_workout(
        workout_date=date(2026, 1, 2),
        name="Push",
        notes=None,
        sets=[
            {"exercise": exercise, "weight_kg": 80, "reps": 8, "rir": 2},
            {"exercise": exercise, "weight_kg": 80, "reps": 6, "rir": 1},
            {"exercise": exercise, "weight_kg": 80, "reps": 5, "rir": 0},
        ],
    )

    suggestion = service.suggest_progressive_overload(exercise)

    assert suggestion.status == "repeat"
    assert suggestion.suggested_weight_kg == 80
    assert "repeat" in suggestion.rationale.lower()


def test_near_failure_without_dropping_reps_still_suggests_repeat() -> None:
    service = _service()
    exercise = _unique_exercise("Squat Near Failure")
    service.create_workout(
        workout_date=date(2026, 1, 3),
        name="Legs",
        notes=None,
        sets=[
            {"exercise": exercise, "weight_kg": 100, "reps": 5, "rir": 0},
        ],
    )

    suggestion = service.suggest_progressive_overload(exercise)

    assert suggestion.status == "repeat"
    assert suggestion.suggested_weight_kg == 100


def test_suggestion_uses_only_the_most_recent_session() -> None:
    service = _service()
    exercise = _unique_exercise("Deadlift")
    service.create_workout(
        workout_date=date(2026, 1, 1),
        name="Pull",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 120, "reps": 3, "rir": 0}],
    )
    service.create_workout(
        workout_date=date(2026, 1, 8),
        name="Pull",
        notes=None,
        sets=[
            {"exercise": exercise, "weight_kg": 130, "reps": 5, "rir": 2},
            {"exercise": exercise, "weight_kg": 130, "reps": 5, "rir": 2},
        ],
    )

    suggestion = service.suggest_progressive_overload(exercise)

    assert suggestion.based_on_workout_date == date(2026, 1, 8)
    assert suggestion.status == "progress"
    assert suggestion.suggested_weight_kg == 132.5


def test_missing_rir_falls_back_to_reps_only_comparison() -> None:
    service = _service()
    exercise = _unique_exercise("Overhead Press No RIR")
    service.create_workout(
        workout_date=date(2026, 1, 1),
        name="Push",
        notes=None,
        sets=[
            {"exercise": exercise, "weight_kg": 40, "reps": 10, "rir": None},
            {"exercise": exercise, "weight_kg": 40, "reps": 10, "rir": None},
        ],
    )

    suggestion = service.suggest_progressive_overload(exercise)

    assert suggestion.status == "progress"
    assert suggestion.suggested_weight_kg == 42.5
    assert "not recorded" in suggestion.rationale
