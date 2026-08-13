from datetime import date, timedelta
from pathlib import Path

from app.services.gym_service import GymService
from app.services.running_service import RunningService
from app.services.training_load_service import TrainingLoadService

# Weekly load aggregates across all records in a date range rather than
# filtering by exercise name, so per-test isolation needs a genuinely
# separate database (not just unique names/dates within a shared one) --
# otherwise another test's baseline-window data can silently pad these
# results. Matches the tmp_path/monkeypatch pattern used by the
# health/conflict/achievement test suites.


def _monday(year: int, week_offset: int) -> date:
    anchor = date(year, 3, 1)
    anchor -= timedelta(days=anchor.weekday())
    return anchor + timedelta(weeks=week_offset)


def _services(tmp_path: Path, monkeypatch) -> tuple[RunningService, GymService, TrainingLoadService]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/training_load.db")
    running = RunningService()
    running.initialise()
    gym = GymService()
    gym.initialise()
    return running, gym, TrainingLoadService(running_service=running, gym_service=gym)


def test_no_data_returns_zero_loads_and_no_ratio(tmp_path: Path, monkeypatch) -> None:
    _, _, training = _services(tmp_path, monkeypatch)
    current_week = _monday(2026, 0)

    result = training.weekly_load(reference_date=current_week)

    assert result.running_load == 0
    assert result.gym_load == 0
    assert result.running_ratio is None
    assert result.gym_ratio is None
    assert result.combined_index is None
    assert "Not enough" in result.assessment


def test_single_baseline_week_is_insufficient(tmp_path: Path, monkeypatch) -> None:
    _, gym, training = _services(tmp_path, monkeypatch)
    current_week = _monday(2026, 0)
    one_week_back = current_week - timedelta(weeks=1)

    gym.create_workout(
        workout_date=one_week_back,
        name="Legs",
        notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 5, "rir": 2}],
    )
    gym.create_workout(
        workout_date=current_week,
        name="Legs",
        notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 5, "rir": 2}],
    )

    result = training.weekly_load(reference_date=current_week)

    assert result.gym_baseline is None
    assert result.gym_ratio is None


def test_heavier_gym_week_flagged_against_full_baseline(tmp_path: Path, monkeypatch) -> None:
    _, gym, training = _services(tmp_path, monkeypatch)
    current_week = _monday(2026, 0)

    for offset in range(1, 9):
        gym.create_workout(
            workout_date=current_week - timedelta(weeks=offset),
            name="Baseline",
            notes=None,
            sets=[{"exercise": "Deadlift", "weight_kg": 100, "reps": 10, "rir": 2}],
        )
    gym.create_workout(
        workout_date=current_week,
        name="Heavy",
        notes=None,
        sets=[{"exercise": "Deadlift", "weight_kg": 200, "reps": 10, "rir": 2}],
    )

    result = training.weekly_load(reference_date=current_week)

    assert result.gym_baseline == 1000.0
    assert result.gym_ratio == 200.0
    assert result.combined_index == 200.0
    assert "Heavier" in result.assessment


def test_lighter_running_week_flagged_against_full_baseline(tmp_path: Path, monkeypatch) -> None:
    running, _, training = _services(tmp_path, monkeypatch)
    current_week = _monday(2026, 0)

    for offset in range(1, 9):
        running.create_run(
            run_date=current_week - timedelta(weeks=offset),
            run_type="outdoor",
            distance_km=10.0,
            average_pace_seconds_per_km=300,
            average_heart_rate=150,
        )
    running.create_run(
        run_date=current_week,
        run_type="outdoor",
        distance_km=1.0,
        average_pace_seconds_per_km=400,
        average_heart_rate=150,
    )

    result = training.weekly_load(reference_date=current_week)

    assert result.running_ratio is not None
    assert result.running_ratio < 70
    assert result.combined_index == result.running_ratio
    assert "Lighter" in result.assessment


def test_combined_index_sums_both_modalities(tmp_path: Path, monkeypatch) -> None:
    running, gym, training = _services(tmp_path, monkeypatch)
    current_week = _monday(2026, 0)

    for offset in range(1, 9):
        running.create_run(
            run_date=current_week - timedelta(weeks=offset),
            run_type="outdoor",
            distance_km=5.0,
            average_pace_seconds_per_km=300,
            average_heart_rate=150,
        )
        gym.create_workout(
            workout_date=current_week - timedelta(weeks=offset),
            name="Baseline",
            notes=None,
            sets=[{"exercise": "Bench", "weight_kg": 60, "reps": 10, "rir": 2}],
        )
    running.create_run(
        run_date=current_week,
        run_type="outdoor",
        distance_km=5.0,
        average_pace_seconds_per_km=300,
        average_heart_rate=150,
    )
    gym.create_workout(
        workout_date=current_week,
        name="Same",
        notes=None,
        sets=[{"exercise": "Bench", "weight_kg": 60, "reps": 10, "rir": 2}],
    )

    result = training.weekly_load(reference_date=current_week)

    assert result.running_ratio == 100.0
    assert result.gym_ratio == 100.0
    assert result.combined_index == 200.0
    assert "typical" in result.assessment.lower()


def test_recent_weekly_loads_returns_consecutive_weeks_in_order(tmp_path: Path, monkeypatch) -> None:
    _, _, training = _services(tmp_path, monkeypatch)
    current_week = _monday(2026, 0)

    results = training.recent_weekly_loads(weeks=3, reference_date=current_week)

    assert [item.week_start for item in results] == [
        current_week - timedelta(weeks=2),
        current_week - timedelta(weeks=1),
        current_week,
    ]
    assert results[-1].week_end == current_week + timedelta(days=6)
