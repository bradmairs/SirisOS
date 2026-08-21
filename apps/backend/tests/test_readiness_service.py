from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.services.health_ingest_service import HealthIngestService
from app.services.readiness_service import ReadinessService


def _health_service(tmp_path: Path) -> HealthIngestService:
    service = HealthIngestService(database_url=f"sqlite:///{tmp_path}/readiness.db")
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


def _seed_baseline_days(health: HealthIngestService, *, metric: str, unit: str, value: float, days: range) -> None:
    # 08:00 UTC is 19:00 local (Melbourne, UTC+11 in March) -- same local
    # calendar day as the UTC date, so this lands HRV/other point-in-time
    # metrics squarely on bucket `day`.
    for day in days:
        health.ingest(_payload_at(metric, unit, value, datetime(2026, 3, day, 8, 0, tzinfo=timezone.utc)))


def _seed_sleep_bucket_days(health: HealthIngestService, *, value: float, days: range) -> None:
    # Sleep buckets to the wake day (see health_ingest_service's
    # _bucket_day), so a sample must be timed as a real bedtime to land in
    # bucket `day`: 11:00 UTC on `day - 1` is 22:00 local the evening
    # before `day` -- shifted back 12h that's local 10:00 on `day - 1`,
    # whose date plus one day is `day`.
    for day in days:
        health.ingest(_payload_at("sleep_analysis", "min", value, datetime(2026, 3, day - 1, 11, 0, tzinfo=timezone.utc)))


def test_score_is_none_without_enough_baseline_history(tmp_path: Path) -> None:
    health = _health_service(tmp_path)
    health.ingest(_payload_at("heart_rate_variability", "ms", 45, datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc)))
    service = ReadinessService(health_service=health)

    reference_now = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
    today = service.today(now=reference_now)

    assert today is not None
    assert today.score is None
    assert today.hrv_ratio is None


def test_score_at_baseline_is_one_hundred(tmp_path: Path) -> None:
    health = _health_service(tmp_path)
    _seed_baseline_days(health, metric="heart_rate_variability", unit="ms", value=50, days=range(1, 10))
    health.ingest(_payload_at("heart_rate_variability", "ms", 50, datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc)))
    service = ReadinessService(health_service=health)

    reference_now = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
    today = service.today(now=reference_now)

    assert today is not None
    assert today.hrv_ratio == 100.0
    assert today.score == 100


def test_hrv_and_sleep_on_the_same_day_are_averaged(tmp_path: Path) -> None:
    health = _health_service(tmp_path)
    _seed_baseline_days(health, metric="heart_rate_variability", unit="ms", value=50, days=range(1, 10))
    _seed_sleep_bucket_days(health, value=420, days=range(2, 10))
    # Day 10: below-baseline HRV, above-baseline sleep -- the two metrics
    # must genuinely combine, not one silently overriding the other.
    health.ingest(_payload_at("heart_rate_variability", "ms", 40, datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc)))
    health.ingest(_payload_at("sleep_analysis", "min", 480, datetime(2026, 3, 9, 11, 0, tzinfo=timezone.utc)))
    service = ReadinessService(health_service=health)

    reference_now = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
    today = service.today(now=reference_now)

    assert today is not None
    assert today.day == date(2026, 3, 10)
    assert today.hrv_ratio == 80.0
    assert today.sleep_ratio == 114.3  # 480 / 420 * 100, rounded
    assert today.score == 97  # round((80.0 + 114.3) / 2)


def test_score_falls_back_to_a_single_available_metric(tmp_path: Path) -> None:
    health = _health_service(tmp_path)
    _seed_baseline_days(health, metric="heart_rate_variability", unit="ms", value=50, days=range(1, 10))
    health.ingest(_payload_at("heart_rate_variability", "ms", 40, datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc)))
    service = ReadinessService(health_service=health)

    reference_now = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
    today = service.today(now=reference_now)

    assert today is not None
    assert today.sleep_ratio is None
    assert today.hrv_ratio == 80.0
    assert today.score == 80


def test_score_is_clamped_to_one_hundred(tmp_path: Path) -> None:
    health = _health_service(tmp_path)
    _seed_baseline_days(health, metric="heart_rate_variability", unit="ms", value=40, days=range(1, 10))
    health.ingest(_payload_at("heart_rate_variability", "ms", 200, datetime(2026, 3, 10, 8, 0, tzinfo=timezone.utc)))
    service = ReadinessService(health_service=health)

    reference_now = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
    today = service.today(now=reference_now)

    assert today is not None
    assert today.hrv_ratio == 500.0
    assert today.score == 100


def test_daily_history_returns_one_point_per_day_with_data(tmp_path: Path) -> None:
    health = _health_service(tmp_path)
    _seed_baseline_days(health, metric="heart_rate_variability", unit="ms", value=50, days=range(1, 12))
    service = ReadinessService(health_service=health)

    reference_now = datetime(2026, 3, 11, 20, 0, tzinfo=timezone.utc)
    history = service.daily_history(days=30, now=reference_now)

    days_with_scores = [point.day for point in history if point.score is not None]
    # The first MIN_BASELINE_POINTS(=3) days can never have a score --
    # there's no prior history yet to compare against.
    assert date(2026, 3, 4) in days_with_scores
    assert date(2026, 3, 1) not in days_with_scores


def test_no_data_at_all_returns_empty_history(tmp_path: Path) -> None:
    health = _health_service(tmp_path)
    service = ReadinessService(health_service=health)

    assert service.daily_history() == []
    assert service.today() is None
