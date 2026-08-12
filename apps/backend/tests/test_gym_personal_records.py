import uuid
from datetime import date

from app.services.gym_service import GymService


def _unique_exercise(label: str) -> str:
    return f"{label} {uuid.uuid4().hex[:8]}"


def _service() -> GymService:
    service = GymService()
    service.initialise()
    return service


def test_first_ever_log_of_an_exercise_is_not_a_record() -> None:
    service = _service()
    exercise = _unique_exercise("Bench Press")
    _, records = service.create_workout(
        workout_date=date(2026, 1, 1),
        name="Push",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 60, "reps": 8, "rir": 2}],
    )
    assert records == []


def test_heavier_weight_than_prior_best_is_a_weight_record() -> None:
    service = _service()
    exercise = _unique_exercise("Bench Press")
    service.create_workout(
        workout_date=date(2026, 1, 1),
        name="Push",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 80, "reps": 5, "rir": 2}],
    )

    _, records = service.create_workout(
        workout_date=date(2026, 1, 8),
        name="Push",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 82.5, "reps": 5, "rir": 2}],
    )

    weight_records = [item for item in records if item.record_type == "weight"]
    assert len(weight_records) == 1
    assert weight_records[0].value == 82.5
    assert weight_records[0].previous_value == 80


def test_equal_or_lighter_weight_is_not_a_record() -> None:
    service = _service()
    exercise = _unique_exercise("Bench Press")
    service.create_workout(
        workout_date=date(2026, 1, 1),
        name="Push",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 80, "reps": 5, "rir": 2}],
    )

    _, records = service.create_workout(
        workout_date=date(2026, 1, 8),
        name="Push",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 80, "reps": 5, "rir": 2}],
    )

    assert records == []


def test_multiple_sets_only_report_the_sessions_best_per_record_type() -> None:
    service = _service()
    exercise = _unique_exercise("Bench Press")
    service.create_workout(
        workout_date=date(2026, 1, 1),
        name="Push",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 80, "reps": 5, "rir": 2}],
    )

    _, records = service.create_workout(
        workout_date=date(2026, 1, 8),
        name="Push",
        notes=None,
        sets=[
            {"exercise": exercise, "weight_kg": 82.5, "reps": 5, "rir": 2},
            {"exercise": exercise, "weight_kg": 85, "reps": 5, "rir": 1},
            {"exercise": exercise, "weight_kg": 80, "reps": 8, "rir": 2},
        ],
    )

    weight_records = [item for item in records if item.record_type == "weight"]
    assert len(weight_records) == 1
    assert weight_records[0].value == 85


def test_higher_estimated_one_rep_max_is_recorded_even_at_lower_weight() -> None:
    service = _service()
    exercise = _unique_exercise("Deadlift")
    service.create_workout(
        workout_date=date(2026, 1, 1),
        name="Pull",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 140, "reps": 1, "rir": 0}],
    )

    _, records = service.create_workout(
        workout_date=date(2026, 1, 8),
        name="Pull",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": 130, "reps": 5, "rir": 1}],
    )

    types = {item.record_type for item in records}
    assert "weight" not in types
    assert "estimated_one_rep_max" in types


def test_records_are_isolated_per_exercise() -> None:
    service = _service()
    bench = _unique_exercise("Bench Press")
    squat = _unique_exercise("Squat")
    service.create_workout(
        workout_date=date(2026, 1, 1),
        name="Full body",
        notes=None,
        sets=[
            {"exercise": bench, "weight_kg": 80, "reps": 5, "rir": 2},
            {"exercise": squat, "weight_kg": 100, "reps": 5, "rir": 2},
        ],
    )

    _, records = service.create_workout(
        workout_date=date(2026, 1, 8),
        name="Full body",
        notes=None,
        sets=[
            {"exercise": bench, "weight_kg": 82.5, "reps": 5, "rir": 2},
            {"exercise": squat, "weight_kg": 95, "reps": 5, "rir": 2},
        ],
    )

    exercises_with_records = {item.exercise for item in records}
    assert exercises_with_records == {bench}
