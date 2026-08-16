# ADR 078 — Automatic Deload Detection v1

## Status

Accepted.

## Context

Sprint 0.9's SirisGym backlog names Automatic Deload Detection as the natural next step after Progressive Overload and Personal Records: "falling reps, rising RIR-implied effort and a declining e1RM trend across several sessions suggests a lighter week" — depending on nothing but existing set history, no Health data required. Two real judgment calls needed resolving before building it: whether this is a per-exercise signal (like Progressive Overload) or a whole-training-week signal (closer to Weekly Training Load), and how strict the trigger should be. Confirmed with Brad: per-exercise, surfaced on the Exercise Intelligence page like Progressive Overload; and a strict three-signal AND rule over the last 3 sessions, favouring rare, high-confidence flags over a chattier single-signal trigger.

## Decision

`GymService.suggest_deload(exercise)` (new, alongside `suggest_progressive_overload`) groups an exercise's history into distinct sessions (by `workout_id`, preserving chronological order) and takes the last 3. For each session it computes the best estimated 1RM, the first set's rep count, and the minimum RIR recorded (RIR is optional at log time). A deload is recommended only when all three values show a genuine, non-bouncing decline across all 3 sessions (`values[0] >= values[1] >= values[2]` and `values[0] > values[2]`, so a dip-then-recovery session never triggers it). When RIR wasn't recorded for one of the three sessions, the rule falls back to just the e1RM + reps signals rather than refusing to answer — the rationale text says so explicitly either way. Fewer than 3 logged sessions returns `insufficient_data` rather than a guess.

`GET /api/v1/gym/exercises/{exercise_name}/deload` exposes it; the Flutter Exercise Intelligence page fetches it alongside the existing Progressive Overload suggestion and renders a card in the app's `errorContainer` color — visually distinct from the neutral Progressive Overload card — but only when `status == deload_recommended`. `on_track` and `insufficient_data` render nothing, matching the same "don't manufacture content to fill space" principle already applied to Coach and Achievements: this signal is deliberately rare, so staying silent the rest of the time is the point, not an oversight.

## Consequences

- No backend schema changes — reuses the same `gym_workouts`/`gym_workout_sets` tables and `ExerciseHistoryPoint` shape Progressive Overload and Personal Records already read from.
- Verified live end-to-end in the browser: 3 logged sessions with deliberately declining weight/reps/RIR (80kg×8@RIR3 → 80kg×6@RIR1 → 77.5kg×5@RIR0) produced the expected "Consider a deload" card with the correct session dates and signal explanation in the rationale text.
- The strict AND-of-three-signals rule means a real deload situation with, say, steady reps but a climbing RIR and falling e1RM won't trigger v1 — a deliberate false-negative bias over false-positive nagging, consistent with the confirmed scope decision. Loosening it, if it proves too quiet in practice, is a follow-up rather than a redesign.
- Whole-training-week (multi-exercise) deload/fatigue signals remain unbuilt — this is a per-exercise reading only, same boundary Progressive Overload already drew.
