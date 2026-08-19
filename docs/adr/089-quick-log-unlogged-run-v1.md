# ADR 089 — Quick-Log an Unlogged Apple Health Run v1

## Status

Accepted.

## Context

ADR 088's "Not yet logged in SirisOS" card explicitly deferred any auto-fill or quick-log action, shipping visibility-only. The natural follow-up: turn a flagged Apple Health workout into an actual SirisRun/SirisGym entry with minimal retyping.

The two categories aren't symmetric. A run's whole loggable payload -- distance, pace, heart rate -- is exactly what Apple Health already captured, so pre-filling `RunningScreen`'s existing "Add run" dialog from it is a genuine one-tap-to-review-and-save flow. A strength session has none of that: Apple Health records duration and calories, not sets/reps/weight, so there's nothing to pre-fill on `GymScreen`'s workout form beyond the date -- the athlete still has to type every set manually, which isn't meaningfully faster than starting a blank workout. Built the running path only; the strength row keeps showing visibility-only, with the card's own caption explaining why rather than leaving it looking like a missing feature.

## Decision

`_RunEntryDialog` (private to `running_screen.dart`) now accepts optional `initialDate`/`initialDistanceKm`/`initialPaceSecondsPerKm`/`initialHeartRate`, applied in `initState()`; a new public `showAddRunDialog()` function is the single entry point both the Running screen's own "+" button and the Health screen's quick-log action call, so there's one dialog implementation, not two. The dialog's title changes to "Add run (from Apple Health)" when pre-filled, so it's clear the values came from somewhere, not typed. Pace is computed as `duration_seconds / (distance_m / 1000)`, rounded to the nearest second per km -- the same unit `RunningService.createRun()` already expects, no new conversion logic elsewhere.

On the Health screen, a running-category unlogged-workout row gets a "Log this run" button only when it actually has both distance and duration (the two Health fields the computation needs); after a successful save the row's parent list is re-fetched, so the now-logged run naturally drops out of the list on the next render -- no manual list-splicing, just the same fetch-and-rebuild pattern every other card in this app already uses.

## Consequences

- One dialog implementation serves both entry points -- `RunningScreen._addRun()` now calls the same `showAddRunDialog()` the Health screen calls, rather than duplicating the form.
- `UnloggedHealthWorkout` gained `avg_hr` (already captured by `HealthWorkoutModel`, just not previously exposed) specifically so the pre-fill could be genuinely complete -- all three of distance/pace/heart rate arrive filled in, leaving only a review-and-confirm step, not a several-field retype.
- Verified live end-to-end: ingested an Apple Health run (4.2 km, 25 min, avg HR 150), tapped "Log this run," got a dialog pre-filled with 4.20 km / 5:57 per km / 150 bpm exactly, saved it, and the row disappeared from the unlogged list on the next fetch -- confirmed via a direct API call that the new run recorded the exact same values, not an approximation.
- Backend: 240 tests pass, unchanged (this slice is Flutter-only plus one additive backend field). Flutter: 58 tests pass, unchanged -- no new pure-logic helper was extracted; the pace computation is a one-line derivation already covered by the live verification above.
