from datetime import date
from pathlib import Path

from app.services.running_service import RunningService

# Personal records aggregate across all runs, not scoped by any per-test
# unique key, so this needs a genuinely isolated database per test rather
# than relying on unique names -- same reasoning as test_training_load.py.


def _service(tmp_path: Path, monkeypatch) -> RunningService:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/running_records.db")
    service = RunningService()
    service.initialise()
    return service


def test_first_run_ever_sets_no_records(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)

    _, records = service.create_run(
        run_date=date(2026, 1, 1), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=300, average_heart_rate=150,
    )

    assert records == []


def test_longer_run_sets_longest_run_record(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_run(
        run_date=date(2026, 1, 1), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=300, average_heart_rate=150,
    )

    _, records = service.create_run(
        run_date=date(2026, 1, 8), run_type="outdoor", distance_km=8.0,
        average_pace_seconds_per_km=310, average_heart_rate=155,
    )

    assert len(records) == 1
    record = records[0]
    assert record.record_type == "longest_run"
    assert record.value == 8.0
    assert record.previous_value == 5.0


def test_shorter_run_does_not_set_longest_run_record(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_run(
        run_date=date(2026, 1, 1), run_type="outdoor", distance_km=10.0,
        average_pace_seconds_per_km=300, average_heart_rate=150,
    )

    _, records = service.create_run(
        run_date=date(2026, 1, 8), run_type="outdoor", distance_km=6.0,
        average_pace_seconds_per_km=300, average_heart_rate=150,
    )

    assert records == []


def test_lower_heart_rate_at_comparable_pace_sets_record(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_run(
        run_date=date(2026, 1, 1), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=300, average_heart_rate=160,
    )

    _, records = service.create_run(
        run_date=date(2026, 1, 8), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=305, average_heart_rate=152,
    )

    assert len(records) == 1
    record = records[0]
    assert record.record_type == "lowest_heart_rate_at_pace"
    assert record.value == 152.0
    assert record.previous_value == 160.0
    assert record.pace_seconds_per_km == 305


def test_higher_heart_rate_at_comparable_pace_does_not_set_record(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_run(
        run_date=date(2026, 1, 1), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=300, average_heart_rate=150,
    )

    _, records = service.create_run(
        run_date=date(2026, 1, 8), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=305, average_heart_rate=158,
    )

    assert records == []


def test_pace_outside_tolerance_is_not_compared(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_run(
        run_date=date(2026, 1, 1), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=300, average_heart_rate=140,
    )

    # Much slower pace (60s/km slower) -- even a very low heart rate here
    # shouldn't be compared against the faster run's heart rate.
    _, records = service.create_run(
        run_date=date(2026, 1, 8), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=360, average_heart_rate=120,
    )

    assert records == []


def test_both_records_can_fire_together(tmp_path: Path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch)
    service.create_run(
        run_date=date(2026, 1, 1), run_type="outdoor", distance_km=5.0,
        average_pace_seconds_per_km=300, average_heart_rate=160,
    )

    _, records = service.create_run(
        run_date=date(2026, 1, 8), run_type="outdoor", distance_km=10.0,
        average_pace_seconds_per_km=305, average_heart_rate=155,
    )

    record_types = {record.record_type for record in records}
    assert record_types == {"longest_run", "lowest_heart_rate_at_pace"}
