# ADR 072 — Health Summary API v1

## Status

Accepted.

## Context

The Health Auto Export REST ingestion pipeline (previous PR, ahead of this sprint's SirisRun/SirisGym work) made HRV, resting heart rate, sleep and other Apple Health metrics durably persisted for the first time — but write-only. `GET /api/v1/health/status` only reports sync metadata (`last_sync`, `records_received`, `last_error`); nothing reads the actual metric *values* back out. The roadmap's own "Health Data Export REST ingestion" section names this gap explicitly: "Event Bus refresh and Health summary API" is the one item still unchecked there, and it's the stated hard dependency blocking Training Conflict Detection, Run Readiness, and the Smart Weekly Planner — all three need to know whether *today* looks different from *usual* for HRV/sleep/resting HR, and none of that is queryable today.

Two things were bundled under that one roadmap checkbox: a query/read API (this ADR), and Event Bus refresh (live push notification when new health data syncs). Confirmed with Brad to split them and build the read API first — the downstream features that are actually blocked need to be able to `GET` the data, not receive a live event about it. Event Bus refresh remains a separate, still-open item.

## Decision

`HealthIngestService.summary(*, baseline_days: int = 14)` (new method on the existing ingest service, not a new service — it already owns `health_metric_samples` and the DB session) returns one `HealthMetricSummary` per distinct `metric_type` present in the data: the latest reading, plus a trailing baseline average computed from samples strictly *before* the latest reading's own calendar day. This mirrors the exact principle ADR 066/067/069 already apply to gym/running data — a metric is never compared against itself — and expresses the comparison the same way `TrainingLoadService` expresses weekly load: a `baseline_ratio` (latest as a percentage of the trailing baseline, 100 = typical), gated behind a `MIN_BASELINE_SAMPLES` floor (3) so a metric with too little history returns `baseline_average`/`baseline_ratio: null` rather than a distorted number, matching `TrainingLoadService.MIN_BASELINE_WEEKS`'s same reasoning.

The method is fully generic over metric type — it does not hardcode "HRV"/"resting heart rate"/"sleep" specifically, since the ingest pipeline already accepts "any Health Auto Export metric" per the roadmap's own stated design. Whatever metric types are actually present get summarized.

`GET /api/v1/health/summary?baseline_days=1..90` (new, under the existing `health` router) exposes this. On the Flutter side, a "Recovery vs your baseline" section was added directly to the existing `HealthScreen` (not a new screen) — it renders independently of the MCP live-snapshot section above it, since Health Auto Export ingestion and the MCP pull are two separate, already-independent data paths.

## Consequences

- Training Conflict Detection, Run Readiness and the Smart Weekly Planner can now build directly on `HealthIngestService.summary()` for their "is today different from usual" input, the same way they already can lean on `TrainingLoadService` for training-side load. This was the explicit reason this slice was chosen over Gamification (fully standalone, but unblocks nothing else).
- Event Bus refresh (a live `ModuleDataChanged`-style notification when new Health Auto Export data lands) remains explicitly unbuilt. The roadmap's single "Event Bus refresh and Health summary API" line was split into two so this distinction is visible rather than silently implied by a half-completed checkbox.
- No new database table or migration — `summary()` reads the same `health_metric_samples` table the ingest endpoint already writes, so this is a pure read-side addition with zero ingestion-path risk.
- Deliberately out of scope: workouts (`health_workouts`) aren't summarized here — Apple Health's own workout records are a different concept from SirisOS's own `RunningService`/`GymService` sessions, and conflating them wasn't asked for by anything currently blocked on this ADR.
- `baseline_days` defaults to 14 (two weeks), shorter than `TrainingLoadService`'s 8-week window — daily recovery metrics (HRV, resting HR) are noisier day-to-day than weekly training totals, and a two-week trailing window is the more standard comparison window for these specific metrics in the wearables space generally.
