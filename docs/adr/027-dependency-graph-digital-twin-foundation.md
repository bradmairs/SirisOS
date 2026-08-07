# ADR 027 — Deterministic Dependency Graph / Digital Twin Foundation

## Status

Accepted.

## Context

The Incident Engine correlates conditions that occur together, but correlation alone does not prove that one component depends on another. SirisOS needs a separate representation of explicit system relationships before it can make stronger downstream-impact statements.

## Decision

Introduce a deterministic in-process `DependencyGraph` with typed nodes and directed dependency edges. An edge means the dependent node requires the dependency node to function. The graph supports transitive downstream traversal and deduplication across multiple roots.

Only relationships that SirisOS can explicitly justify are declared. The initial graph contains the known software chain `Synology -> Hyper Backup -> Backup Protection Analytics`. It intentionally does not assert physical power or network relationships such as `UPS -> Docker` or `UPS -> UniFi` until those relationships are explicitly configured or otherwise known.

The Incident Engine attaches graph-derived downstream impacts to incidents separately from correlated/affected integrations. Operations Center labels these as `Declared downstream` so users can distinguish dependency evidence from correlation.

## Consequences

- SirisOS can begin deterministic downstream impact reasoning without AI inference.
- Incident correlation and dependency causality remain separate concepts.
- Transitive impacts can be computed consistently for future services and modules.
- Physical topology remains incomplete until a configuration/discovery layer is added.
- Future Digital Twin work can add editable relationships, dependency visualization, dynamic discovery, recommended actions and historical impact analysis without changing the Incident Engine contract substantially.
