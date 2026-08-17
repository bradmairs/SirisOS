from datetime import date, datetime, timedelta, timezone
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


# All of these use explicit UTC datetimes rather than wall-clock "now" so
# local-day bucketing (Sydney, UTC+10/+11) can't flake near local midnight.


def test_cumulative_summary_sums_todays_samples(tmp_path: Path) -> None:
    service = _service(tmp_path)
    reference_now = datetime(2026, 3, 10, 5, 0, tzinfo=timezone.utc)  # 16:00 Sydney, 10 Mar
    service.ingest(_payload_at("step_count", "count", 2500, datetime(2026, 3, 10, 0, 30, tzinfo=timezone.utc)))
    service.ingest(_payload_at("step_count", "count", 3200, datetime(2026, 3, 10, 3, 0, tzinfo=timezone.utc)))
    service.ingest(_payload_at("step_count", "count", 1800, datetime(2026, 3, 10, 4, 30, tzinfo=timezone.utc)))

    summary = service.summary(now=reference_now)

    assert len(summary) == 1
    item = summary[0]
    assert item.metric_type == "step_count"
    assert item.latest_value == 7500


def test_utc_evening_sample_is_attributed_to_the_next_sydney_day(tmp_path: Path) -> None:
    # 22:00 UTC on 10 March is 09:00 on 11 March in Sydney (UTC+11 in March,
    # daylight saving still in effect) -- this sample must count toward the
    # 11th's total, not the 10th's, or steps taken late at night would be
    # silently lost from "today".
    service = _service(tmp_path)
    service.ingest(_payload_at("step_count", "count", 500, datetime(2026, 3, 10, 22, 0, tzinfo=timezone.utc)))

    reference_now_on_11th = datetime(2026, 3, 11, 3, 0, tzinfo=timezone.utc)  # 14:00 Sydney, 11 Mar
    summary = service.summary(now=reference_now_on_11th)

    assert summary[0].latest_value == 500


def test_baseline_averages_prior_days_totals_not_raw_samples(tmp_path: Path) -> None:
    service = _service(tmp_path)
    # Three prior days at 5000 steps/day (two samples each), then today at 8000.
    for day in (5, 6, 7):
        service.ingest(_payload_at("step_count", "count", 3000, datetime(2026, 3, day, 1, 0, tzinfo=timezone.utc)))
        service.ingest(_payload_at("step_count", "count", 2000, datetime(2026, 3, day, 3, 0, tzinfo=timezone.utc)))
    service.ingest(_payload_at("step_count", "count", 8000, datetime(2026, 3, 10, 1, 0, tzinfo=timezone.utc)))

    reference_now = datetime(2026, 3, 10, 5, 0, tzinfo=timezone.utc)
    summary = service.summary(baseline_days=14, now=reference_now)

    item = summary[0]
    assert item.latest_value == 8000
    assert item.baseline_sample_count == 3  # 3 prior days, not 6 samples
    assert item.baseline_average == 5000.0
    assert item.baseline_ratio == 160.0


def test_fewer_than_min_baseline_days_returns_no_ratio(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(_payload_at("step_count", "count", 4000, datetime(2026, 3, 8, 1, 0, tzinfo=timezone.utc)))
    service.ingest(_payload_at("step_count", "count", 5000, datetime(2026, 3, 10, 1, 0, tzinfo=timezone.utc)))

    reference_now = datetime(2026, 3, 10, 5, 0, tzinfo=timezone.utc)
    summary = service.summary(now=reference_now)

    item = summary[0]
    assert item.baseline_average is None
    assert item.baseline_ratio is None
    assert item.baseline_sample_count == 1


def test_point_in_time_metric_is_unaffected_by_cumulative_logic(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(_payload_at("resting_heart_rate", "bpm", 60, datetime(2026, 3, 10, 1, 0, tzinfo=timezone.utc)))
    service.ingest(_payload_at("resting_heart_rate", "bpm", 62, datetime(2026, 3, 10, 3, 0, tzinfo=timezone.utc)))

    reference_now = datetime(2026, 3, 10, 5, 0, tzinfo=timezone.utc)
    summary = service.summary(now=reference_now)

    # Not summed -- the latest single reading, exactly as before.
    assert summary[0].latest_value == 62


def test_daily_history_buckets_cumulative_metric_by_local_day(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(_payload_at("step_count", "count", 3000, datetime(2026, 3, 9, 1, 0, tzinfo=timezone.utc)))
    service.ingest(_payload_at("step_count", "count", 2000, datetime(2026, 3, 9, 3, 0, tzinfo=timezone.utc)))
    service.ingest(_payload_at("step_count", "count", 8000, datetime(2026, 3, 10, 1, 0, tzinfo=timezone.utc)))

    reference_now = datetime(2026, 3, 10, 5, 0, tzinfo=timezone.utc)
    history = service.daily_history("step_count", days=30, now=reference_now)

    by_day = {point.day: point.value for point in history}
    assert by_day[date(2026, 3, 9)] == 5000
    assert by_day[date(2026, 3, 10)] == 8000


def test_daily_history_respects_days_window(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(_payload_at("step_count", "count", 1000, datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)))
    service.ingest(_payload_at("step_count", "count", 2000, datetime(2026, 3, 10, 1, 0, tzinfo=timezone.utc)))

    reference_now = datetime(2026, 3, 10, 5, 0, tzinfo=timezone.utc)
    history = service.daily_history("step_count", days=7, now=reference_now)

    assert len(history) == 1
    assert history[0].value == 2000


def test_daily_history_for_unknown_metric_is_empty(tmp_path: Path) -> None:
    service = _service(tmp_path)

    assert service.daily_history("step_count") == []
