from datetime import date, timedelta
from pathlib import Path

from app.services.gym_service import GymService
from app.services.running_service import RunningService
from app.services.training_level_service import TrainingLevelService

# training_level() aggregates lifetime gym/run history plus weekly buckets,
# not scoped by exercise/run name, so it needs a fully isolated database per
# test -- same reasoning as the achievement/muscle-group-fatigue suites.


def _monday(year: int, week_offset: int) -> date:
    anchor = date(year, 3, 1)
    anchor -= timedelta(days=anchor.weekday())
    return anchor + timedelta(weeks=week_offset)


def _build(tmp_path: Path, monkeypatch) -> tuple[RunningService, GymService, TrainingLevelService]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/training_level.db")
    running = RunningService()
    running.initialise()
    gym = GymService()
    gym.initialise()
    return running, gym, TrainingLevelService(running_service=running, gym_service=gym)


def _dimension(dimensions, name: str):
    return next(item for item in dimensions if item.dimension == name)


def test_no_data_gives_no_dimensions_and_no_overall(tmp_path: Path, monkeypatch) -> None:
    _, _, service = _build(tmp_path, monkeypatch)

    level = service.training_level(today=_monday(2026, 10))

    assert level.overall_score is None
    assert all(item.score is None for item in level.dimensions)
    assert {item.dimension for item in level.dimensions} == {"strength", "endurance", "consistency"}


def test_strength_dimension_reuses_strength_score(tmp_path: Path, monkeypatch) -> None:
    _, gym, service = _build(tmp_path, monkeypatch)
    gym.create_workout(
        workout_date=date(2026, 6, 1), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )
    gym.tag_exercise("Bench Press", "chest")

    level = service.training_level(today=_monday(2026, 10))
    strength = _dimension(level.dimensions, "strength")

    assert strength.score == 100.0
    assert strength.score == round(gym.strength_score().overall_score * 100, 1)


def test_endurance_dimension_uses_latest_run_fitness_score(tmp_path: Path, monkeypatch) -> None:
    running, _, service = _build(tmp_path, monkeypatch)
    running.create_run(
        run_date=date(2026, 6, 1), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=300, average_heart_rate=160,
    )
    running.create_run(
        run_date=date(2026, 6, 8), run_type="outdoor", distance_km=6.0,
        average_pace_seconds_per_km=290, average_heart_rate=158,
    )

    level = service.training_level(today=_monday(2026, 10))
    endurance = _dimension(level.dimensions, "endurance")

    latest_fitness = running.list_runs()[0].fitness_score
    assert endurance.score == round(latest_fitness, 1)


def test_consistency_needs_at_least_two_baseline_weeks(tmp_path: Path, monkeypatch) -> None:
    # Only one qualifying baseline week exists (plus the "current" reading
    # week) -- not enough to call it a trend yet.
    _, gym, service = _build(tmp_path, monkeypatch)
    today = _monday(2026, 10)
    gym.create_workout(
        workout_date=today - timedelta(weeks=2), name="Legs", notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 5, "rir": 2}],
    )
    gym.create_workout(
        workout_date=today - timedelta(weeks=1), name="Legs", notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 5, "rir": 2}],
    )

    level = service.training_level(today=today)
    consistency = _dimension(level.dimensions, "consistency")

    assert consistency.score is None


def test_consistency_scores_last_full_week_against_its_own_baseline(tmp_path: Path, monkeypatch) -> None:
    _, gym, service = _build(tmp_path, monkeypatch)
    today = _monday(2026, 10)

    # Three baseline weeks (4 weeks ago, 3 weeks ago, 2 weeks ago) at 2
    # training days each -> baseline average = 2.0.
    for weeks_ago in (4, 3, 2):
        week_start = today - timedelta(weeks=weeks_ago)
        for day_offset in (0, 2):
            gym.create_workout(
                workout_date=week_start + timedelta(days=day_offset), name="Session", notes=None,
                sets=[{"exercise": "Bench Press", "weight_kg": 60, "reps": 8, "rir": 2}],
            )
    # Last full week (1 week ago): 3 training days -> ratio 3/2 = 1.5,
    # clamped to 100%.
    last_week_start = today - timedelta(weeks=1)
    for day_offset in (0, 1, 2):
        gym.create_workout(
            workout_date=last_week_start + timedelta(days=day_offset), name="Session", notes=None,
            sets=[{"exercise": "Bench Press", "weight_kg": 60, "reps": 8, "rir": 2}],
        )

    level = service.training_level(today=today)
    consistency = _dimension(level.dimensions, "consistency")

    assert consistency.score == 100.0
    assert "3 training days last week" in consistency.detail
    assert "2.0-day trailing average" in consistency.detail


def test_consistency_reflects_a_lighter_week_below_100_percent(tmp_path: Path, monkeypatch) -> None:
    _, gym, service = _build(tmp_path, monkeypatch)
    today = _monday(2026, 10)

    for weeks_ago in (4, 3, 2):
        week_start = today - timedelta(weeks=weeks_ago)
        for day_offset in (0, 1, 2, 3):
            gym.create_workout(
                workout_date=week_start + timedelta(days=day_offset), name="Session", notes=None,
                sets=[{"exercise": "Bench Press", "weight_kg": 60, "reps": 8, "rir": 2}],
            )
    # Baseline average = 4.0. Last full week: only 2 training days -> 50%.
    last_week_start = today - timedelta(weeks=1)
    for day_offset in (0, 1):
        gym.create_workout(
            workout_date=last_week_start + timedelta(days=day_offset), name="Session", notes=None,
            sets=[{"exercise": "Bench Press", "weight_kg": 60, "reps": 8, "rir": 2}],
        )

    level = service.training_level(today=today)
    consistency = _dimension(level.dimensions, "consistency")

    assert consistency.score == 50.0


def test_overall_averages_only_the_dimensions_with_data(tmp_path: Path, monkeypatch) -> None:
    _, gym, service = _build(tmp_path, monkeypatch)
    gym.create_workout(
        workout_date=date(2026, 6, 1), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )
    gym.tag_exercise("Bench Press", "chest")
    # No runs logged, no full weekly history -- endurance and consistency
    # both stay None.

    level = service.training_level(today=_monday(2026, 10))

    strength = _dimension(level.dimensions, "strength")
    assert _dimension(level.dimensions, "endurance").score is None
    assert _dimension(level.dimensions, "consistency").score is None
    assert level.overall_score == strength.score
