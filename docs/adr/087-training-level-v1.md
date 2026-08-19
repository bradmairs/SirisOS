# ADR 087 — Training Level v1

## Status

Accepted.

## Context

The Level System (a composite Strength/Endurance/Consistency/Recovery score) was deliberately deferred in ADR 074: Endurance (`RunRecord.fitness_score`, a 0-100 EWMA) and Consistency (session frequency) already had a real basis, but Strength didn't -- every other score in this app is self-relative, and a Strength number without bodyweight or strength-standards data would have been the first fabricated number in an app that had consistently declined to invent one. Recovery had no precedent either: nobody had combined HRV and resting-HR baseline ratios into one blended score before.

Strength Score v1 (ADR 085) resolved the Strength blocker with a strictly self-relative design (current e1RM versus each exercise's own all-time peak). Recovery's blocker remains open -- `HealthIngestService.summary()` computes an HRV `baseline_ratio` and a resting-HR `baseline_ratio` independently, but nobody has established a weighting to blend the two into a single recovery number, and inventing one now would be exactly the fabrication ADR 074 declined to do. Confirmed with Brad before building: ship three dimensions now (Strength, Endurance, Consistency), leave Recovery deferred again rather than force a fourth number into existence -- the same conditional ADR 074 itself set: "a future attempt has to either find a real basis... or explicitly accept the fabrication tradeoff, not silently skip past it."

Consistency also needed a genuinely new piece: only a binary achievement-style check existed (`AchievementService`'s "4+ days/week for 8 consecutive weeks" streak), no continuous score. Confirmed to build it self-relative to the athlete's own trailing average (matching Strength Score/Training Load/the fatigue estimate's shared convention) rather than against the achievement system's fixed 4-day target, which would have broken from that convention for a fixed, unjustified number.

## Decision

`TrainingLevelService.training_level()` returns three independent dimensions plus an overall average:

- **Strength**: `GymService.strength_score().overall_score` scaled to 0-100, verbatim -- no new computation, reuses ADR 085 exactly.
- **Endurance**: the most recent run's `fitness_score` (already 0-100), the current reading of the athlete's own EWMA trend.
- **Consistency** (new): weekly-bucketed like `AchievementService`'s streak check -- only fully-elapsed weeks count, so an in-progress week can't look artificially bad before it's over. The last full week's distinct training days is compared against the athlete's own trailing average across the `CONSISTENCY_BASELINE_WEEKS = 8` weeks before that (averaged only over weeks that had any training, mirroring `muscle_group_fatigue()`'s baseline convention of not zero-filling calendar gaps), requiring at least `CONSISTENCY_MIN_BASELINE_WEEKS = 2` qualifying weeks before showing a ratio.

Each dimension is `None` (not a fabricated 0) when there's no evidence yet -- no exercises tagged, no runs logged, or not enough weekly history. `overall_score` averages only the dimensions that have data, matching Strength Score's own "average of what exists" convention; when zero dimensions have data, `overall_score` is `None` too. New endpoint `GET /coach/training-level`, following `coach.py`'s existing module-singleton DI pattern.

Flutter: a new `_TrainingLevelCard` on the Coach screen (after Achievements, before Ask Siris) -- overall score as a big header number matching `TrainingLoadCard`/`StrengthScoreCard`'s placement, a caveat line naming both the self-relative philosophy and the Recovery gap explicitly, then one row per dimension showing its label, its plain-English basis, and its score (or "--" when unscored).

## Consequences

- Recovery stays a named, deferred gap -- not silently dropped. If a future slice finds a real basis for blending HRV/resting-HR (or decides to accept the fabrication tradeoff explicitly), this is the number it would extend, not replace.
- Zero new fabrication risk: Strength and Endurance are exact reuses of existing self-relative scores; Consistency is the only new computation, and it follows the same self-relative-to-own-history rule everything else in this app already follows.
- Verified live: with one tagged exercise (chest, 93.7% of its own peak) and no runs/insufficient weekly history logged, Training Level correctly showed an overall of 94 (Strength alone, since it's the only scored dimension), with Endurance and Consistency both showing their specific "why not yet" reasons rather than a blank or a fabricated zero.
- Backend: 230 tests pass (7 new). Flutter: 58 tests pass, unchanged (Training Level's card has no new pure-logic helper worth extracting -- the composition logic lives entirely in the tested backend service).
