# ADR 082 — Health Daily Cumulative Totals v1

## Status

Accepted.

## Context

The Health screen showed "the latest import" for every metric type generically — for a metric like steps, that meant the single most recent HealthKit sample (e.g. "342" from one ~10-minute window), not the day's actual step count. Brad asked for the app to be cumulative per day instead: each sync should add to a running daily total, with that total stored and browsable as a historical trend per metric.

Two things needed resolving before building this, confirmed with Brad:

1. **Not every metric should be summed.** Apple HealthKit itself distinguishes cumulative quantity types (steps, active energy, sleep duration — sum to a meaningful daily total) from discrete ones (heart rate, weight — summing readings would be nonsense; you want the latest). Confirmed scope: steps, active energy and sleep are cumulative; resting heart rate and body weight stay latest-reading.
2. **Day boundaries need a timezone**, which the backend had never had a concept of — every timestamp was implicitly treated as UTC. Apple Health samples are real UTC instants, so without a local timezone, a walk taken at 8am in Sydney would silently land in *yesterday's* UTC-day bucket. Confirmed: `SIRISOS_TIMEZONE` env var, defaulting to `Australia/Sydney`.

The raw data to build this already existed and needed no new capture: `health_metric_samples` already stores every individual timestamped sample, content-addressed and idempotent (ADR before this one), so a "daily total" is just a query-time aggregation over rows already there — not a new mutable running counter that risks double-counting across repeated syncs.

## Decision

`HealthIngestService` gains `_is_cumulative(metric_type)` (a fixed set of known cumulative type strings, matching the alias-set pattern `TrainingConflictService` already uses for HRV/resting-HR) and local-timezone helpers (`_local_date`, `_local_day_start_utc`) built on `zoneinfo.ZoneInfo(SIRISOS_TIMEZONE)` — the first local-time-aware code in the backend; everywhere else still treats naive datetimes as UTC.

`summary()` and `snapshot()` both branch on this classification now:
- **Cumulative metrics** report the sum of every sample on today's *local* calendar day, with the baseline being the average of each of the trailing `baseline_days` prior days' own totals (not prior individual samples).
- **Point-in-time metrics** are unchanged in behavior — latest single reading, baselined against prior individual readings — just now using a correct local-day boundary instead of an implicit UTC one.

A new `daily_history(metric_type, days=30)` method and `GET /api/v1/health/metrics/{metric_type}/history` endpoint expose the same per-day buckets across a rolling window, backing a new `HealthMetricHistoryScreen` (reusing the existing `MetricLineChart` widget) that opens when tapping either a "Today" tile or a "Recovery vs your baseline" row — the drill-down Brad asked for.

`summary()`, `snapshot()` and `daily_history()` all take an optional `now: datetime | None` parameter, matching the testable-`reference_date` convention every other service in this app already follows (`TrainingLoadService`, `CoachService`, `AskSirisService`, etc.) — without it, testing "today's total" would mean either flaky wall-clock-relative fixtures or no coverage of the timezone-crossing edge cases at all.

## Consequences

- No schema changes — reuses the existing `health_metric_samples` table exactly as ADR 072 defined it.
- Verified live end-to-end: ingesting three step-count samples across a real day (2100 + 3400 + 1800) produced a "Today" tile reading exactly 7300, a baseline row reading "137% of usual" against three prior days averaging 5333, and a drill-down chart showing the correct 4-day history — all cross-checked against the raw API responses before touching the UI.
- Found and fixed a real, unrelated, pre-existing layout bug while wiring up the tap-to-drill-down interaction: `_MetricTile`'s `Spacer()` inside a `Container` with only `minHeight` (no `maxHeight`), inside a `Wrap` — the exact same `Spacer`-in-`Wrap` crash already found and fixed once this sprint in Coach's `_MetricTile`, but apparently never applied to Health's copy. Fixed with the same established pattern (`mainAxisSize: MainAxisSize.min` + a fixed `SizedBox` gap instead of `Spacer()`), confirmed via live browser testing — the Health screen would not render at all without this fix, independent of anything in this ADR.
- Found and fixed a second, unrelated latent bug in the process of updating an existing test: `test_baseline_excludes_same_day_as_latest`'s fixture used a 22:00 UTC sample that (correctly, once local-day boundaries were introduced) crosses into the *next* Sydney calendar day, defeating the test's own premise — fixed by using a fixture time that stays within the same local day.
- `MIN_BASELINE_DAYS = 3` (days with data) is the cumulative-metric equivalent of `MIN_BASELINE_SAMPLES = 3` (individual readings) — both gate `baseline_ratio` behind "enough personal history to call anything typical," same principle as every other baseline in this app.
