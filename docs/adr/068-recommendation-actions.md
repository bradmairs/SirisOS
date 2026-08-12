# ADR 068 — Wire Recommendations to Action Framework capabilities

## Status

Accepted.

## Context

Both ADR 064 (Recommendation Engine v1) and ADR 065 (Action Framework v1) named this as their explicit next step: a Recommendation's `suggested_action` was free text — accurate, evidence-linked, but never anything the user could click to actually run. Action Framework v1 separately built a real, audited execution surface (`docker.start`/`stop`/`restart`) with no caller yet. Closing that gap doesn't require new architecture — both pieces already exist; this just connects them.

## Decision

`app/api/recommendations.py` gains `_capability_binding(alert_id)`, a small deterministic mapping alongside the existing `_suggested_action()` mapping: a `container-*-stopped` alert binds to `docker.start`, a `container-*-unhealthy` alert binds to `docker.restart`, each with `{"container_id": <parsed from the alert id>}` as params. Every other alert shape (host resource alerts, `docker-unavailable`, image-update alerts) gets no binding — there's no registered capability for them, so `Recommendation.capability_id`/`capability_params` stay `null` rather than inventing one. `Recommendation` gained these two nullable fields; the reconciliation logic in `_reconcile()` needed no changes since a fresh candidate's fields (including the binding) always win over the persisted copy except `status`/`created_at`/`updated_at`.

Flutter: a new `ActionService.execute(capabilityId, params)` posts to `/api/v1/actions/{id}/execute` with `confirm: true` — the client always shows its own confirmation dialog first (matching the existing `container_detail_screen.dart` pattern), so setting `confirm: true` unconditionally on the request is safe; the server doesn't trust it blindly, it's just the caller asserting what the dialog already established. When a recommendation has a `capability_id`, its row in Operations Center shows a "Run" button instead of "Mark acted" (running the capability and succeeding marks it acted automatically); a recommendation without a binding keeps the manual Dismiss/Mark acted pair unchanged.

## Consequences

- Two container-lifecycle alert types now go end-to-end: alert → recommendation → one click → real, audited Docker action → recommendation auto-marked acted. Every other recommendation stays descriptive-only, honestly, rather than a capability being force-fit where none exists.
- No new safety surface was introduced — execution still runs through the exact same `POST /api/v1/actions/{id}/execute` endpoint and `PROTECTED_CONTAINERS`/audit logic Action Framework v1 already established; this ADR only adds a caller.
- Extending binding coverage (e.g. Home Assistant capabilities, once ADR 065's "bring HA into the registry" follow-up lands) is now a one-line addition to `_capability_binding` per new capability, not a new pattern.
- Verified end-to-end for the `docker-unavailable` case (correctly no "Run" button, confirmed live); the `-stopped`/`-unhealthy` bindings are covered by backend unit tests (container-state fixtures asserting the exact capability id and params) rather than a live click-through, since this sandbox has no real Docker daemon to produce those alerts naturally.
