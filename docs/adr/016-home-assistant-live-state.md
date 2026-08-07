# ADR 016 — Home Assistant live state and safe controls

## Status

Accepted.

## Context

The Home Assistant connector foundation used bounded REST snapshots. That was reliable and kept credentials server-side, but it introduced unnecessary latency for state changes and did not provide a useful entity-control surface inside SirisOS.

Home Assistant exposes an authenticated WebSocket API at `/api/websocket` and supports subscribing specifically to `state_changed` events. SirisOS also needs to preserve the Integration Framework rule that third-party credentials do not reach Flutter and external integrations cannot block the core app.

## Decision

The SirisOS backend owns the Home Assistant WebSocket connection.

- `HOME_ASSISTANT_URL` and `HOME_ASSISTANT_TOKEN` remain backend-only.
- The backend authenticates the WebSocket and subscribes to `state_changed`.
- Incoming events update an in-memory entity cache and sequence.
- REST `/api/states` supplies initial state and validates availability while the stream reconnects.
- Flutter reads the authenticated SirisOS state endpoint, which is normally served from the live cache.
- The `HomeAssistantConnector` refresh interval is reduced to five seconds because its normal read is local to the SirisOS backend.
- The dedicated `/home-assistant` screen refreshes the cached view every two seconds for a near-live control surface.
- SirisOS service actions are allow-listed server-side. The first supported controls are lights, switches, input booleans, and covers.
- Arbitrary Home Assistant domain/service combinations are rejected even if a modified Flutter client attempts to submit them.

## Consequences

State changes become visible to SirisOS without repeatedly polling Home Assistant REST endpoints, while the HA token remains protected by the API boundary. A failed WebSocket connection degrades to bounded REST checks instead of breaking the dashboard or authentication flow.

The Flutter client does not maintain a direct Home Assistant WebSocket. This is intentional: SirisCore remains independent of Home Assistant transport details and there is one trusted credential boundary.

Future work can add a SirisOS-native push channel between the API and Flutter without changing the Home Assistant connector contract or moving the HA token into the client.
