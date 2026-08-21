from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.services.health_ingest_service import HealthIngestService

# A daily readiness/recovery score, self-relative like everything else in
# this app (Strength Score, Training Level, HealthIngestService's own
# baseline_ratio): each of HRV and sleep duration is expressed as a percent
# of the athlete's own trailing baseline for that metric, and the score is
# the average of whichever of the two have enough history for that day,
# clamped to [0, 100]. A completely typical day (both metrics at 100% of
# baseline) scores 100 -- "fully at your own norm" -- rather than reserving
# 100 for an unusually good day; below-baseline HRV/sleep pulls the score
# down proportionally. Neither metric alone determines the score if the
# other is available; if neither has enough history for a given day, that
# day has no score rather than a fabricated one.
DEFAULT_BASELINE_DAYS = 14
MIN_BASELINE_POINTS = 3
READINESS_HISTORY_DEFAULT_DAYS = 30

# Same alias sets TrainingConflictService already established for these two
# metrics -- kept as a local copy rather than importing from there, since
# the two services don't otherwise depend on each other.
_HRV_METRIC_TYPES = ("heart_rate_variability", "hrv")
_SLEEP_METRIC_TYPES = ("sleep_analysis", "sleep", "sleep_duration")


@dataclass(frozen=True)
class DailyReadinessPoint:
    day: date
    score: int | None
    hrv_ratio: float | None
    sleep_ratio: float | None


class ReadinessService:
    def __init__(self, health_service: HealthIngestService | None = None) -> None:
        self._health_service = health_service or HealthIngestService()

    def daily_history(
        self,
        *,
        days: int = READINESS_HISTORY_DEFAULT_DAYS,
        baseline_days: int = DEFAULT_BASELINE_DAYS,
        now: datetime | None = None,
    ) -> list[DailyReadinessPoint]:
        now = now or datetime.now(timezone.utc)
        # Need extra lookback so the earliest requested day can still see a
        # full baseline window behind it, not just be silently score-less.
        lookback_days = days + baseline_days
        hrv_by_day = self._merged_daily_history(_HRV_METRIC_TYPES, days=lookback_days, now=now)
        sleep_by_day = self._merged_daily_history(_SLEEP_METRIC_TYPES, days=lookback_days, now=now)

        candidate_days = sorted(set(hrv_by_day) | set(sleep_by_day))
        if not candidate_days:
            return []
        # Anchored on the most recent day either metric actually has data
        # for, not the literal current calendar day -- so a "last 30 days"
        # window still shows real data instead of going empty just because
        # today hasn't synced yet.
        most_recent_day = candidate_days[-1]
        cutoff = most_recent_day - timedelta(days=days - 1)

        points: list[DailyReadinessPoint] = []
        for day in candidate_days:
            if day < cutoff:
                continue
            hrv_ratio = self._baseline_ratio(hrv_by_day, day, baseline_days)
            sleep_ratio = self._baseline_ratio(sleep_by_day, day, baseline_days)
            points.append(
                DailyReadinessPoint(
                    day=day,
                    score=self._score(hrv_ratio, sleep_ratio),
                    hrv_ratio=hrv_ratio,
                    sleep_ratio=sleep_ratio,
                )
            )
        return points

    def today(self, *, now: datetime | None = None) -> DailyReadinessPoint | None:
        history = self.daily_history(days=1, now=now)
        return history[-1] if history else None

    def _merged_daily_history(
        self, metric_types: tuple[str, ...], *, days: int, now: datetime
    ) -> dict[date, float]:
        merged: dict[date, float] = {}
        for metric_type in metric_types:
            for point in self._health_service.daily_history(metric_type, days=days, now=now):
                merged[point.day] = point.value
        return merged

    @staticmethod
    def _baseline_ratio(values_by_day: dict[date, float], day: date, baseline_days: int) -> float | None:
        today_value = values_by_day.get(day)
        if today_value is None:
            return None
        window_start = day - timedelta(days=baseline_days)
        prior = [value for candidate, value in values_by_day.items() if window_start <= candidate < day]
        if len(prior) < MIN_BASELINE_POINTS:
            return None
        baseline_average = sum(prior) / len(prior)
        if baseline_average == 0:
            return None
        return round((today_value / baseline_average) * 100, 1)

    @staticmethod
    def _score(hrv_ratio: float | None, sleep_ratio: float | None) -> int | None:
        ratios = [ratio for ratio in (hrv_ratio, sleep_ratio) if ratio is not None]
        if not ratios:
            return None
        average = sum(ratios) / len(ratios)
        return round(min(100.0, max(0.0, average)))
