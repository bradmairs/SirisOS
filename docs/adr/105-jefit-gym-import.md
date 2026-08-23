# ADR 105 — JEFIT Gym Data Import

## Status

Accepted.

## Context

Per the 2026-08-22 complement-not-replace product pivot, JEFIT is Brad's system of record for gym logging — SirisOS shifts from being the primary logger to importing JEFIT's own data, feeding the same analytics (Progressive Overload, PRs, Strength Score, Muscle Map, Training Level) that already exist. JEFIT's "Backup & Export" feature produces a single CSV covering the account's entire database (settings, profile history, routines, workout sessions, exercise logs, per-set logs, PRs, cardio, custom exercises, notes) in a multi-section format — `### SECTION NAME #####...` headers, each followed by its own CSV header row and data rows.

A real export (Brad's own, 6.5 years, 859 gym sessions, ~11,200 sets) was used to validate this design before writing any import code, rather than guessing at JEFIT's schema.

## Decision

**Parsing** (`apps/backend/app/services/jefit_import_service.py`) uses only the `EXERCISE LOGS` section — not `WORKOUT SESSIONS` or the more granular `EXERCISE SET LOGS`. Its `logs` field (e.g. `"35x10,45x10,40x10"`, weight×reps per set) is already in the account's own display unit — confirmed against that same row's `record` field, an Epley e1RM computed directly from `logs`' best set with no unit conversion involved. `EXERCISE SET LOGS`' `weight_lbs` column, by contrast, is always in lbs regardless of account unit and would need converting; using `logs` avoids that conversion and the extra join entirely. Sessions are grouped by JEFIT's own `belongsession` id (already present on every `EXERCISE LOGS` row, no need to read the separate `WORKOUT SESSIONS` table for it). JEFIT does not track RIR, so every imported set gets `rir: None`, same as manual logging with RIR left blank.

**Storage**: imported sessions land in the exact same `gym_workouts`/`gym_workout_sets` tables manual logging already uses — `WorkoutModel` gains `source` ("manual" | "jefit") and `external_id` (JEFIT's session id, for idempotent re-import) columns. Because `Base.metadata.create_all()` only creates missing tables and never alters an existing one, and `gym_workouts` already holds real production data, `GymService.initialise()` gained an explicit, idempotent column-add guard (`inspect()` the existing columns, `ALTER TABLE ... ADD COLUMN` only what's missing) — portable across SQLite (tests) and Postgres (production) since it avoids Postgres-only `ADD COLUMN IF NOT EXISTS` syntax. This is the first schema change to an existing SQLAlchemy table in this codebase; there is no Alembic or other migration framework, so this guard is the established pattern going forward for the same situation.

**Idempotency**: `GymService.existing_external_ids("jefit")` is one bulk query returning every already-imported session id; `JefitImportService.import_export()` skips any session already present before importing the rest, so re-uploading the same or a newer export only imports genuinely new sessions.

**Bulk insert, not `create_workout()` in a loop**: `create_workout()`'s per-call "prior bests" PR snapshot (`get_exercise()` → `list_exercises()` → `list_workouts()`, a full rescan of everything logged so far) is fine for one manual log but is O(existing data) per call — calling it in a loop across a historical import became O(n²) overall. Against the real 859-session file this hung past two minutes before being killed. `GymService.bulk_import_workouts()` inserts every workout in one transaction with no per-session rescan; nothing needs `PersonalRecord` events for years-old imported sessions (the API layer only fires one summary activity event per import, not one per historical PR), and every existing analytic still computes PRs/scores correctly afterwards since they're always derived live from `list_workouts()`, never stored at insert time. Fixed, the same real file imports in ~0.5 seconds.

**API**: `POST /gym/import/jefit` (multipart file upload, `SIRISOS_JEFIT_EXPORT_MAX_UPLOAD_MB` size-limited, same pattern as Standards Library PDF upload) returns a summary (sessions imported/skipped, sets imported, date range, any per-session errors) and records one `ActivityService` event when anything new was imported.

**Flutter**: `GymScreen` gained an upload-icon button (file picker restricted to `.csv`/`.txt`) next to the existing "Workout"/templates/progress actions, showing a busy spinner during upload and a result snackbar afterward.

## Consequences

- Live-verified against the real 6.5-year, 859-session, ~11,200-set export through the actual running app (not just tests): imported correctly, idempotent on re-upload (second import: 859 skipped, 0 imported), and every existing Gym screen surface (weekly training load, training volume heatmap, muscle map, exercise progress list with correct best-e1RM/set/workout counts) rendered correctly against the imported data with no code changes to any of them.
- The manual gym logging UI (workout form, templates) is untouched and still fully functional — per the product pivot, it's no longer the primary intended input path, but nothing about this change disables or hides it.
- `bulk_import_workouts()` is a second, leaner insert path alongside `create_workout()` rather than a shared one — deliberately, since manual logging's per-entry PR computation and activity/record surfacing is exactly what a single live log should do, and bulk import exists specifically because that per-call cost doesn't scale to hundreds of sessions at once.
- Backend: 13 new tests (9 in `test_jefit_import_service.py` covering parsing, grouping, idempotency, incremental re-import and shared-analytics compatibility; 4 in `test_gym_jefit_import_route.py` covering auth, size limit, non-UTF-8 rejection and the full route). Existing gym tests (19) still pass unchanged against the migrated schema.
- Flutter: 2 new tests for `JefitImportResult.fromJson`. `flutter analyze` clean.
