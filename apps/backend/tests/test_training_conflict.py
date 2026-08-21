from datetime import date, timedelta
from pathlib import Path

from app.services.gym_service import GymService
from app.services.health_ingest_service import HealthIngestService
from app.services.running_service import RunningService
from app.services.training_conflict_service import TrainingConflictService

# HealthIngestService.summary() aggregates globally with no per-test
# partition key (this is a genuinely single-user datastore, matching the
# rest of the app), so unlike the gym/running test isolation elsewhere, this
# suite needs a fully isolated database per test rather than random-year
# date scoping.


def _build(tmp_path: Path, monkeypatch) -> tuple[RunningService, GymService, HealthIngestService, TrainingConflictService]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/conflict.db")
    running = RunningService()
    running.initialise()
    gym = GymService()
    gym.initialise()
    health = HealthIngestService()
    health.initialise()
    conflict = TrainingConflictService(running_service=running, gym_service=gym, health_service=health)
    return running, gym, health, conflict


def _hrv_payload(entries: list[tuple[date, float]]) -> dict:
    return {
        "data": {
            "metrics": [
                {
                    "name": "heart_rate_variability",
                    "units": "ms",
                    "data": [
                        {"date": f"{d.isoformat()} 06:00:00 +0000", "qty": qty} for d, qty in entries
                    ],
                }
            ]
        }
    }


def test_no_health_data_is_insufficient(tmp_path: Path, monkeypatch) -> None:
    _, _, _, conflict = _build(tmp_path, monkeypatch)
    today = date(2026, 3, 10)

    result = conflict.check(reference_date=today)

    assert result.status == "insufficient_data"


def test_stale_health_data_is_insufficient(tmp_path: Path, monkeypatch) -> None:
    _, _, health, conflict = _build(tmp_path, monkeypatch)
    today = date(2026, 3, 10)
    old_day = today - timedelta(days=5)

    health.ingest(_hrv_payload([
        (old_day - timedelta(days=3), 50.0),
        (old_day - timedelta(days=2), 50.0),
        (old_day - timedelta(days=1), 50.0),
        (old_day, 50.0),
    ]))

    result = conflict.check(reference_date=today)

    assert result.status == "insufficient_data"


def test_evening_local_hrv_sample_matches_its_own_local_reference_day(tmp_path: Path, monkeypatch) -> None:
    # A sample timestamped late enough in UTC to already be the *next* local
    # calendar day (Melbourne, UTC+10/11) must still match reference_date --
    # comparing raw UTC .date() against a local reference_date silently
    # treated real, same-day data as "not synced for today" for roughly half
    # of every day.
    _, _, health, conflict = _build(tmp_path, monkeypatch)
    today = date(2026, 3, 10)

    health.ingest(_hrv_payload([
        (today - timedelta(days=4), 50.0),
        (today - timedelta(days=3), 50.0),
        (today - timedelta(days=2), 50.0),
    ]))
    # 20:30 UTC on the 9th is 07:30 local on the 10th (AEDT, UTC+11) --
    # genuinely "today's" morning HRV reading in Melbourne.
    health.ingest(
        {
            "data": {
                "metrics": [
                    {
                        "name": "heart_rate_variability",
                        "units": "ms",
                        "data": [{"date": "2026-03-09 20:30:00 +0000", "qty": 51.0}],
                    }
                ]
            }
        }
    )

    result = conflict.check(reference_date=today)

    assert result.status == "clear"


def test_normal_recovery_is_clear(tmp_path: Path, monkeypatch) -> None:
    _, gym, health, conflict = _build(tmp_path, monkeypatch)
    today = date(2026, 3, 10)

    health.ingest(_hrv_payload([
        (today - timedelta(days=4), 50.0),
        (today - timedelta(days=3), 50.0),
        (today - timedelta(days=2), 50.0),
        (today, 51.0),
    ]))
    gym.create_workout(
        workout_date=today, name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )

    result = conflict.check(reference_date=today)

    assert result.status == "clear"


def test_reduced_recovery_without_training_is_not_a_conflict(tmp_path: Path, monkeypatch) -> None:
    _, _, health, conflict = _build(tmp_path, monkeypatch)
    today = date(2026, 3, 10)

    health.ingest(_hrv_payload([
        (today - timedelta(days=4), 50.0),
        (today - timedelta(days=3), 50.0),
        (today - timedelta(days=2), 50.0),
        (today, 30.0),
    ]))

    result = conflict.check(reference_date=today)

    assert result.status == "reduced_recovery"
    assert result.trained is False
    assert "HRV" in result.reasons[0]


def test_reduced_recovery_with_gym_session_is_a_conflict(tmp_path: Path, monkeypatch) -> None:
    _, gym, health, conflict = _build(tmp_path, monkeypatch)
    today = date(2026, 3, 10)

    health.ingest(_hrv_payload([
        (today - timedelta(days=4), 50.0),
        (today - timedelta(days=3), 50.0),
        (today - timedelta(days=2), 50.0),
        (today, 30.0),
    ]))
    gym.create_workout(
        workout_date=today, name="Legs", notes=None,
        sets=[{"exercise": "Squat", "weight_kg": 100, "reps": 5, "rir": 2}],
    )

    result = conflict.check(reference_date=today)

    assert result.status == "conflict"
    assert result.trained is True
    assert "Legs" in result.session_summary
    assert "Legs" in result.guidance


def test_reduced_recovery_with_run_is_a_conflict(tmp_path: Path, monkeypatch) -> None:
    running, _, health, conflict = _build(tmp_path, monkeypatch)
    today = date(2026, 3, 10)

    health.ingest(_hrv_payload([
        (today - timedelta(days=4), 50.0),
        (today - timedelta(days=3), 50.0),
        (today - timedelta(days=2), 50.0),
        (today, 30.0),
    ]))
    running.create_run(
        run_date=today, run_type="outdoor", distance_km=8.0,
        average_pace_seconds_per_km=300, average_heart_rate=150,
    )

    result = conflict.check(reference_date=today)

    assert result.status == "conflict"
    assert "km run" in result.session_summary


def test_elevated_resting_heart_rate_triggers_conflict(tmp_path: Path, monkeypatch) -> None:
    _, gym, health, conflict = _build(tmp_path, monkeypatch)
    today = date(2026, 3, 10)

    health.ingest(
        {
            "data": {
                "metrics": [
                    {
                        "name": "resting_heart_rate",
                        "units": "bpm",
                        "data": [
                            {"date": f"{(today - timedelta(days=4)).isoformat()} 06:00:00 +0000", "qty": 58},
                            {"date": f"{(today - timedelta(days=3)).isoformat()} 06:00:00 +0000", "qty": 58},
                            {"date": f"{(today - timedelta(days=2)).isoformat()} 06:00:00 +0000", "qty": 58},
                            {"date": f"{today.isoformat()} 06:00:00 +0000", "qty": 70},
                        ],
                    }
                ]
            }
        }
    )
    gym.create_workout(
        workout_date=today, name="Push", notes=None,
        sets=[{"exercise": "Bench Press", "weight_kg": 80, "reps": 8, "rir": 2}],
    )

    result = conflict.check(reference_date=today)

    assert result.status == "conflict"
    assert "resting heart rate" in result.reasons[0]
