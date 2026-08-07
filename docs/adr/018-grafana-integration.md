# ADR 018 — Grafana integration

## Status

Accepted.

## Context

SirisOS needs Grafana dashboard discovery and launch capability without exposing Grafana service-account credentials to Flutter or creating another bespoke integration lifecycle. Grafana 12 introduced the new `/apis/dashboard.grafana.app/...` dashboard API, while older self-hosted versions use the legacy `/api/search` endpoint. Grafana panel PNG rendering also depends on Grafana image rendering being separately configured.

## Decision

Grafana is implemented as an optional `SirisConnector`.

- `GRAFANA_URL` and `GRAFANA_TOKEN` remain in the SirisOS API container.
- Flutter calls only authenticated SirisOS endpoints.
- Dashboard discovery prefers the Grafana 12+ dashboard list API and falls back to legacy `/api/search/?type=dash-db` for compatibility.
- The authenticated `/grafana` SirisOS route exposes searchable dashboard metadata and opens selected dashboards in Grafana.
- A deterministic Notification Policy handles sustained Grafana unavailability.
- Panel rendering is exposed only as an authenticated backend proxy and is disabled unless `GRAFANA_RENDERING_ENABLED=true`.
- Render identifiers and dimensions are bounded before forwarding to Grafana.
- SirisOS does not deploy a Grafana image-renderer container automatically; operators opt into that resource-intensive component separately.

## Consequences

Existing SirisOS installations are unchanged when Grafana is not configured. Credentials remain server-side, older Grafana installations retain dashboard discovery compatibility, and future Mission Control panel snapshots can reuse the render proxy without changing the security boundary. The legacy search fallback can be removed once SirisOS establishes a minimum Grafana version that supports the new API.
