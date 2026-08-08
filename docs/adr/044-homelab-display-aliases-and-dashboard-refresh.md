# ADR 044 — Homelab display aliases and stable Dashboard refresh

## Status
Accepted

## Decision

SirisOS presentation labels for the monitored Linux host and UPS are independent from their canonical monitoring identities. The Flutter UI receives build-time aliases through `SIRISOS_HOST_DISPLAY_NAME` and `SIRISOS_UPS_DISPLAY_NAME`, defaulting to `Linux Server` and `Server UPS`. Raw node-exporter hostnames and NUT UPS identities remain unchanged for history, policies, incidents and integration logic.

Dashboard background refreshes must preserve the last successfully rendered Dashboard while a refresh is in flight. Notification-state events update the unread notification count only; they do not trigger a full Dashboard fetch. Module-data changes remain eligible for a debounced Dashboard refresh, and overlapping refreshes are coalesced.

## Consequences

The user-facing Homelab names can be changed without breaking historical identity, and frequent background notification events no longer make the Dashboard appear to reload continuously. Tonal circular action buttons also use an explicit high-contrast container/foreground pair through the shared theme.
