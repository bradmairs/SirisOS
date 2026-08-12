# ADR 065 — Action Framework v1

## Status

Accepted.

## Context

The roadmap describes an "Action Framework bound to stable capability IDs" so planners, playbooks and a future Hermes agent can target a capability by a stable name rather than a provider-specific implementation (README rule #19). ADR 030 already established `SirisCapability`/`SirisCapabilityRegistry` in Flutter (`apps/mobile/lib/src/core/capability_registry.dart`) — but that ADR is explicit that the registry is "discovery only: it does not execute commands." It's a hardcoded, client-side, in-memory list with no backend counterpart, the same pattern this sprint already hit once with the Incident Engine and Notification Policy engine (ADR 064).

Investigation before implementation found the backend already has two working, real action-execution primitives — `DockerMonitor.action()` (start/stop/restart, with `PROTECTED_CONTAINERS` enforcement and full audit via `HomelabAuditService` + `ActivityService`) and `HomeAssistantService.call_service()` (domain/service allow-listed device control) — but neither is exposed behind a stable capability ID, and the Home Assistant path had no audit trail at all despite executing real device commands, unlike the Docker path.

## Decision

Add `app/api/actions.py`: a server-side capability registry (`_CAPABILITIES: dict[str, tuple[ActionCapability, handler]]`) with exactly the capabilities that already have proven, audited execution — `docker.start`, `docker.stop`, `docker.restart`. Each handler is a thin wrapper delegating directly to the existing `docker_monitor.action()` (imported from `app.main`, the same instance the legacy Docker route already uses) — no new execution or audit logic invented, just a stable-ID front door onto what's already real.

`GET /api/v1/actions` lists registered capabilities (id, title, description, provider_id, risk, `requires_confirmation`). `POST /api/v1/actions/{capability_id}/execute` takes `{params, confirm}`; a capability with `requires_confirmation: true` (stop/restart — medium risk) rejects the request with 400 unless `confirm: true` is explicitly set, and unknown capability ids return 404. This is server-side enforcement of confirmation, not just a client-side dialog the caller could skip by hitting the API directly — a concrete instance of README rule #22 ("must not use approval bypasses"): there is no way to execute a confirmation-required capability without the caller affirmatively asserting confirmation in the request itself.

Separately, fixed the audit gap found during research: `home_assistant_action` (`app/api/homelab_alerts.py`) now records an `ActivityService` event on every outcome — success, rejected (400), and failed (502) — matching the "audit every outcome, not just success" pattern `DockerMonitor.action()` already established. This wasn't folded into the new capability registry (Home Assistant control isn't onboarded as a capability id in v1) — it's a narrower, independent fix to close a real "auditable" gap without expanding this slice's scope.

## Consequences

- SirisOS now has one real answer to "what can a future Hermes/playbook actually invoke by a stable ID" — three capabilities, all backed by already-audited execution, rather than the Flutter-only aspirational list ADR 030 left behind.
- The Flutter `SirisCapabilityRegistry` is unchanged and still discovery-only; nothing in the app UI calls the new `/api/v1/actions` endpoints yet. Wiring a Recommendation's `suggested_action` to a specific capability (so a recommendation gets a "Run this" button) is explicitly deferred — a decision made with the user before implementation, to avoid getting the first case of "a recommendation drives a real action" wrong under time pressure.
- Home Assistant device control is not yet a capability in this registry — it stays a directly-called endpoint, now at least audited. Bringing it into the capability registry (with its own allow-listed action set) is natural follow-up work once the client actually needs it.
- Coverage is deliberately narrow: three Docker container lifecycle actions. Every future capability added here should have the same property — a real, already-working, already-audited execution primitive underneath it — rather than the registry ever becoming a list of things SirisOS merely intends to be able to do.
