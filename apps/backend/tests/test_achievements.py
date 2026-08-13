from datetime import date, timedelta
from pathlib import Path

from app.services.achievement_service import AchievementService
from app.services.gym_service import GymService
from app.services.running_service import RunningService

# Achievements are lifetime, unscoped by date -- every check looks at the
# entire history. Like the health/conflict-detection tests, this needs a
# fully isolated database per test rather than date-range isolation.


def _build(tmp_path: Path, monkeypatch) -> tuple[RunningService, GymService, AchievementService]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/achievements.db")
    running = RunningService()
    running.initialise()
    gym = GymService()
    gym.initialise()
    return running, gym, AchievementService(running_service=running, gym_service=gym)


def _find(achievements, achievement_id: str):
    return next(item for item in achievements if item.id == achievement_id)


def test_no_data_returns_all_locked(tmp_path: Path, monkeypatch) -> None:
    _, _, service = _build(tmp_path, monkeypatch)

    achievements = service.list_achievements()

    assert len(achievements) == 8
    assert all(not item.unlocked for item in achievements)
    assert all(item.achieved_date is None for item in achievements)


def test_weight_club_unlocks_at_threshold(tmp_path: Path, monkeypatch) -> None:
    _, gym, service = _build(tmp_path, monkeypatch)
    milestone_date = date(2026, 5, 1)

    gym.create_workout(
        workout_date=date(2026, 4, 1), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 90, "reps": 5, "rir": 2}],
    )
    gym.create_workout(
        workout_date=milestone_date, name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 100, "reps": 3, "rir": 1}],
    )

    bench = _find(service.list_achievements(), "bench_100_club")
    squat = _find(service.list_achievements(), "squat_100_club")

    assert bench.unlocked is True
    assert bench.achieved_date == milestone_date
    assert squat.unlocked is False
    assert "0" in squat.progress_label


def test_million_kilo_club_tracks_cumulative_volume(tmp_path: Path, monkeypatch) -> None:
    _, gym, service = _build(tmp_path, monkeypatch)

    # 5000 kg per workout; 200 workouts = 1,000,000 kg exactly.
    crossing_date = None
    total = 0.0
    for offset in range(200):
        workout_date = date(2020, 1, 1) + timedelta(days=offset)
        gym.create_workout(
            workout_date=workout_date, name="Push", notes=None,
            sets=[{"exercise": "Bench Press", "weight_kg": 100, "reps": 50, "rir": 2}],
        )
        total += 100 * 50
        if crossing_date is None and total >= 1_000_000:
            crossing_date = workout_date

    million = _find(service.list_achievements(), "million_kilo_club")

    assert million.unlocked is True
    assert million.achieved_date == crossing_date


def test_sub_25_5k_unlocks_on_qualifying_run(tmp_path: Path, monkeypatch) -> None:
    running, _, service = _build(tmp_path, monkeypatch)

    running.create_run(
        run_date=date(2026, 6, 1), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=310, average_heart_rate=160,
    )
    sub25 = _find(service.list_achievements(), "sub_25_5k")
    assert sub25.unlocked is False
    assert "need under 25:00" in sub25.progress_label

    running.create_run(
        run_date=date(2026, 6, 8), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=290, average_heart_rate=165,
    )
    sub25 = _find(service.list_achievements(), "sub_25_5k")
    assert sub25.unlocked is True
    assert sub25.achieved_date == date(2026, 6, 8)


def test_consistency_streak_ignores_current_incomplete_week(tmp_path: Path, monkeypatch) -> None:
    running, _, service = _build(tmp_path, monkeypatch)
    today = date(2026, 8, 13)  # Thursday
    current_week_monday = today - timedelta(days=today.weekday())

    # Only 1 day logged in the current (incomplete) week -- must not count
    # against or toward the streak.
    running.create_run(
        run_date=current_week_monday, run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=300, average_heart_rate=150,
    )

    achievements = service.list_achievements(today=today)
    consistency = _find(achievements, "consistency_streak")
    assert consistency.unlocked is False
    assert "0 / 8" in consistency.progress_label


def test_consistency_streak_unlocks_after_eight_qualifying_weeks(tmp_path: Path, monkeypatch) -> None:
    running, _, service = _build(tmp_path, monkeypatch)
    today = date(2026, 8, 13)
    current_week_monday = today - timedelta(days=today.weekday())

    for weeks_ago in range(1, 9):
        week_monday = current_week_monday - timedelta(weeks=weeks_ago)
        for day_offset in range(4):
            running.create_run(
                run_date=week_monday + timedelta(days=day_offset),
                run_type="outdoor", distance_km=5.0,
                average_pace_seconds_per_km=300, average_heart_rate=150,
            )

    achievements = service.list_achievements(today=today)
    consistency = _find(achievements, "consistency_streak")

    assert consistency.unlocked is True
    assert consistency.achieved_date is not None


def test_progressive_streak_unlocks_and_resets_on_non_improvement(tmp_path: Path, monkeypatch) -> None:
    _, gym, service = _build(tmp_path, monkeypatch)
    weights = [80, 82.5, 85, 85, 90, 92.5, 95, 97.5, 100]
    for index, weight in enumerate(weights):
        gym.create_workout(
            workout_date=date(2026, 1, 1) + timedelta(weeks=index),
            name="Push", notes=None,
            sets=[{"exercise": "Bench Press", "weight_kg": weight, "reps": 5, "rir": 2}],
        )

    progressive = _find(service.list_achievements(), "progressive_streak")

    # Streak breaks at index 3 (85 == 85, not an improvement), so the
    # qualifying run is indices 3..8 (85, 90, 92.5, 95, 97.5, 100) = 6 sessions.
    assert progressive.unlocked is True
    assert "Bench Press" in progressive.progress_label
    assert progressive.achieved_date == date(2026, 1, 1) + timedelta(weeks=7)
