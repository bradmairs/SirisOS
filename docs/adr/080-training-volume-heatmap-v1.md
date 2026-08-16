# ADR 080 — Training Volume Heatmap v1

## Status

Accepted.

## Context

The roadmap's "Training volume heatmap (sessions/sets/tonnage/muscle group over time)" is the next SirisGym item without a new capture-side dependency — but "muscle group" isn't buildable (no exercise-to-muscle-group tagging exists), the same honest-scoping pattern already applied twice this sprint (ADR 078, ADR 079). Confirmed with Brad before building: a daily, GitHub-contributions-style calendar grid, shaded by that day's combined training volume across both gym and running.

The real design problem was combining two differently-shaped metrics — gym's `total_volume_kg` and running's `effort_score` (a 0–100 personal comparative score) — into one visual intensity without inventing a fake kg-to-effort exchange rate. `TrainingLoadService` (ADR 069) already solved an adjacent version of this problem at weekly granularity, by expressing each modality as a percentage of the athlete's own trailing 8-week baseline. A daily grain doesn't support a meaningful trailing-baseline window the same way (most individual days have no training at all), so this reuses the same "express relative to the athlete's own history" philosophy with a simpler mechanism suited to daily data.

## Decision

`TrainingLoadService.daily_intensity()` (new) buckets all gym workouts and runs by calendar day, then finds each modality's own all-time single-day maximum (`max_gym_day`, `max_run_day` — the athlete's personal-best day for that modality, computed over their full history regardless of the requested window). Each day's intensity is `min(1.0, gym_kg/max_gym_day + effort/max_run_day)` — the two modalities' fractions of their own respective bests, summed and capped at 1.0. A day that's only gym-trained or only run-trained scores purely on that modality's fraction; a day with both adds them together, so a big combined day reads as maximally intense without needing to know how a kilogram compares to an effort point.

`GET /api/v1/training/heatmap?days=84` exposes it (84 days ≈ 12 weeks default, matching the calendar grid's natural width). The Flutter `TrainingHeatmapCard` renders a Monday-aligned grid (weeks as columns, matching `TrainingLoadService._week_start`'s existing Monday convention) using continuous opacity on the app's `primaryBright` accent color rather than discrete buckets, with a `Tooltip` on each cell showing the exact date and that day's real numbers (kg lifted / running effort) — no fabricated "score," just the underlying evidence on hover. Added to both the Gym and Running screens, alongside the existing `TrainingLoadCard`, matching that widget's own precedent of appearing on both.

## Consequences

- No schema changes — reads from the same `gym_workouts`/`run_records` tables `TrainingLoadService` already queries.
- Verified live: logging 3 gym sessions and 2 runs on the same day produced a single fully-saturated cell with a tooltip reading "1508 kg lifted, 123 running effort" — both modalities' real numbers, correctly combined.
- Because the color scale is normalized against the athlete's own all-time best day, a genuinely quiet stretch (e.g. a new user's first week) will show muted colors even on their hardest day so far — this is intentional (self-relative, not an absolute scale) but means the visual "reads" differently for someone with months of history versus someone just starting out, the same personal-relative-not-absolute tradeoff Weekly Training Load and the running effort score already accept.
- Muscle-group breakdown remains unbuilt, same reason as Strength Score and the Muscle Map roadmap items: no exercise taxonomy exists yet.
