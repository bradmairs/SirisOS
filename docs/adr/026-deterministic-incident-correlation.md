# ADR 026 — Deterministic Incident Correlation

## Status
Accepted

## Context

Notification Policies intentionally describe individual conditions. Operations Center previously rendered those outcomes one-for-one, which made related failures appear as separate incidents and forced the operator to infer the shared context.

SirisOS needs a correlation layer that remains deterministic, explainable, and safe before richer dependency/Digital Twin reasoning exists.

## Decision

Add a Flutter-side `IncidentEngine` that derives active incidents from current Notification Policy outcomes and Integration Manager health.

The engine uses explicit correlation rules. UPS `on_battery` or `low_battery` outcomes anchor a power incident; concurrent infrastructure failures are attached as possible impacts. Remaining outcomes are grouped into stable subsystem categories such as compute, storage/backup, network, observability, and Home Assistant. Unmatched outcomes remain visible as standalone incidents.

Each incident exposes its source policy outcomes, affected integrations, severity, start time, and a human-readable correlation reason. Raw policy outcomes remain visible in the Operations Center attention queue.

Correlation does not claim causation. The initial power rule uses the UPS power-state signal as an explicit anchor and describes attached failures as possible impacts. Cross-system causal reasoning is deferred to the planned dependency/Digital Twin graph.

## Consequences

- Operations Center can present fewer, more meaningful incidents without hiding source evidence.
- Incident IDs are stable for future persistence/history work.
- Correlation stays testable and explainable without AI.
- The engine can later consume dependency-graph context without changing Notification Policy producers.
- Historical incident lifecycle/persistence is intentionally deferred.
