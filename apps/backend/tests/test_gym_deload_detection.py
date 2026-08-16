import uuid
from datetime import date

from app.services.gym_service import GymService


def _unique_exercise(label: str) -> str:
    return f"{label} {uuid.uuid4().hex[:8]}"


def _service() -> GymService:
    service = GymService()
    service.initialise()
    return service


def _log(service: GymService, exercise: str, workout_date: date, weight_kg: float, reps: int, rir: int | None) -> None:
    service.create_workout(
        workout_date=workout_date,
        name="Push",
        notes=None,
        sets=[{"exercise": exercise, "weight_kg": weight_kg, "reps": reps, "rir": rir}],
    )


def test_no_sets_returns_insufficient_data() -> None:
    service = _service()
    suggestion = service.suggest_deload(_unique_exercise("Never Logged"))
    assert suggestion.status == "insufficient_data"
    assert suggestion.session_dates is None


def test_fewer_than_three_sessions_returns_insufficient_data() -> None:
    service = _service()
    exercise = _unique_exercise("Bench Press Short History")
    _log(service, exercise, date(2026, 1, 1), 80, 8, 2)
    _log(service, exercise, date(2026, 1, 8), 82.5, 8, 2)

    suggestion = service.suggest_deload(exercise)

    assert suggestion.status == "insufficient_data"
    assert "2 so far" in suggestion.rationale


def test_declining_e1rm_reps_and_rir_triggers_deload() -> None:
    service = _service()
    exercise = _unique_exercise("Bench Press Declining")
    _log(service, exercise, date(2026, 1, 1), 80, 8, 3)
    _log(service, exercise, date(2026, 1, 8), 80, 6, 1)
    _log(service, exercise, date(2026, 1, 15), 77.5, 5, 0)

    suggestion = service.suggest_deload(exercise)

    assert suggestion.status == "deload_recommended"
    assert suggestion.session_dates == [date(2026, 1, 1), date(2026, 1, 8), date(2026, 1, 15)]
    assert "2026-01-15" in suggestion.rationale


def test_steady_or_improving_sessions_do_not_trigger_deload() -> None:
    service = _service()
    exercise = _unique_exercise("Squat Progressing")
    _log(service, exercise, date(2026, 1, 1), 100, 5, 2)
    _log(service, exercise, date(2026, 1, 8), 102.5, 5, 2)
    _log(service, exercise, date(2026, 1, 15), 105, 5, 2)

    suggestion = service.suggest_deload(exercise)

    assert suggestion.status == "on_track"


def test_bounce_back_session_does_not_trigger_deload() -> None:
    service = _service()
    exercise = _unique_exercise("Deadlift Bounce")
    _log(service, exercise, date(2026, 1, 1), 140, 5, 2)
    _log(service, exercise, date(2026, 1, 8), 130, 4, 1)
    _log(service, exercise, date(2026, 1, 15), 140, 5, 2)

    suggestion = service.suggest_deload(exercise)

    assert suggestion.status == "on_track"


def test_only_uses_last_three_sessions() -> None:
    service = _service()
    exercise = _unique_exercise("Overhead Press History")
    _log(service, exercise, date(2026, 1, 1), 40, 10, 0)
    _log(service, exercise, date(2026, 1, 8), 40, 10, 0)
    _log(service, exercise, date(2026, 1, 15), 42.5, 10, 3)
    _log(service, exercise, date(2026, 1, 22), 42.5, 10, 3)
    _log(service, exercise, date(2026, 1, 29), 42.5, 10, 3)

    suggestion = service.suggest_deload(exercise)

    assert suggestion.status == "on_track"
    assert suggestion.session_dates == [date(2026, 1, 15), date(2026, 1, 22), date(2026, 1, 29)]


def test_missing_rir_for_one_session_falls_back_to_e1rm_and_reps() -> None:
    service = _service()
    exercise = _unique_exercise("Row Missing Rir")
    _log(service, exercise, date(2026, 1, 1), 60, 10, 2)
    _log(service, exercise, date(2026, 1, 8), 60, 8, None)
    _log(service, exercise, date(2026, 1, 15), 57.5, 6, 0)

    suggestion = service.suggest_deload(exercise)

    assert suggestion.status == "deload_recommended"
    assert "RIR wasn't recorded" in suggestion.rationale
