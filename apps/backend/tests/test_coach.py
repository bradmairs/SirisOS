from datetime import date, timedelta
from pathlib import Path

from app.services.coach_service import CoachService
from app.services.gym_service import GymService
from app.services.running_service import RunningService
from app.services.training_load_service import TrainingLoadService

# Coach reports aggregate across all records in a date range and match
# exercises by name globally, so per-test isolation needs a genuinely
# separate database rather than unique names/dates within a shared one.
# Matches the tmp_path/monkeypatch pattern used by the
# health/conflict/achievement test suites.


def _monday(year: int, week_offset: int) -> date:
    anchor = date(year, 3, 1)
    anchor -= timedelta(days=anchor.weekday())
    return anchor + timedelta(weeks=week_offset)


def _services(tmp_path: Path, monkeypatch) -> tuple[RunningService, GymService, CoachService]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/coach.db")
    running = RunningService()
    running.initialise()
    gym = GymService()
    gym.initialise()
    training_load = TrainingLoadService(running_service=running, gym_service=gym)
    return running, gym, CoachService(
        running_service=running, gym_service=gym, training_load_service=training_load
    )


def test_first_ever_week_has_no_deltas(tmp_path: Path, monkeypatch) -> None:
    running, gym, coach = _services(tmp_path, monkeypatch)
    current_week = _monday(2026, 0)

    running.create_run(
        run_date=current_week,
        run_type="outdoor",
        distance_km=5.0,
        average_pace_seconds_per_km=300,
        average_heart_rate=150,
    )
    gym.create_workout(
        workout_date=current_week,
        name="Push",
        notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 60, "reps": 8, "rir": 2}],
    )

    report = coach.weekly_report(reference_date=current_week)

    assert report.running_distance_km == 5.0
    assert report.running_distance_km_delta is None
    assert report.gym_volume_kg == 480.0
    assert report.gym_volume_kg_delta is None
    assert report.run_count_delta is None
    assert report.gym_session_count_delta is None


def test_delta_compares_against_immediately_preceding_week(tmp_path: Path, monkeypatch) -> None:
    running, gym, coach = _services(tmp_path, monkeypatch)
    current_week = _monday(2026, 0)
    previous_week = current_week - timedelta(weeks=1)

    running.create_run(
        run_date=previous_week,
        run_type="outdoor",
        distance_km=5.0,
        average_pace_seconds_per_km=300,
        average_heart_rate=150,
    )
    running.create_run(
        run_date=current_week,
        run_type="outdoor",
        distance_km=8.0,
        average_pace_seconds_per_km=300,
        average_heart_rate=150,
    )

    report = coach.weekly_report(reference_date=current_week)

    assert report.running_distance_km == 8.0
    assert report.running_distance_km_delta == 3.0
    assert report.run_count == 1
    assert report.run_count_delta == 0


def test_improvement_detected_against_prior_history_not_first_ever_log(tmp_path: Path, monkeypatch) -> None:
    running, gym, coach = _services(tmp_path, monkeypatch)
    current_week = _monday(2026, 0)
    two_weeks_back = current_week - timedelta(weeks=2)
    bench = "Bench Press"
    cable_fly = "Cable Fly"

    gym.create_workout(
        workout_date=two_weeks_back,
        name="Push",
        notes=None,
        sets=[{"exercise": bench, "weight_kg": 80, "reps": 8, "rir": 2}],
    )
    gym.create_workout(
        workout_date=current_week,
        name="Heavy Push",
        notes=None,
        sets=[{"exercise": bench, "weight_kg": 90, "reps": 8, "rir": 2}],
    )
    # A brand-new exercise logged for the first time this week -- must not
    # appear as an "improvement" since there's nothing prior to beat.
    gym.create_workout(
        workout_date=current_week,
        name="Heavy Push",
        notes=None,
        sets=[{"exercise": cable_fly, "weight_kg": 20, "reps": 12, "rir": 2}],
    )

    report = coach.weekly_report(reference_date=current_week)

    exercises_improved = {item.exercise for item in report.improvements}
    assert bench in exercises_improved
    assert cable_fly not in exercises_improved
    weight_improvement = next(
        item for item in report.improvements if item.exercise == bench and item.record_type == "weight"
    )
    assert weight_improvement.value == 90
    assert weight_improvement.previous_value == 80
    assert f"New best on {bench}" in report.headline


def test_headline_falls_back_to_training_load_assessment_with_no_improvements(
    tmp_path: Path, monkeypatch
) -> None:
    _, _, coach = _services(tmp_path, monkeypatch)
    current_week = _monday(2026, 0)

    report = coach.weekly_report(reference_date=current_week)

    assert report.improvements == []
    assert report.headline == report.training_load.assessment
