# ADR 019 — UniFi Network integration

## Status
Accepted

## Context
SirisOS needs network awareness without exposing UniFi credentials to Flutter or coupling Mission Control to UniFi-specific transport details.

## Decision
UniFi is implemented as an optional `SirisConnector` backed by an authenticated SirisOS API endpoint. The backend owns `UNIFI_URL`, `UNIFI_API_KEY`, optional `UNIFI_SITE_ID`, and TLS verification configuration.

The backend uses Ubiquiti's official local UniFi Network API with `X-API-Key` authentication. It supports both common UniFi OS `/proxy/network/integration/v1` and direct `/integration/v1` roots, discovers a site when no explicit site ID is configured, and caches snapshots for 15 seconds.

The snapshot normalises controller reachability, device online/offline state, access-point count, connected-client count, WAN-interface count, firmware-update flags, and basic device identity. Flutter receives only this normalised SirisOS model.

The connector refreshes every 30 seconds and publishes Homelab events only when meaningful aggregate state changes. Notification Policies handle prolonged controller unavailability and adopted devices remaining offline. The registered `homelab.unifi` widget uses shared SirisOS design primitives.

## Consequences
- Existing installs remain unchanged when UniFi is not configured.
- API keys never enter Flutter persistence or browser requests to UniFi.
- Local self-signed deployments can opt out of TLS verification with `UNIFI_VERIFY_SSL=false`; trusted TLS should enable verification.
- WAN data currently represents interface discovery/availability from the official API, not an inferred Internet-quality score. More detailed latency/ISP health can be layered in later through official UniFi metrics without changing the connector contract.
