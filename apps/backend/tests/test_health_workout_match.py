from datetime import date, timedelta
from pathlib import Path

from app.services.gym_service import GymService
from app.services.health_ingest_service import HealthIngestService
from app.services.health_workout_match_service import HealthWorkoutMatchService
from app.services.running_service import RunningService

# Matching reads across health/gym/running data by date, unscoped by exercise
# or run name, so this needs a fully isolated database per test -- same
# reasoning as the other cross-service suites (training conflict, ask siris).


def _build(tmp_path: Path, monkeypatch) -> tuple[HealthIngestService, GymService, RunningService, HealthWorkoutMatchService]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/workout_match.db")
    health = HealthIngestService()
    health.initialise()
    gym = GymService()
    gym.initialise()
    running = RunningService()
    running.initialise()
    service = HealthWorkoutMatchService(health_service=health, gym_service=gym, running_service=running)
    return health, gym, running, service


def _health_payload(*, workout_id: str, name: str, start: str) -> dict:
    return {
        "data": {
            "metrics": [],
            "workouts": [
                {
                    "id": workout_id,
                    "name": name,
                    "start": start,
                    "duration": 1800,
                    "distance": {"qty": 5000, "units": "m"},
                    "source": "Apple Watch",
                }
            ],
        }
    }


def test_no_health_workouts_gives_empty_list(tmp_path: Path, monkeypatch) -> None:
    _, _, _, service = _build(tmp_path, monkeypatch)

    assert service.list_unlogged_workouts(today=date(2026, 8, 15)) == []


def test_running_workout_with_no_matching_run_is_flagged(tmp_path: Path, monkeypatch) -> None:
    health, _, _, service = _build(tmp_path, monkeypatch)
    health.ingest(_health_payload(workout_id="w1", name="Running", start="2026-08-11 06:00:00 +1000"))

    unlogged = service.list_unlogged_workouts(today=date(2026, 8, 15))

    assert len(unlogged) == 1
    assert unlogged[0].category == "running"
    assert unlogged[0].start_date == date(2026, 8, 11)


def test_running_workout_matched_by_same_date_run_is_not_flagged(tmp_path: Path, monkeypatch) -> None:
    health, _, running, service = _build(tmp_path, monkeypatch)
    health.ingest(_health_payload(workout_id="w1", name="Running", start="2026-08-11 06:00:00 +1000"))
    running.create_run(
        run_date=date(2026, 8, 11), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=300, average_heart_rate=150,
    )

    assert service.list_unlogged_workouts(today=date(2026, 8, 15)) == []


def test_strength_workout_with_no_matching_gym_session_is_flagged(tmp_path: Path, monkeypatch) -> None:
    health, _, _, service = _build(tmp_path, monkeypatch)
    health.ingest(
        _health_payload(workout_id="w2", name="Traditional Strength Training", start="2026-08-12 06:00:00 +1000")
    )

    unlogged = service.list_unlogged_workouts(today=date(2026, 8, 15))

    assert len(unlogged) == 1
    assert unlogged[0].category == "strength"


def test_strength_workout_matched_by_same_date_gym_session_is_not_flagged(tmp_path: Path, monkeypatch) -> None:
    health, gym, _, service = _build(tmp_path, monkeypatch)
    health.ingest(
        _health_payload(workout_id="w2", name="Traditional Strength Training", start="2026-08-12 06:00:00 +1000")
    )
    gym.create_workout(
        workout_date=date(2026, 8, 12), name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )

    assert service.list_unlogged_workouts(today=date(2026, 8, 15)) == []


def test_unrecognised_workout_type_is_never_flagged(tmp_path: Path, monkeypatch) -> None:
    # Walking has nowhere to be "logged" in SirisOS -- flagging it as missing
    # would be misleading, not helpful.
    health, _, _, service = _build(tmp_path, monkeypatch)
    health.ingest(_health_payload(workout_id="w3", name="Walking", start="2026-08-13 06:00:00 +1000"))

    assert service.list_unlogged_workouts(today=date(2026, 8, 15)) == []


def test_workout_outside_the_lookback_window_is_excluded(tmp_path: Path, monkeypatch) -> None:
    health, _, _, service = _build(tmp_path, monkeypatch)
    today = date(2026, 8, 15)
    old_start = (today - timedelta(days=40)).strftime("%Y-%m-%d") + " 06:00:00 +1000"
    health.ingest(_health_payload(workout_id="w4", name="Running", start=old_start))

    assert service.list_unlogged_workouts(today=today, lookback_days=30) == []
