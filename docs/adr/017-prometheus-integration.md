# ADR 017 — Prometheus integration

## Status
Accepted

## Context
SirisOS needs broader infrastructure observability without coupling Flutter directly to third-party monitoring systems or making an optional Prometheus server part of the core boot path.

## Decision
Prometheus is implemented as an optional `SirisConnector` backed by authenticated SirisOS API endpoints.

- `PROMETHEUS_URL` is stored only in backend environment configuration.
- The backend exposes a short-lived cached target-health snapshot and an authenticated instant PromQL query endpoint.
- The snapshot uses the standard `up` metric to derive healthy/down target counts.
- Snapshot results are cached for 15 seconds to avoid duplicate Prometheus queries from connector and widget refreshes.
- The Flutter connector refreshes every 15 seconds, publishes Homelab events only on meaningful changes, and reports an unconfigured installation as disabled rather than failed.
- Notification Policies cover Prometheus unavailability and scrape targets remaining down.
- Mission Control consumes Prometheus through the shared Widget Registry and Siris design system.
- External integration startup remains asynchronous and may never block authentication or the core dashboard.

## Consequences
Prometheus remains optional and existing installations require no new container or migration. SirisOS gains a reusable read-only PromQL boundary for future dashboards and diagnostics while credentials/endpoints remain server-side. Grafana can be integrated separately without changing this connector contract.
