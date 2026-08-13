# ADR 074 — Gamification: Achievements v1

## Status

Accepted.

## Context

The roadmap's Gamification section bundles two brainstorm ideas: Achievements (concrete, evidence-backed milestones) and a Level System (a composite "Training Level 42" score across Strength/Endurance/Consistency/Recovery). Confirmed with Brad before starting: build Achievements only for this slice.

The Level System was deliberately deferred, not just left for later opportunistically. Endurance (`RunningService.fitness_score`, already a 0–100 EWMA) and Consistency (session frequency, already computable) have real, existing bases. Strength does not: every other score in this app — `TrainingLoadService`'s ratio, the Health Summary API's baseline ratio — is expressed relative to the *athlete's own history*, never against an absolute/objective scale, because SirisOS has no strength-standards table and no reliably-present bodyweight data to normalize against. A "Strength" sub-score built without either of those would be the first fabricated number in an app that has consistently declined to invent one everywhere else (ADR 069's baseline-ratio design, ADR 072's minimum-sample floor, ADR 073's staleness check, Ask Siris's "I don't recognise that question yet" fallback). Recovery would need a new HRV+resting-HR blending formula with no precedent either. Both remain open problems, not solved-and-shipped.

## Decision

`AchievementService.list_achievements()` (new) returns eight fixed, hand-written checks, each a real recorded fact crossing a real threshold:

- **Weight clubs** (4): 100 kg+ on Bench Press, Squat, Deadlift, Overhead Press — generalizing the brainstorm's single "100 Club — Bench 100 kg" example across the four standard compound lifts, matched by substring against the athlete's actually-logged exercise names (same matching convention Ask Siris and Training Conflict Detection already use)
- **Million Kilo Club**: cumulative lifetime `total_volume_kg` across all logged workouts crosses 1,000,000 kg
- **Sub-25**: any run within tolerance of 5 km completed in under 25:00
- **Consistency**: 4+ distinct training days a week for 8 consecutive *fully-elapsed* weeks — the current in-progress week is explicitly excluded so it can neither falsely break nor falsely complete a streak before it's actually over
- **Progressive**: any exercise strung together 5 consecutive sessions of increasing best-set weight

Every achievement reports `unlocked`, `achieved_date` (the date the threshold was *first* crossed — not the date of whatever the eventual best turned out to be, matching the "first crossing" semantics `TrainingConflictService` and the weight-club checks already use), and a `progress_label` so a locked achievement still shows how close the athlete is (e.g. "70 / 100 kg"), rather than just a binary yes/no. The brainstorm's "Climber" (1,000 m elevation in a month) is excluded outright — `RunRecord` doesn't capture elevation, and this repo's convention is to decline rather than approximate when the data genuinely isn't there.

`GET /api/v1/coach/achievements` exposes this under the existing `coach` router. On the Flutter side, an "Achievements" card on the Coach screen shows all eight (locked and unlocked) with a trophy/lock icon, title, description, and progress label — deliberately showing the full list rather than hiding un-attempted ones, so it reads as "here's what you could earn," matching typical achievement-system UX without inventing any scoring.

## Consequences

- Zero fabrication risk: every number here already existed somewhere in `GymService`/`RunningService`; this slice only composes and thresholds it.
- The Level System (Strength/Endurance/Consistency/Recovery composite) remains unbuilt, with the reasoning above on record specifically so a future attempt has to either find a real basis for Strength (bodyweight capture, or an opt-in strength-standards reference) or explicitly accept the fabrication tradeoff — not silently skip past it.
- This surfaced a genuine, previously-recurring test flake: `test_training_load.py`/`test_coach.py`/`test_ask_siris.py` relied on random-year date scoping within a shared dev database to avoid cross-test collisions (ADR 069/070/071's documented tradeoff). Since this slice was already touching those files, all three were converted to the same fully-isolated-per-test-database pattern the health/conflict/achievement suites already use (`tmp_path`/`monkeypatch`), eliminating the flake class entirely rather than continuing to widen the odds. Verified stable across 11 consecutive full-suite reruns.
- Achievement thresholds (100 kg, 1,000,000 kg, 25:00, 4 days/8 weeks, 5 sessions) are fixed constants, not configurable or tiered. A natural, explicitly-deferred follow-up is additional tiers (150 kg, 200 kg; 250k/500k kg) for athletes who've already cleared the first threshold — not built now, to keep this slice's scope matched to the brainstorm's own named examples.
