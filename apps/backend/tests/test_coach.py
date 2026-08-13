from datetime import date, timedelta
import random
import uuid

from app.services.coach_service import CoachService
from app.services.gym_service import GymService
from app.services.running_service import RunningService
from app.services.training_load_service import TrainingLoadService

# Same per-test far-future-year isolation as test_training_load.py -- deltas
# are computed against "the immediately preceding week", so a fixed literal
# year would accumulate stale data across repeated local test runs and a
# shared year across tests could bleed into each other's "previous week".
# Exercise names still need the "_unique_exercise" pattern from the gym tests
# on top of that, though: improvement detection matches by exercise name
# globally (not scoped to a date range), so a repeated literal name like
# "Bench Press" would compare against whatever weight a previous run of this
# same test already logged under that name, in some other random year.


def _random_year() -> int:
    return random.randint(4000, 5999)


def _unique_exercise(label: str) -> str:
    return f"{label} {uuid.uuid4().hex[:8]}"


def _monday(year: int, week_offset: int) -> date:
    anchor = date(year, 3, 1)
    anchor -= timedelta(days=anchor.weekday())
    return anchor + timedelta(weeks=week_offset)


def _services() -> tuple[RunningService, GymService, CoachService]:
    running = RunningService()
    running.initialise()
    gym = GymService()
    gym.initialise()
    training_load = TrainingLoadService(running_service=running, gym_service=gym)
    return running, gym, CoachService(
        running_service=running, gym_service=gym, training_load_service=training_load
    )


def test_first_ever_week_has_no_deltas(tmp_path, monkeypatch) -> None:
    # Needs a genuinely empty history, not just a fresh date range -- the
    # shared dev/test database already has old records from other tests,
    # which would otherwise count as legitimate prior data and produce a
    # real (non-None) delta. Same isolation approach as
    # test_training_load.py::test_single_baseline_week_is_insufficient.
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/isolated.sqlite3")
    running = RunningService()
    running.initialise()
    gym = GymService()
    gym.initialise()
    coach = CoachService(
        running_service=running,
        gym_service=gym,
        training_load_service=TrainingLoadService(running_service=running, gym_service=gym),
    )
    current_week = _monday(_random_year(), 0)

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


def test_delta_compares_against_immediately_preceding_week() -> None:
    running, gym, coach = _services()
    current_week = _monday(_random_year(), 0)
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


def test_improvement_detected_against_prior_history_not_first_ever_log() -> None:
    running, gym, coach = _services()
    current_week = _monday(_random_year(), 0)
    two_weeks_back = current_week - timedelta(weeks=2)
    bench = _unique_exercise("Bench Press")
    cable_fly = _unique_exercise("Cable Fly")

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


def test_headline_falls_back_to_training_load_assessment_with_no_improvements() -> None:
    _, _, coach = _services()
    current_week = _monday(_random_year(), 0)

    report = coach.weekly_report(reference_date=current_week)

    assert report.improvements == []
    assert report.headline == report.training_load.assessment
