from datetime import date, timedelta
from pathlib import Path

from app.services.gym_service import GymService
from app.services.running_service import RunningService
from app.services.training_load_service import TrainingLoadService

# Aggregates across all records rather than filtering by a per-test unique
# key, so this needs a genuinely isolated database -- same reasoning as
# test_training_load.py.


def _services(tmp_path: Path, monkeypatch) -> tuple[RunningService, GymService, TrainingLoadService]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/heatmap.db")
    running = RunningService()
    running.initialise()
    gym = GymService()
    gym.initialise()
    return running, gym, TrainingLoadService(running_service=running, gym_service=gym)


def test_no_data_returns_zero_intensity_for_every_day(tmp_path: Path, monkeypatch) -> None:
    _, _, training = _services(tmp_path, monkeypatch)
    reference = date(2026, 3, 1)

    results = training.daily_intensity(days=7, reference_date=reference)

    assert len(results) == 7
    assert all(item.intensity == 0.0 for item in results)
    assert results[-1].day == reference
    assert results[0].day == reference - timedelta(days=6)


def test_window_length_matches_requested_days(tmp_path: Path, monkeypatch) -> None:
    _, _, training = _services(tmp_path, monkeypatch)
    results = training.daily_intensity(days=14, reference_date=date(2026, 3, 1))
    assert len(results) == 14


def test_single_gym_day_is_its_own_all_time_max_and_scores_full_intensity(
    tmp_path: Path, monkeypatch
) -> None:
    running, gym, training = _services(tmp_path, monkeypatch)
    workout_day = date(2026, 3, 1)
    gym.create_workout(
        workout_date=workout_day, name="Push", notes=None,
        sets=[{"exercise": "Bench", "weight_kg": 80, "reps": 8, "rir": 2}],
    )

    results = training.daily_intensity(days=7, reference_date=workout_day)

    today = next(item for item in results if item.day == workout_day)
    assert today.gym_volume_kg == 640.0
    assert today.intensity == 1.0


def test_lighter_gym_day_scores_below_the_all_time_max_day(tmp_path: Path, monkeypatch) -> None:
    running, gym, training = _services(tmp_path, monkeypatch)
    heavy_day = date(2026, 2, 20)
    light_day = date(2026, 2, 27)
    gym.create_workout(
        workout_date=heavy_day, name="Push", notes=None,
        sets=[{"exercise": "Bench", "weight_kg": 100, "reps": 10, "rir": 2}],
    )
    gym.create_workout(
        workout_date=light_day, name="Push", notes=None,
        sets=[{"exercise": "Bench", "weight_kg": 50, "reps": 10, "rir": 2}],
    )

    results = training.daily_intensity(days=14, reference_date=date(2026, 3, 1))

    heavy = next(item for item in results if item.day == heavy_day)
    light = next(item for item in results if item.day == light_day)
    assert heavy.intensity == 1.0
    assert light.intensity == 0.5


def test_running_contribution_adds_to_gym_contribution_on_the_same_day(
    tmp_path: Path, monkeypatch
) -> None:
    running, gym, training = _services(tmp_path, monkeypatch)
    max_gym_day = date(2026, 2, 1)
    max_run_day = date(2026, 2, 8)
    combined_day = date(2026, 2, 15)

    # Establish each modality's own all-time max on separate days.
    gym.create_workout(
        workout_date=max_gym_day, name="Push", notes=None,
        sets=[{"exercise": "Bench", "weight_kg": 100, "reps": 10, "rir": 2}],
    )
    running.create_run(
        run_date=max_run_day, run_type="outdoor", distance_km=15.0,
        average_pace_seconds_per_km=270, average_heart_rate=150,
    )

    # A lighter gym session on its own, for comparison.
    gym.create_workout(
        workout_date=combined_day, name="Push", notes=None,
        sets=[{"exercise": "Bench", "weight_kg": 50, "reps": 10, "rir": 2}],
    )
    gym_only_results = training.daily_intensity(days=21, reference_date=combined_day)
    gym_only_intensity = next(item for item in gym_only_results if item.day == combined_day).intensity

    # Same gym session, now with an easy run added on the same day.
    running.create_run(
        run_date=combined_day, run_type="outdoor", distance_km=3.0,
        average_pace_seconds_per_km=420, average_heart_rate=120,
    )
    combined_results = training.daily_intensity(days=21, reference_date=combined_day)
    combined = next(item for item in combined_results if item.day == combined_day)

    assert combined.running_effort_score > 0
    assert combined.intensity > gym_only_intensity
    assert combined.intensity <= 1.0
