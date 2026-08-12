# ADR 067 — Personal Records v1

## Status

Accepted.

## Context

The Sprint 0.9 brainstorm calls out "Personal records beyond live-computed rollups" — `ExerciseSummary` already tracks `best_weight_kg`/`best_estimated_one_rep_max_kg`/`best_set_volume_kg`, but purely as numbers recomputed fresh from full history on every request. Nothing ever *says* "new record" at the moment it happens; a PR is only discoverable by noticing a number changed on a chart. This is the same shape of gap as Progressive Overload v1 (ADR 066) and the Recommendation Engine (ADR 064): a fact that already exists in the data isn't surfaced as an event.

## Decision

`GymService.create_workout()` now snapshots each exercise's prior bests (via the existing `get_exercise()` rollup) *before* inserting the new workout, then compares the new workout's own best set per exercise against that snapshot — never against itself, and never double-counting multiple sets of the same exercise in one session (a session's three sets at 80/82.5/85 kg reports exactly one weight record, at 85 kg, not three). Three record types are checked independently per exercise: heaviest weight, best estimated 1RM (so a higher-rep set at lower weight can still be a record), and best single-set volume. An exercise's very first-ever log is not treated as a record — there's nothing to beat yet.

`POST /api/v1/gym/workouts` returns the new records inline (`new_records` on `WorkoutResponse`) and records one `ActivityService` event per record achieved (`event_type: "personal_record"`), so it surfaces in the notification feed exactly like every other logged event. The Flutter workout form now returns the created workout's records back to `GymScreen`, which shows an understated SnackBar after the workout list refreshes — matching the brainstorm's own explicit gamification instinct ("kept understated," "🏆 New record" as a small callout, not a modal celebration).

## Consequences

- A PR is now a real, timestamped fact with a message stating the previous value, not something a user has to notice themselves on a trend chart.
- No schema change beyond the existing `ExerciseHistoryPoint.workout_id` field added in ADR 066 (already needed for precise session grouping there, reused here for nothing extra).
- Running PR tracking (fastest splits, longest run, best negative split — the brainstorm's "Personal running records beyond PRs") is explicitly out of scope for this slice; `RunRecord` doesn't capture splits today, and that's a meaningfully different, larger piece of work than extending the already-rich Gym exercise data.
- The `GymService.create_workout()` signature changed from returning `Workout` to `tuple[Workout, list[PersonalRecord]]` — its only caller (`app/api/gym.py`) was updated; no other backend module calls it.
