# ADR 066 — Progressive Overload v1

## Status

Accepted.

## Context

Sprint 0.9 (a user-supplied Running/Gym brainstorm incorporated into the roadmap) calls out Automatic Progressive Overload as "one of the best potential features": after a comfortable session, suggest an increase; after a struggled session, suggest repeating the weight rather than blindly increasing. Auditing the existing Gym module before implementing found this already partially existed — but only as a client-side-only Dart heuristic in the workout form (`+2.5 kg` if the previous session's reps met the template's target at RIR ≥ 2), with no backend representation, no persistence, and — critically — no handling of the "struggled" case at all. A session with dropping reps and near-failure effort got exactly the same `+2.5 kg` treatment as a comfortable one. This is the same category of gap already found and fixed three times this sprint (Notification Policy/Incident Engine, Home Assistant audit, Flutter-only capability registry): logic that should be a stable, reusable server-side fact was living only in one client screen.

## Decision

Add `GymService.suggest_progressive_overload(exercise)` (`app/services/gym_service.py`), reasoning deterministically from the exercise's own most recent logged session only (no template dependency, no Ollama): grouped by `workout_id` (added to `ExerciseHistoryPoint` for precise session grouping, replacing an implicit date/name proxy), it compares first-set vs. last-set reps and the session's minimum RIR.

- Reps dropped across the session, or any set hit RIR ≤ 1 (near failure) → **repeat**: suggest the same weight, reasoning from the exact rep/RIR sequence observed.
- Reps held steady or grew, and RIR stayed ≥ 2 throughout (or wasn't recorded) → **progress**: suggest `+2.5 kg`, targeting the lowest rep count achieved in that session.
- No RIR data and reps didn't clearly grow → **repeat**, conservatively.
- No prior sets for the exercise → **no_data**.

Exposed via `GET /api/v1/gym/exercises/{exercise_name}/suggestion`. The Flutter workout form (`gym_screen.dart`) now calls this per template exercise instead of computing its own heuristic over `GET /gym/exercises`, and the per-exercise "Exercise Intelligence" detail page (`exercise_progress_screen.dart`) gets a new "Next session suggestion" card so the suggestion is visible even for ad-hoc workouts started without a template.

v1's known limitation, stated plainly rather than engineered around: it assumes straight-set training at a roughly consistent weight per session. A pyramid session (ascending weight, naturally falling reps) would be read as "struggled" today, since weight isn't part of the comparison. This is left for real usage data to inform rather than guessed at now — the roadmap's own instinct throughout this sprint has been to ship the simple, honest version first.

## Consequences

- The workout form's suggestion is now evidence-backed and reasoned, not just a flat increment — and correctly recommends repeating a weight after a rough session, closing the gap the brainstorm specifically called out.
- The suggestion logic exists exactly once, server-side, reusable by any future surface (Siris Coach, "Ask Siris" training queries, a future Action-Framework-bound "log this weight" capability) rather than being re-derived per screen.
- `ExerciseHistoryPoint` now carries `workout_id` — a small, additive schema change to the existing dataclass that makes session-grouping exact instead of a date/name proxy.
- Pyramid/pre-fatigue/pyramid-adjacent training styles aren't distinguished from a struggled straight-set session yet; this is documented, not silently wrong.
