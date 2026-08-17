# ADR 084 — Muscle Map Body Diagram and Fatigue Estimate

## Status

Accepted.

## Context

ADR 083 shipped Muscle Map v1 as a bar chart of weekly volume per muscle group. Brad asked for two changes: render it as an actual body diagram rather than a bar list, and shade muscle groups lighter as they become "good to workout again" -- not just by volume.

The second half is the harder decision. SirisOS has no per-athlete recovery timeline anywhere in the codebase, and the roadmap already lists a personalized "Personal Fatigue Model" under Experimental/unscheduled, precisely because building one honestly needs real recovery evidence (how an athlete's own performance actually responds after N days off), not a guess. A literal "ready to train again" claim would be exactly the kind of fabricated number this app's no-fabrication rule exists to prevent -- the same reasoning that made Training Level's "Strength" sub-score get shelved earlier this sprint.

Two options were weighed with Brad before building:
- Self-relative only: shade by days-since-trained, with no claim about readiness at all.
- A labeled estimate: combine real evidence (the athlete's own logged volume, self-relative to their own typical session) with one named, clearly-caveated recovery-window assumption.

Brad chose the labeled estimate -- closer to what he actually asked for -- on the condition that it stays visibly labeled as an estimate, not presented as fact.

## Decision

**Fatigue model** (`GymService.muscle_group_fatigue()`): for each muscle group, sum tagged-exercise volume per day within a `MUSCLE_GROUP_RECOVERY_WINDOW_DAYS = 3` trailing window, linearly decayed to zero by day 3 (today counts full weight, the boundary counts zero). That decayed volume is compared against a **self-relative baseline** -- the athlete's own average daily volume for that group from *before* the current recovery window, looked back `MUSCLE_GROUP_FATIGUE_BASELINE_LOOKBACK_DAYS = 90` -- so "fatigued" means heavy relative to that athlete's own typical session, not an absolute number, and a session can't inflate the very baseline it's measured against. `fatigue_fraction` is `decayed_volume / baseline`, clamped to `[0, 1]`; a group with no historical baseline but a session today reads as maximally fresh (`1.0`) rather than silently zero. Alongside the fraction, `last_trained_date`, `days_since_trained`, and `ready_at` (`last_trained_date + 3 days`) are returned so the UI can show a genuine date, not just a color. New endpoint: `GET /gym/muscle-groups/fatigue`.

**Flutter body diagram** (`BodyDiagram` widget): a hand-authored SVG front/back silhouette split into the same six regions as `MUSCLE_GROUPS`, using `flutter_svg` (new dependency) to render a color-baked SVG string built per-frame from the fatigue data -- flutter_svg has no per-path recoloring API, and generating the markup directly avoided sourcing/licensing an external anatomical asset. `chest` only renders on the front view and `back` only on the back view (a `SegmentedButton` toggles which); `shoulders`/`arms`/`legs`/`core` render identically on both since they're visible from either side. Color is a single-hue lerp from a pale tint of `AppTheme.primary` (fraction 0) to `AppTheme.primaryBright` (fraction 1) -- lighter as a group is closer to `ready_at`, darker right after a heavy session, matching what Brad asked for literally.

The readiness label/threshold logic (`Ready` / `Recovering` / `Fatigued` / `No data yet`, and the "ready in N days" caption) lives in a plain-Dart `MuscleReadiness` helper (`lib/src/core/`) rather than inline in the widget, so it's unit-testable without a widget harness -- the same pattern this app already uses for `NotificationPolicyEngine`/`DashboardRefreshPolicy`. A caveat line is always visible on the card: "Estimated from your own volume and a general 3-day recovery window -- not a physiological measurement." Below the diagram, a per-group row still shows the raw 7-day volume number (from the existing `muscle_group_workload()`), so the color is never the only source of truth.

## Consequences

- `MuscleMapCard` now makes three calls on mount (`muscle_group_workload`, `muscle_group_fatigue`, `list_untagged_exercises`) instead of two; combined via `Future.wait`, one combined loading/error state, consistent with the card's existing single-fetch-in-`initState` pattern (still doesn't live-refresh mid-session, same as `TrainingLoadCard`/`TrainingHeatmapCard`).
- The 3-day recovery window and 90-day baseline lookback are one named constant apiece, applied equally to every muscle group -- not per-group tuned, since there's no evidence yet to justify different numbers per group. If/when the real "Personal Fatigue Model" gets built from actual recovery evidence, this estimate is the thing it would replace, not something it needs to coexist with.
- Verified live: tagged "Bench Press" (today, chest) and "Squat" (2 days ago plus an older baseline session, legs) via direct API calls, then confirmed in the browser -- chest rendered fully saturated ("Fatigued", ready in ~2 days), legs rendered a lighter partial shade ("Recovering", ready now), untrained groups rendered at the palest tint ("No data yet"); the Front/Back toggle correctly swapped the chest/back region and reflowed the torso height, while arms/legs/shoulders stayed identical across both views.
- No changes to `muscle_group_workload()` or existing gym endpoints; fully additive.
