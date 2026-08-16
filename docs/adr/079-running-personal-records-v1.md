# ADR 079 — Running Personal Records v1

## Status

Accepted.

## Context

ADR 067 shipped Gym Personal Records but explicitly deferred running: "Running PR tracking (fastest splits, longest run, best negative split) remains separate future work — `RunRecord` doesn't capture splits today." The roadmap's own "Personal running records beyond simple PRs" item lists several sub-items — fastest splits at multiple distances, best negative split, highest-elevation week — that genuinely can't be built honestly: `RunRecordModel` captures only `run_date`, `run_type`, `distance_km`, `average_pace_seconds_per_km` and `average_heart_rate` — no GPS, no splits, no elevation. Confirmed with Brad before building: v1 covers only what's real from existing data — longest run, and lowest heart rate recorded at a comparable pace — rather than approximating split-level PRs from whole-run averages.

## Decision

`RunningService.create_run()` now returns `tuple[RunRecord, list[RunningPersonalRecord]]` (previously just `RunRecord`), mirroring `GymService.create_workout()`'s shape. It snapshots prior bests before inserting the new run — the same "never compare a record against itself" discipline Gym Personal Records already established — then checks two independent conditions:

- **Longest run**: the new run's `distance_km` exceeds every prior run's distance.
- **Lowest heart rate at pace**: the new run's `average_heart_rate` is lower than any prior run whose pace was within `LOWEST_HEART_RATE_PACE_TOLERANCE_SECONDS_PER_KM` (15 sec/km) of this run's pace — a "same effort, less cardiovascular strain" fitness signal, the running equivalent of Gym's estimated-1RM record.

A first-ever run sets no records (no baseline to beat, matching Gym's identical rule). `POST /api/v1/running` fires an `ActivityService` "personal_record" event per new record and returns them in the response's `new_records` field; the Flutter `_RunEntryDialog` pops them back to `RunningScreen`, which shows the same `🏆 New record: ...` SnackBar pattern Gym already uses.

## Consequences

- No schema changes — reuses the existing `run_records` table.
- Fastest splits, best negative split and highest-elevation week remain explicitly unbuilt, same as ADR 067 already stated — they need a capture-side decision (GPS/splits/elevation) this app doesn't have, not a service-layer change.
- Verified live end-to-end: a 5km run at 5:00/km (160 bpm) followed by an 8km run at a comparable 5:05/km pace but a lower 150 bpm correctly fired both records simultaneously, with the SnackBar reading "New record: longest run, lowest heart rate at pace".
- `RunningService.create_run()`'s signature change is a breaking change for any direct caller; the only caller (`POST /api/v1/running`) was updated, and the existing test suites that call `create_run()` without capturing its return value (achievements, ask-siris, coach, training-conflict, training-load) needed no changes since none of them relied on the old single-value return.
