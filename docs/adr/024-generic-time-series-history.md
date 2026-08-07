# ADR 024 — Generic Time-Series History Engine

## Status

Accepted.

## Context

SirisOS integrations increasingly need trend and history data: UPS runtime degradation, storage growth, Synology volume usage, backup protection history, Docker resource behaviour, and later anomaly/incident correlation. Implementing a separate history table and API for every connector would duplicate retention, sampling, querying, and client logic.

Prometheus remains the right tool for high-frequency infrastructure metrics, but SirisOS also needs a small durable history of operational observations that is available even when a source system has no metrics backend.

## Decision

Introduce a generic PostgreSQL-backed `TimeSeriesHistoryService` using a single `time_series_observations` table.

Each observation is identified by:

- `source`
- `metric`
- canonical string dimensions
- observation timestamp

An observation may carry a numeric value, a short text value, or both. Producers choose a conservative minimum sampling interval. The service enforces retention centrally (90 days by default).

The authenticated `GET /api/v1/history` endpoint provides bounded queries by source, metric, time window, optional exact dimensions, and result limit. Flutter consumes this through a shared `HistoryService`.

Initial producers are host storage, Synology volumes, Hyper Backup task state, and NUT UPS state. Existing dedicated host history remains in place until it can be migrated safely; the generic engine is not intended to replace Prometheus for high-frequency telemetry.

## Consequences

- New modules can gain persistent history without defining new database schemas.
- Operations Center, trend widgets, anomaly detection, Incident Engine, and Digital Twin work can share one data contract.
- Sampling remains intentionally low frequency to bound PostgreSQL growth and UI/API load.
- History persistence must not become a reason for external integration polling to become more frequent.
- Automatic shutdown or other safety-critical actions must never be triggered directly from raw history observations; they require explicit policy/orchestration layers.
