import asyncio
from datetime import date
from pathlib import Path

import jwt
import pytest
from fastapi import HTTPException

from app.api import health
from app.services.health_ingest_service import HealthIngestService

METRICS_PAYLOAD = {
    "data": {
        "metrics": [
            {
                "name": "step_count",
                "units": "count",
                "data": [
                    {"date": "2026-08-10 07:00:00 +1000", "qty": 5123, "source": "iPhone"},
                    {"date": "2026-08-11 07:00:00 +1000", "qty": 6042, "source": "iPhone"},
                ],
            },
            {
                "name": "heart_rate_variability",
                "units": "ms",
                "data": [
                    {"date": "2026-08-11 06:30:00 +1000", "qty": 51.2, "source": "Apple Watch"},
                ],
            },
        ],
        "workouts": [
            {
                "id": "workout-1",
                "name": "Running",
                "start": "2026-08-11 06:00:00 +1000",
                "end": "2026-08-11 06:30:00 +1000",
                "duration": 1800,
                "distance": {"qty": 5200, "units": "m"},
                "activeEnergyBurned": {"qty": 410, "units": "kcal"},
                "heartRateData": [
                    {"qty": 140}, {"qty": 150}, {"qty": 160},
                ],
                "source": "Apple Watch",
            }
        ],
    }
}


def _service(tmp_path: Path) -> HealthIngestService:
    service = HealthIngestService(database_url=f"sqlite:///{tmp_path}/health.db")
    service.initialise()
    return service


def test_ingest_parses_metrics_and_workouts(tmp_path: Path) -> None:
    service = _service(tmp_path)

    result = service.ingest(METRICS_PAYLOAD, automation_id="auto-1", automation_name="SirisOS Health")

    assert result.accepted is True
    assert result.metric_samples_received == 3
    assert result.workouts_received == 1

    status = service.status()
    assert status.records_received == 4
    assert status.last_error is None
    assert status.last_sync is not None


def test_ingest_is_idempotent_for_identical_samples(tmp_path: Path) -> None:
    service = _service(tmp_path)

    service.ingest(METRICS_PAYLOAD)
    service.ingest(METRICS_PAYLOAD)

    status = service.status()
    assert status.records_received == 4


def test_ingest_workout_upserts_by_external_id(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(METRICS_PAYLOAD)

    amended = {
        "data": {
            "metrics": [],
            "workouts": [
                {
                    **METRICS_PAYLOAD["data"]["workouts"][0],
                    "duration": 1850,
                    "activeEnergyBurned": {"qty": 430, "units": "kcal"},
                }
            ],
        }
    }
    result = service.ingest(amended)

    assert result.workouts_received == 1
    status = service.status()
    assert status.records_received == 4  # replaced, not duplicated


def test_list_workouts_reads_back_ingested_workouts(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(METRICS_PAYLOAD)

    workouts = service.list_workouts()

    assert len(workouts) == 1
    workout = workouts[0]
    assert workout.external_id == "workout-1"
    assert workout.workout_type == "Running"
    assert workout.distance_m == 5200
    assert workout.duration_seconds == 1800
    assert workout.avg_hr == 150.0
    assert workout.max_hr == 160.0


def test_late_local_timestamp_does_not_shift_into_the_next_day(tmp_path: Path) -> None:
    # A regression guard: timestamps past ~2pm local were previously getting
    # double-shifted forward under SQLite (offset preserved instead of
    # normalised to UTC before storage, then re-added on read).
    service = _service(tmp_path)
    service.ingest(
        {
            "data": {
                "metrics": [],
                "workouts": [
                    {
                        "id": "late-workout",
                        "name": "Traditional Strength Training",
                        "start": "2026-08-18 18:00:00 +1000",
                        "duration": 2400,
                    }
                ],
            }
        }
    )

    workouts = service.list_workouts()

    assert len(workouts) == 1
    assert workouts[0].start_date == date(2026, 8, 18)


def test_list_workouts_since_filters_by_local_start_date(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(METRICS_PAYLOAD)  # workout starts 2026-08-11

    assert len(service.list_workouts(since=date(2026, 8, 11))) == 1
    assert len(service.list_workouts(since=date(2026, 8, 12))) == 0


def test_ingest_records_receipt_on_malformed_payload(tmp_path: Path) -> None:
    service = _service(tmp_path)

    result = service.ingest({"data": {"metrics": "not-a-list", "workouts": "not-a-list"}})

    assert result.accepted is True
    assert result.metric_samples_received == 0
    assert result.workouts_received == 0


def _admin_token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": health.AUTH_USERNAME, "iss": "sirisos-api"},
        health.JWT_SECRET,
        algorithm="HS256",
    )


def test_ingest_endpoint_requires_configured_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(health, "ingest_service", _service(tmp_path))
    monkeypatch.setattr(health, "HEALTH_INGEST_TOKEN", "")

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(health.ingest_health_data(METRICS_PAYLOAD, "Bearer anything"))
    assert excinfo.value.status_code == 401


def test_ingest_endpoint_rejects_wrong_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(health, "ingest_service", _service(tmp_path))
    monkeypatch.setattr(health, "HEALTH_INGEST_TOKEN", "correct-token")

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(health.ingest_health_data(METRICS_PAYLOAD, "Bearer wrong-token"))
    assert excinfo.value.status_code == 401


def test_ingest_endpoint_accepts_valid_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(health, "ingest_service", _service(tmp_path))
    monkeypatch.setattr(health, "HEALTH_INGEST_TOKEN", "correct-token")

    response = asyncio.run(
        health.ingest_health_data(
            METRICS_PAYLOAD,
            "Bearer correct-token",
            automation_id="auto-1",
            automation_name="SirisOS Health",
            session_id="session-1",
        )
    )

    assert response.accepted is True
    assert response.metric_samples_received == 3
    assert response.workouts_received == 1


def test_status_endpoint_requires_admin_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(health, "ingest_service", _service(tmp_path))

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(health.health_ingest_status(None))
    assert excinfo.value.status_code == 401


def test_status_endpoint_reports_sync_state(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path)
    service.ingest(METRICS_PAYLOAD)
    monkeypatch.setattr(health, "ingest_service", service)
    monkeypatch.setattr(health, "HEALTH_INGEST_TOKEN", "correct-token")

    response = asyncio.run(health.health_ingest_status(_admin_token()))

    assert response.configured is True
    assert response.records_received == 4
    assert response.last_error is None
    assert response.last_sync is not None


def test_ingest_endpoint_accepts_session_jwt_without_ingest_token(tmp_path: Path, monkeypatch) -> None:
    """The iOS app's HealthKit sync is already logged in and should be able to
    push without a separately configured SIRISOS_HEALTH_INGEST_TOKEN."""
    monkeypatch.setattr(health, "ingest_service", _service(tmp_path))
    monkeypatch.setattr(health, "HEALTH_INGEST_TOKEN", "")

    response = asyncio.run(
        health.ingest_health_data(METRICS_PAYLOAD, _admin_token())
    )

    assert response.accepted is True
    assert response.metric_samples_received == 3
    assert response.workouts_received == 1


def test_ingest_endpoint_rejects_other_users_jwt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(health, "ingest_service", _service(tmp_path))
    monkeypatch.setattr(health, "HEALTH_INGEST_TOKEN", "")
    other_user_token = "Bearer " + jwt.encode(
        {"sub": "someone-else", "iss": "sirisos-api"}, health.JWT_SECRET, algorithm="HS256"
    )

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(health.ingest_health_data(METRICS_PAYLOAD, other_user_token))
    assert excinfo.value.status_code == 401
