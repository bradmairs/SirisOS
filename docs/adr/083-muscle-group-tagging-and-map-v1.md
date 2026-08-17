# ADR 083 — Muscle Group Tagging and Muscle Map v1

## Status

Accepted.

## Context

Three roadmap items — Strength Score, Muscle Map, and Run Readiness — all share the same missing prerequisite: no exercise-to-muscle-group mapping exists anywhere in SirisOS. Exercise names are free text with no picker, so there's no existing structure to build a mapping on top of. Confirmed with Brad before building: tagging is athlete-assigned (pick a muscle group once per exercise, from a fixed list), not inferred from exercise-name keywords. Keyword inference was the faster option but genuinely ambiguous (a name like "curls" or "press" doesn't map to one muscle group reliably), and this app's no-fabrication rule already governs exactly this kind of situation elsewhere -- `AchievementService`'s `_MAJOR_LIFTS` only keyword-matches a small, unambiguous set (bench/squat/deadlift/overhead press) for a completely different purpose (badge detection), not general classification.

## Decision

New `exercise_muscle_groups` table (`GymService`) maps a casefolded exercise key to one of a fixed six groups (`chest`, `back`, `legs`, `shoulders`, `arms`, `core`) -- the same casefold-key convention `list_exercises()` already uses to group sets, so a tag applies uniformly to every past and future set logged under that exercise name regardless of capitalization. `tag_exercise()` upserts (retagging replaces rather than erroring); `list_untagged_exercises()` surfaces exercises with logged sets but no tag yet.

`muscle_group_workload(days=7)` sums `total_volume_kg`/set count/exercise count per group across recent workouts, reading only tagged exercises -- an untagged exercise is missing evidence, not zero workload, so it's surfaced separately via the untagged list rather than silently folded into a bucket or dropped without explanation. All six groups are always returned, even at zero, so the UI can render a stable bar chart rather than a list that grows as tags get added.

Flutter: a `Tag muscle group` chip on the Exercise Intelligence detail screen opens a picker dialog (or shows the current tag once set); a new `MuscleMapCard` on the Gym screen renders the six groups as a horizontal bar chart scaled to the largest group, with a note naming how many exercises still need tagging.

## Consequences

- No changes to existing gym endpoints' request/response contracts beyond one new optional field (`ExerciseSummaryResponse.muscle_group`) -- fully backward compatible.
- Verified live end-to-end: tagging "Bench Press" as chest immediately reflected in `list_untagged_exercises()` (empty), the exercise detail's `muscle_group` field, and `muscle_group_workload()` (chest: 640 kg from the one logged set) -- confirmed via direct API calls before checking the UI, then confirmed again in the real Muscle Map bar chart after a fresh screen mount.
- `MuscleMapCard`, like `TrainingLoadCard` and `TrainingHeatmapCard` before it, fetches once in `initState()` and doesn't live-refresh on tag changes within the same session -- consistent with those existing cards' behavior on this same screen, not a new gap introduced here. A full remount (navigating away and back, or reloading) picks up the change immediately.
- This is the tagging infrastructure and its first consumer (Muscle Map), not Strength Score or Run Readiness -- both are now unblocked and can reuse `muscle_group_workload()`/the tag data directly as clean follow-up slices, rather than needing their own tagging mechanism.
