from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.health_ingest_service import HealthIngestService


def _service(tmp_path: Path) -> HealthIngestService:
    service = HealthIngestService(database_url=f"sqlite:///{tmp_path}/health.db")
    service.initialise()
    return service


def _payload_at(name: str, unit: str, qty: float, when: datetime) -> dict:
    return {
        "data": {
            "metrics": [
                {
                    "name": name,
                    "units": unit,
                    "data": [{"date": when.strftime("%Y-%m-%d %H:%M:%S +0000"), "qty": qty}],
                }
            ]
        }
    }


def test_snapshot_with_no_data_is_unavailable(tmp_path: Path) -> None:
    service = _service(tmp_path)

    snapshot = service.snapshot()

    assert snapshot.available is False
    assert snapshot.endpoint_configured is False
    assert snapshot.metrics == []
    assert snapshot.error is not None


def test_snapshot_is_available_for_recent_samples(tmp_path: Path) -> None:
    service = _service(tmp_path)
    now = datetime.now(timezone.utc)
    service.ingest(_payload_at("step_count", "count", 6000, now - timedelta(hours=2)))
    service.ingest(_payload_at("resting_heart_rate", "bpm", 58, now - timedelta(hours=1)))

    snapshot = service.snapshot()

    assert snapshot.available is True
    assert snapshot.endpoint_configured is True
    assert snapshot.error is None
    assert {m.name for m in snapshot.metrics} == {"step_count", "resting_heart_rate"}
    assert sorted(snapshot.tools) == ["resting_heart_rate", "step_count"]


def test_snapshot_is_stale_when_newest_sample_is_old(tmp_path: Path) -> None:
    service = _service(tmp_path)
    now = datetime.now(timezone.utc)
    service.ingest(_payload_at("step_count", "count", 6000, now - timedelta(hours=72)))

    snapshot = service.snapshot()

    assert snapshot.available is False
    assert snapshot.endpoint_configured is True
    assert snapshot.error is not None
    assert len(snapshot.metrics) == 1


def test_snapshot_reports_latest_value_per_metric_type(tmp_path: Path) -> None:
    service = _service(tmp_path)
    now = datetime.now(timezone.utc)
    service.ingest(_payload_at("step_count", "count", 4000, now - timedelta(hours=5)))
    service.ingest(_payload_at("step_count", "count", 7000, now - timedelta(hours=1)))

    snapshot = service.snapshot()

    assert len(snapshot.metrics) == 1
    assert snapshot.metrics[0].value == 7000
