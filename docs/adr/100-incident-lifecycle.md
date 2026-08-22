# ADR 100 — Incident Lifecycle (Acknowledge / Assign / Resolve / History)

## Status

Accepted.

## Context

The Incident Engine (`apps/mobile`'s `IncidentEngine`, ADR 026) is a pure, stateless correlation function: on every Operations Center build it recomputes the current incident list fresh from `NotificationPolicyEngine.activeOutcomes` and `SirisIntegrationManager.health`. Nothing about an incident persists -- there is no way to acknowledge one, note who's on it, mark it resolved, or see what was resolved yesterday once its underlying policy condition clears and it silently drops out of the live list. The roadmap named both gaps directly under 0.4.3i: "Persist incident lifecycle/history" and "Acknowledge/assign/resolve workflow".

Unlike Recommendations (ADR 064), which already has a backend `/api/v1/homelab/alerts` source it reconciles against on every poll, the Incident Engine has no backend representation at all -- the correlation logic (power-outage anchoring, category grouping, dependency-impact enrichment) only exists in Dart. Rebuilding that logic backend-side just to get persisted lifecycle state would be a large, unrequested re-architecture solving a problem the roadmap bullet didn't ask to solve.

## Decision

The correlation engine is untouched. A new backend module, `apps/backend/app/api/incidents.py`, tracks only the human-facing lifecycle for whatever incident id the client is currently showing -- it never discovers incidents on its own. `SirisIncident.id` is already deterministic and stable for as long as the same category of incident stays active (`incident.power`, `incident.compute`, `incident.policy.<outcome id>`, etc.), so that id is the join key.

- `GET /api/v1/incidents` -- lists every persisted lifecycle record, active or not. Because records are never deleted once created, this list *is* the history: a resolved incident whose underlying condition later cleared (and so no longer appears in the client's live `correlate()` output) stays visible here.
- `PATCH /api/v1/incidents/{incident_id}` -- upserts: creates a record on the first call for an id that's never been seen, updates it otherwise. Body: `status` (open/acknowledged/resolved), optional `assigned_to` (freeform text -- SirisOS is single-admin, so this is a label, not a real multi-user permission target), optional `notes`.
- Same JSON-file-persisted, atomic-write, JWT-bearer-authenticated shape as `recommendations.py`, including a `MAX_INCIDENT_LIFECYCLE_RECORDS = 500` bound.
- Timestamp rules: `acknowledged_at` is stamped once and kept; `resolved_at` refreshes on every resolution and backfills `acknowledged_at` if the incident jumped straight from open to resolved; reopening (`status: "open"`) clears both, a deliberate fresh start rather than carrying stale timestamps into a later recurrence of the same incident id.

Flutter: `IncidentLifecycleService` (list/update) and `IncidentLifecycleRecord` model, matching `RecommendationService`'s shape. `_IncidentPanel` in Operations Center became stateful -- it fetches lifecycle records alongside the live, always-synchronous incident list and joins them by id. The live list is authoritative and renders immediately regardless of lifecycle-fetch state (loading or failed), so lifecycle is strictly additive enrichment, never a gate on seeing what's actually active. Each row gets Acknowledge/Resolve/Reopen actions; a resolved-but-still-live incident is flagged explicitly ("Marked resolved but the underlying condition is still active") rather than silently hidden. A "Recently resolved" section lists up to 5 records that are resolved and no longer in the live list -- the actual history view.

## Consequences

- Cross-device consistency: because lifecycle now lives backend-side (not client `SharedPreferences`, unlike ADR 099's manual context override), acknowledging an incident on one device is visible from any other session against the same backend -- deliberately chosen over the ADR 099 pattern because incident response genuinely benefits from that, where a personal context assertion doesn't.
- The backend has no opinion on whether an incident is "real" right now -- a lifecycle record can exist for an id the client never currently shows (already resolved and cleared) or can be marked resolved while the client still shows it live (flagged, not hidden). This honesty was a deliberate choice over trying to keep the two in lockstep, which isn't possible without moving correlation itself server-side.
- Backend: 8 new tests (`test_incidents.py`) covering auth, empty list, create-on-first-acknowledge, backfilling `acknowledged_at` on a skip-straight-to-resolved, `acknowledged_at` staying put across a later resolve, reopen clearing both timestamps, resolved records staying listed as history, and two distinct incident ids not disturbing each other. Full suite: 338 tests pass.
- Flutter: 2 new tests (`incident_lifecycle_service_test.dart`, covering `IncidentLifecycleRecord.fromJson` parsing and its fallback for an unrecognised status). No widget test for `_IncidentPanel`'s async fetch/merge -- matching this codebase's existing precedent of not widget-testing `RecommendationService`'s equivalent HTTP-backed panel either. `flutter analyze` clean, full suite (66 tests) passes.
