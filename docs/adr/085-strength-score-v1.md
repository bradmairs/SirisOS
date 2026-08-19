# ADR 085 — Strength Score v1

## Status

Accepted.

## Context

Strength Score has been on the roadmap since ADR 083 unblocked it (it needed the same exercise-to-muscle-group tagging Muscle Map required), explicitly worded as "aggregate + per-muscle-group breakdown from historical performance, personal/relative rather than a universal absolute number." That last clause exists on purpose: Training Level's own Strength sub-score was shelved in ADR 074 for having no defensible basis -- ranking someone's strength meaningfully needs bodyweight or strength-standards data (e.g. "your squat is in the top 20% for your bodyweight") that SirisOS doesn't capture and has no way to capture honestly. Confirmed with Brad before building: Strength Score must not repeat that mistake -- no comparison to anyone else, no external standard, self-relative only.

## Decision

`GymService.strength_score()` compares each tagged exercise only to **itself**: `ratio = current_e1RM / that_same_exercise's_own_all_time_best_e1RM`. Bench press is never compared to squat, and nothing is compared to any other athlete or published standard -- 100% means "you are at your personal strongest for this exact lift right now," nothing more. "Current" is the most recent logged session's e1RM, with no time-decay or staleness assumption applied (unlike the Muscle Map fatigue estimate's deliberate recovery-window assumption, ADR 084) -- strength doesn't decay on a knowable schedule the way muscle fatigue recovers, so this stays purely evidence-based: the latest real number, whenever it was logged.

Per-muscle-group score is the average of that group's own tagged-exercise ratios (untagged exercises excluded entirely -- missing evidence, not zero, same convention `muscle_group_workload()` established). The overall score averages **muscle-group scores**, not raw exercises directly -- a group with three tagged exercises doesn't get 3x the weight of a group with one, avoiding a Strength Score that's secretly just "how many exercises did you happen to tag in your strongest group." A group and the overall score are both `None` when no evidence exists yet, distinct from a real 0% (which basically can't happen, since a lift is trivially at 100% of its own peak the first time it's ever logged). New endpoint: `GET /gym/strength-score`.

Flutter: a new `StrengthScoreCard` on the Gym screen, positioned right after `MuscleMapCard` since it reads the same tag data -- overall percentage in the header (matching `TrainingLoadCard`'s big-number placement), a caveat line ("never compared to anyone else"), and a per-muscle-group breakdown row showing lift count + percentage, or "No data yet" for untagged groups.

## Consequences

- Reuses `list_exercises()`/`_muscle_group_tags()` directly -- no new tables, no new tagging mechanism, fully additive on top of ADR 083's infrastructure.
- Verified live: Bench Press peaked at 100kg/5 three weeks ago (e1RM 116.7kg), most recent session at 85kg/6 (e1RM 102kg) -- correctly read as chest 87%; Squat logged once at a new all-time load -- correctly read as legs 100%; overall correctly averaged the two group scores (93.7%), matching a direct API call before trusting the UI.
- Strength Score and Muscle Map's fatigue estimate now sit side by side but answer genuinely different questions -- one is "how strong are you right now versus your own history" (no time assumption), the other is "how recovered is this muscle group" (an explicit, labeled recovery-window assumption) -- and they should stay conceptually separate rather than getting merged into one number.
- Run Readiness (also unblocked by ADR 083) remains the other queued roadmap item; not addressed here.
