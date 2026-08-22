# ADR 096 — Bring Home Assistant device control into the Action Framework

## Status

Accepted.

## Context

Action Framework v1 (ADR 065) shipped with exactly three capabilities — `docker.start`/`stop`/`restart` — and explicitly deferred Home Assistant device control, since that ADR was scoped to capabilities with proven execution already behind them. Home Assistant control has existed as a directly-called endpoint (`POST /api/v1/homelab/home-assistant/action`) since earlier in the project, allow-listed by domain/service in `HomeAssistantService.call_service()` (`light`/`switch`/`input_boolean` turn_on/turn_off/toggle, `cover` open/close/stop), but with no stable capability ID a Planner/Hermes/future automation could target — the same gap ADR 068 closed for Docker via Recommendations.

Separately, ADR 065 fixed the direct endpoint's missing audit trail by recording an `ActivityService` event from inside the route handler (`home_assistant_action`). That fix lived in the wrong layer: it audited calls made *through that one route*, not calls to `HomeAssistantService.call_service()` in general — so a second caller (this ADR's new capability handlers) would have silently skipped audit again, reintroducing the exact gap ADR 065 closed, just one layer removed.

## Decision

Moved audit recording out of the route handler and into `HomeAssistantService.call_service()` itself, matching the precedent `DockerMonitor` already set (`self._activity = ActivityService()` in `__init__`, a `_record()` helper called on every outcome). Every outcome — not configured, rejected by the allow-list, entity/domain mismatch, HTTP failure, or success — now records exactly once, regardless of caller. `home_assistant_action` (the direct REST route) is simplified accordingly; it no longer duplicates audit logic, just maps exceptions to HTTP status codes.

Two new capabilities in `app/api/actions.py`: `home_assistant.control` (light/switch/input_boolean, `risk: low`, no confirmation required — matching the direct endpoint's existing, unchanged behavior) and `home_assistant.cover_control` (cover only, `risk: medium`, confirmation required — a real risk distinction this ADR adds, since covers can be physically consequential — a garage door — in a way a light toggle isn't). Both delegate to the same `HomeAssistantService.call_service()` the direct endpoint already used; no second execution path.

This required `execute_capability`'s dispatch to support async handlers (`home_assistant_service.call_service()` is a coroutine; `docker_monitor.action()` is not) — `_CAPABILITIES`' handler type changed from a plain callable to `Callable[[dict[str, str], str], Awaitable[str]]`, and the three existing Docker handlers were wrapped in trivial `async def` closures to match, calling the (still synchronous) `docker_monitor.action()` inside.

## Consequences

- Every Home Assistant action SirisOS can take now has the same properties Docker actions already had: a stable capability ID, allow-list enforcement, and complete audit — regardless of whether it's invoked through the direct REST route or the Action Framework.
- Audit logic now lives exactly once, at the layer that's actually responsible for it (the service, not each caller) — the same fix pattern as ADR 065, applied one level deeper so it can't recur a third time for a third caller.
- `execute_capability`'s handler type is now async-only; any future capability (even a purely synchronous one) must be wrapped in an `async def`, matching what the three Docker capabilities already do.
- Home Assistant capabilities aren't yet bound to any Recommendation (unlike `docker.start`/`docker.restart`, per ADR 068) — nothing in `homelab_alerts` generates an HA-shaped alert today, so there's no natural recommendation to bind to yet. That remains open, unforced future work.
