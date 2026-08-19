# ADR 088 — Unlogged Apple Health Workouts v1

## Status

Accepted.

## Context

Apple Health workouts have been ingested and stored (`health_workouts`: type, duration, distance, calories, avg/max HR) since the original Health Data Export slice, but nothing has ever read them back -- no endpoint, no UI. A watch-tracked run or gym session syncs into SirisOS and then goes completely dark, even though SirisRun/SirisGym exist specifically to track that data. Confirmed with Brad before building: don't just surface the raw list -- cross-reference it against SirisGym/SirisRun's own manually-logged sessions and flag the ones missing a same-day entry, since a passive "here's your Apple Health history" list duplicates what the Health app already shows, while "you did this and haven't logged it" is a genuine gap this app is positioned to catch.

## Decision

`HealthIngestService.list_workouts()` (new) is the first reader of `health_workouts`, converting each row's `start_time` to a local date via the existing `_local_date()` helper.

`HealthWorkoutMatchService.list_unlogged_workouts()` cross-references by same local calendar date only -- no time-of-day or duration/distance closeness matching, the same deterministic same-day signal `TrainingConflictService` already uses for its own session-logged-today check. Matching is deliberately narrow: only Apple Health workout types containing "run" or "strength" are ever compared (against `RunningService.list_runs()`/`GymService.list_workouts()` respectively) -- SirisOS only tracks those two categories, so a walk, swim, or yoga session has nowhere to be "logged" in this app yet, and flagging it as missing would be misleading rather than helpful. This mirrors why muscle-group tagging stayed athlete-assigned rather than keyword-inferred (ADR 083): a small, unambiguous keyword set, not a general classifier. New endpoint `GET /health/unlogged-workouts?days=30`.

Flutter: a new "Not yet logged in SirisOS" card on the Health screen (after the recovery-baseline section), listing each unlogged workout's type, date, and duration/distance -- pure visibility, no auto-fill or quick-log action in this v1.

**Bug found and fixed while building this**: `_parse_timestamp` parsed an ingested timestamp's offset (Health Auto Export sends `"YYYY-MM-DD HH:MM:SS +ZZZZ"`) but never normalised it to UTC before storage, even though the rest of the module (`_as_aware`) assumes every stored value already is UTC. Under Postgres this was harmless (the driver normalises on write), but under SQLite -- this app's local dev/test database -- tzinfo is dropped on round-trip, so a naive value read back gets re-interpreted as UTC and shifted again by the local offset. Any workout or metric sample timestamped past ~2pm local silently rolled into the next calendar day. Existing test fixtures never caught it because they all used early-morning timestamps, which don't cross the boundary either way. Live-verifying this feature's same-day matching against a realistic evening workout surfaced it directly; fixed by converting to UTC in `_parse_timestamp` itself, with a regression test pinning a late-local-time workout to its correct date.

## Consequences

- Zero fabrication risk: every field displayed is a real ingested value; the only new logic is a same-date set-membership check.
- The timezone fix is a genuine correctness improvement for every local-date-boundary-sensitive feature that touches ingested Health data (daily cumulative totals, recovery baselines, this feature) under SQLite -- not just this slice's own code path.
- Verified live: ingested a real Apple Health payload (a run 3 days ago, a strength session the prior evening), neither logged in SirisRun/SirisGym -- both correctly appeared with the right dates after the timezone fix (the strength session had initially misdated itself a day forward, exposing the bug before the fix landed).
- Backend: 240 tests pass (10 new: 2 `list_workouts()`, 1 timezone regression, 7 matching). Flutter: 58 tests pass, unchanged.
- Cross-referencing other Apple Health workout types (walking, cycling, swimming) stays out of scope until SirisOS has somewhere to log them -- the same "decline rather than approximate" precedent as the Achievements' excluded "Climber" badge (ADR 074).
