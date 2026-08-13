# ADR 069 — Weekly Training Load v1

## Status

Accepted.

## Context

The Sprint 0.9 brainstorm's "Unified training" section calls combined running + strength load the signature differentiator — "a self-hosted system that can say... starts feeling like an actual personal operating system, rather than a collection of health dashboards." Running and Gym have always been logged as two unrelated modules: `RunningService` computes a 0–100 `effort_score` per run (and an EWMA `fitness_score` trend from it), while `GymService` computes raw tonnage (`total_volume_kg`) per workout. Nothing today looks across both to say whether *this week*, as a whole, was heavy or light.

The two source numbers are not directly comparable — a 0–100 per-run score and raw kilograms of tonnage have no shared unit. Any "one number" design has to resolve that mismatch, and a fixed conversion constant (e.g. dividing tonnage by an arbitrary factor) would need retuning per person and doesn't meet the deterministic, defensible-reasoning bar ADR 066/067 set.

## Decision

`TrainingLoadService` (new) computes each modality's weekly load as a **percentage of the athlete's own trailing baseline**, then sums the two percentages into one combined index — 100 means "typical," not an absolute unit. Concretely, for a given week:

- Running load = sum of `effort_score` across runs in that week; gym load = sum of `total_volume_kg` across workouts in that week. Both reuse fields that already exist — no new scoring formula was invented for this slice.
- The baseline is the average of that same sum across the trailing 8 weeks, but only counting weeks *at or after* the modality's first-ever logged record — a week that predates a user's first run or first workout isn't a real "zero" week, it's a week that didn't exist for them yet, and counting it would understate the baseline and overstate the ratio for anyone with a short history. A week with no training that happens *after* someone's history began, on the other hand, is a genuine data point (a rest week) and counts as 0.
- At least 2 qualifying baseline weeks are required before a ratio is computed at all; with fewer, the modality's `ratio`/`baseline` are `null` and the response says so plainly ("Not enough training history yet to compare this week") rather than fabricating a misleading number from too little data.
- `combined_index` sums whichever ratios are available (both, one, or `null` if neither modality has enough history yet) and a v1 `assessment` string labels it against fixed thresholds (<70 lighter, >130 heavier, else typical).

`GET /api/v1/training/weekly-load` returns the current week; `GET /api/v1/training/weekly-load/history?weeks=1..12` returns a trailing run of weeks for a simple trend view. Both endpoints live in a new `app/api/training.py`, wired into the existing `/api/v1` aggregator router in `app/api/running.py` alongside gym/activity/search/intelligence/health — there was no shared "training" router before this, since nothing had previously needed to read both `RunningService` and `GymService` together.

On the Flutter side, a single `TrainingLoadCard` widget is shared by the Gym and Running screens (both call the same `GET /weekly-load`), rather than building a new dedicated screen — this is presentation of an existing pair of modules' data, not a third module.

## Consequences

- No arbitrary tuning constants: the only configurable numbers are the baseline window (8 weeks) and the minimum-baseline-weeks floor (2), both named constants in `training_load_service.py`, and both express a policy choice ("how much history counts as typical") rather than a unit conversion.
- A brand-new user, or a user who just started one of the two modalities, correctly sees `null`/"not enough history" for that modality rather than a wildly inflated or deflated ratio — verified in `test_training_load.py::test_single_baseline_week_is_insufficient`.
- `combined_index` is deliberately not comparable across users or over long time spans — it only means "vs. your own last ~2 months," matching Personal Records' (ADR 067) and the brainstorm's own stated preference for scores "based on your own historical performance rather than pretending there's one universally meaningful strength score."
- Training conflict detection (roadmap's next unified-training item) can now build on `TrainingLoadService` directly instead of re-deriving weekly sums itself.
- Deliberately out of scope for v1: per-day load (only weekly rollups), any notion of recovery/HRV weighting (blocked on the still-unbuilt Health Data Export pipeline), and a drag-to-rearrange planner — this slice only answers "was this week heavy," not "what should next week look like."
