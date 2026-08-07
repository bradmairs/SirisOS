# ADR 015 — Home Assistant Connector

## Status
Accepted

## Context

SirisOS already exposed basic Home Assistant connectivity diagnostics, but Home Assistant did not participate in the reusable Integration Framework. The connector also needs to preserve a strict credential boundary and must not reintroduce the dashboard/startup blocking behaviour previously caused by slow external integration work.

## Decision

Home Assistant is implemented as a `SirisConnector` backed by authenticated SirisOS API endpoints.

The FastAPI backend owns `HOME_ASSISTANT_URL` and `HOME_ASSISTANT_TOKEN`. Flutter never receives or persists the Home Assistant token.

The first connector transport uses bounded REST state snapshots every 30 seconds. The connector compares snapshots and publishes `ModuleDataChanged` only when meaningful state or availability changes occur. Direct Home Assistant WebSocket streaming is explicitly deferred as a transport optimisation; the SirisCore event contract does not depend on REST versus WebSocket.

The backend also exposes a constrained authenticated service-action endpoint so future SirisOS entity controls can act without exposing Home Assistant credentials to the client.

Home Assistant conditions use the shared Notification Policy Engine:

- Home Assistant unreachable for 2 minutes: warning.
- Home Assistant unreachable for 10 minutes: critical.
- Three or more unavailable/unknown entities for 2 minutes: warning.

An unconfigured Home Assistant connector reports the shared `disabled` integration state using `SirisConnectorDisabledException` rather than appearing healthy or accumulating failure noise.

Integration startup remains asynchronous. Home Assistant availability must never block authentication, the app shell, Dashboard, or Mission Control.

## Consequences

- Home Assistant follows the same lifecycle, scheduling, event and policy architecture as Docker.
- Credentials remain server-side.
- Mission Control receives Home Assistant changes through existing Homelab events and policy hooks.
- A slow or offline Home Assistant instance degrades only its connector.
- Direct WebSocket streaming and richer entity-control UI can be added later without changing the connector contract.
