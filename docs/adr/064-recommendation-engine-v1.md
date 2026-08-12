# ADR 064 — Recommendation Engine v1

## Status

Accepted.

## Context

The roadmap's suggested Sprint 0.7 sequencing places a deterministic recommendation engine between Siris Memory and the Action Framework: "Observation → Rule/Policy → Recommendation → Evidence → Capability → Action." The initial plan was for this to evaluate the existing Incident Engine (`apps/mobile/lib/src/core/incident_engine.dart`) and Notification Policy engine (`apps/mobile/lib/src/core/notification_policy.dart`) as its observation source, since those already correlate and prioritize operational conditions.

Investigation before implementation found this premise doesn't hold: both engines are entirely client-side Flutter, computed synchronously and in-memory per app instance, with zero backend representation and zero persistence — there is no incident or policy-outcome data for a Python backend rule engine to read. Porting that stateful debounce/escalate timing logic to the backend would be a substantial, risky undertaking (a second implementation of the same state machine to keep in sync with Flutter's), and a poor fit for a v1 slice.

The backend does already compute something real and evidence-grounded: `GET /api/v1/homelab/alerts` (`app/api/homelab_alerts.py`), which deterministically derives severity/source/title/message from live host metrics and Docker state on every request, with no persistence of its own.

## Decision

Build v1's only rule as a direct mapping from `homelab_alerts` output to `Recommendation` records — `app/api/recommendations.py`. `GET /api/v1/recommendations` calls `homelab_alerts.alerts()` directly (the existing cross-module private-function-import convention, matching `search.py`), reconciles the resulting candidates against a persisted atomic-JSON store (same `_load`/`_save` tempfile+rename pattern as every other record store this sprint) keyed by a stable id derived from the alert's own already-stable id (`rec-{alert.id}`), and returns the merged list.

Reconciliation semantics: a candidate not seen before is new (`status: "pending"`, and emits one `ActivityService` event so it surfaces in the notification feed); a candidate matching a persisted id keeps its stored `status`/`created_at` so a user's dismiss/act decision survives across polls; a persisted id with no matching candidate (the underlying alert cleared) is dropped — the recommendation is evidence-based, so no evidence means no recommendation, not a permanently-dismissed but immortal record. `PATCH /api/v1/recommendations/{id}` moves a recommendation between `pending`/`dismissed`/`acted`.

`suggested_action` is a small deterministic string lookup keyed on the alert id's shape (host vs. container vs. Docker-unavailable) — a human-readable next step, not an executable capability. The Action Framework (future Sprint 0.7 work) is what turns a suggestion into something SirisOS can actually do; v1 deliberately stops short of that.

Surfaced in Operations Center as a new "Recommendations" panel (`OperationsCenterScreen`), between Active Incidents/Integrations and "What needs attention" — evidence → recommendation → dismiss/act in one place, following the same `SirisPanel`/`SirisStatusChip` design-system pattern as every other panel on that screen.

## Consequences

- Coverage is intentionally narrower than "every incident SirisOS could reasonably flag": today it's exactly what `homelab_alerts` already computes (host resource thresholds, Docker container health/updates, Docker availability). Cross-source correlation and escalation-duration-aware rules (the full Incident Engine's capabilities) remain future work once there's a real backend representation to build on — this ADR does not attempt to replicate that.
- No new observation infrastructure was built — reusing an existing, already-deterministic backend endpoint kept this a one-file slice instead of a multi-system port.
- The persisted store is self-pruning: it never accumulates recommendations for alerts that no longer exist, so it doesn't need a retention/expiry policy beyond `MAX_RECOMMENDATION_RECORDS`.
- This is the first SirisOS surface where "Siris noticed something and suggests a next step" exists as a real, evidence-linked object with a lifecycle (pending/dismissed/acted) — Siris Inbox (next in the roadmap sequencing) can build directly on this shape rather than inventing its own.
