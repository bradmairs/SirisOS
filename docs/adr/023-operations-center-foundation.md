# ADR 023 — Operations Center foundation

## Status

Accepted.

## Context

Mission Control answers the ambient question "what is happening now?" but SirisOS also needs a focused operational surface that answers "what needs my attention?". Integration health and Notification Policy state already exist as deterministic SirisCore sources of truth.

## Decision

Operations Center is an authenticated Flutter route at `/operations` that composes existing SirisCore state rather than introducing a parallel monitoring backend.

The foundation reads:

- `SirisIntegrationManager` for connector registration and health
- `NotificationPolicyEngine` for active policy outcomes
- `SirisEventBus` for integration/policy change notifications

It presents:

- operational overview counts
- active incidents derived from active Notification Policies
- live integration health
- a prioritised attention queue
- explicit manual integration refresh

The screen performs no periodic polling of its own. Connector refresh remains owned by the Integration Framework and Scheduler.

## Consequences

- Operations Center stays deterministic, fast and consistent with Mission Control.
- No new credentials, backend aggregation endpoint or database schema are required.
- Active incidents currently map one-to-one to policy outcomes; cross-system incident correlation is a later Incident Engine concern.
- Historical incidents, trends and maintenance workflows require the planned Time-Series/History Engine and persistent operational models.
