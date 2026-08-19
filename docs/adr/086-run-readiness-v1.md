# ADR 086 — Run Readiness v1

## Status

Accepted.

## Context

Run Readiness has been on the roadmap since Health Summary (ADR 072) and Training Conflict Detection (ADR 073) shipped, worded with its own open question: "someone can be HRV-recovered while their legs are wrecked from squats; needs both Health recovery data and recent gym leg volume as inputs... still needs a decision on how to combine the two signals." Muscle Group Tagging (ADR 083) and the muscle-group fatigue estimate (ADR 084) finally made "recent leg volume" queryable, unblocking this.

The existing "Can I train today?" Ask Siris pattern (ADR 081) already triggers on "should I run" phrasing, but only ever answers with whole-body signals (`TrainingConflictService`'s HRV/resting-HR check + `TrainingLoadService`'s weekly assessment) -- it has no idea whether legs specifically are fatigued, which is exactly the gap the roadmap named. Confirmed with Brad before building: combine the two signals into one verdict (rather than showing them as two separate, uncombined lines) that names whichever signal is actually the problem, and do it by extending the existing Ask Siris pattern rather than building a parallel Run Readiness subsystem.

## Decision

`AskSirisService._readiness_check()` now distinguishes "should I run" / "can I run" phrasing from the more general "should I train" / "can I lift" / "can I work out" phrasing it already recognized. Only for the run-specific phrasing, it additionally reads the `legs` entry from `GymService.muscle_group_fatigue()` (ADR 084) and flags it when `fatigue_fraction >= 0.6` -- the exact same "Fatigued" boundary the Muscle Map UI already draws (`MuscleReadiness`), reused rather than inventing a second threshold for what's conceptually the same signal shown two different ways. A day with no leg-training data (`days_since_trained is None`) is never flagged, matching the fatigue estimate's own "no data yet" convention.

The verdict is additive, not a single collapsed status: the existing whole-body `conflict.guidance` sentence always leads, a leg-fatigue sentence is appended only when flagged (naming how recently legs were trained), and the weekly-load assessment always trails -- so a "should I lift" question is completely unaffected (legs aren't assumed to be the limiting factor for lifting the way they are for running), while "should I run" can now say both "recovery looks fine" and "your legs are still fatigued from squats" in the same answer, addressing the roadmap's own named scenario directly. No new endpoint, no new UI -- this flows through the existing `GET /coach/ask` route and the existing Ask Siris box on the Coach screen unchanged.

## Consequences

- Zero Flutter changes. The Ask Siris answer is free text already rendered generically; this is a pure backend enrichment of one existing question pattern.
- `facts["legs_fatigued"]` is only present when the question was run-specific -- absent (not `false`) for lifting/generic-training questions, so a caller can tell "not checked" apart from "checked and fine."
- Verified live: seeded three historical squat sessions (establishing a baseline) plus one logged today, asked "Should I run today?" through `/coach/ask` -- got back "...Your legs are still estimated fatigued from training earlier today -- an easy run or extra rest is reasonable before pushing pace...", `legs_fatigued: true`; the same data with "Can I train today?" correctly omitted any mention of legs. Confirmed in the actual Coach screen's Ask Siris box afterward, unchanged UI.
- This is deliberately still an estimate layered on an estimate: the underlying `muscle_group_fatigue()` is itself a labeled 3-day-recovery-window assumption (ADR 084), not a measurement. Run Readiness inherits that caveat rather than hiding it -- the wording says "estimated fatigued," not "fatigued."
