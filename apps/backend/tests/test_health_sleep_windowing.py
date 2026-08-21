from datetime import date, datetime, timezone
from pathlib import Path

from app.services.health_ingest_service import HealthIngestService

# Melbourne is UTC+11 (AEDT) in March -- matches the same convention already
# used in test_health_daily_totals.py so both suites reason about the same
# real offset.


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


def test_a_single_nights_sleep_spanning_midnight_lands_on_one_wake_day(tmp_path: Path) -> None:
    service = _service(tmp_path)
    # Bedtime segment: 23:30 local on the 10th (before midnight).
    service.ingest(_payload_at("sleep_analysis", "min", 240, datetime(2026, 3, 10, 12, 30, tzinfo=timezone.utc)))
    # Pre-wake segment: 06:45 local on the 11th (after midnight, same night).
    service.ingest(_payload_at("sleep_analysis", "min", 200, datetime(2026, 3, 10, 19, 45, tzinfo=timezone.utc)))

    reference_now = datetime(2026, 3, 10, 22, 0, tzinfo=timezone.utc)  # 09:00 local on the 11th
    summary = service.summary(now=reference_now)

    assert len(summary) == 1
    item = summary[0]
    assert item.metric_type == "sleep_analysis"
    # Both segments of the same night must be summed together, not split
    # across the 10th and the 11th by raw local calendar day.
    assert item.latest_value == 440


def test_todays_sleep_summary_includes_last_evenings_pre_midnight_samples(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ingest(_payload_at("sleep_analysis", "min", 300, datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)))

    reference_now = datetime(2026, 3, 10, 21, 0, tzinfo=timezone.utc)  # 08:00 local on the 11th, still asleep-ish
    summary = service.summary(now=reference_now)

    # Checking "today" (the 11th local) must already see last night's
    # pre-midnight sleep -- this is exactly the "sleep from the night before
    # isn't showing" bug.
    assert summary[0].latest_value == 300


def test_daily_history_buckets_sleep_by_wake_day_not_sample_day(tmp_path: Path) -> None:
    service = _service(tmp_path)
    # Night of the 9th->10th: one segment each side of local midnight.
    service.ingest(_payload_at("sleep_analysis", "min", 180, datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)))
    service.ingest(_payload_at("sleep_analysis", "min", 220, datetime(2026, 3, 9, 19, 0, tzinfo=timezone.utc)))
    # Night of the 10th->11th.
    service.ingest(_payload_at("sleep_analysis", "min", 400, datetime(2026, 3, 10, 13, 0, tzinfo=timezone.utc)))

    reference_now = datetime(2026, 3, 11, 5, 0, tzinfo=timezone.utc)
    history = service.daily_history("sleep_analysis", days=30, now=reference_now)

    by_day = {point.day: point.value for point in history}
    assert by_day[date(2026, 3, 10)] == 400  # the 9th->10th night, attributed to the 10th (wake day)
    assert by_day[date(2026, 3, 11)] == 400
    assert date(2026, 3, 9) not in by_day  # nothing should land on the pre-midnight sample's own local day


def test_last_nights_sleep_total_stays_visible_through_the_evening(tmp_path: Path) -> None:
    # A noon cutoff would make "today's sleep" silently reset to 0 mid-
    # afternoon, hours before that night's sleep has even started. Checking
    # right up until 20:00 local must still show the completed night.
    service = _service(tmp_path)
    service.ingest(_payload_at("sleep_analysis", "min", 300, datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)))

    reference_now = datetime(2026, 3, 11, 8, 30, tzinfo=timezone.utc)  # 19:30 local on the 11th
    summary = service.summary(now=reference_now)

    assert summary[0].latest_value == 300


def test_non_sleep_cumulative_metrics_still_use_plain_calendar_day(tmp_path: Path) -> None:
    # Regression guard: the wake-day shift is sleep-specific and must not
    # leak into steps/active-energy bucketing.
    service = _service(tmp_path)
    service.ingest(_payload_at("step_count", "count", 500, datetime(2026, 3, 10, 12, 30, tzinfo=timezone.utc)))

    reference_now = datetime(2026, 3, 10, 12, 45, tzinfo=timezone.utc)  # still 23:45 local on the 10th
    summary = service.summary(now=reference_now)

    # 12:30 UTC on the 10th is 23:30 local on the 10th -- still the 10th's
    # steps, not shifted forward the way sleep would be.
    assert summary[0].latest_value == 500
