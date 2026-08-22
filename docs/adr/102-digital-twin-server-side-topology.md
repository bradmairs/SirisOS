# ADR 102 — Digital Twin Server-Side Canonical Topology

## Status

Accepted.

## Context

The Digital Twin's dependency graph (`apps/mobile`'s `DependencyGraph`, ADRs 027-028) has always been client-local: the built-in node/edge catalog is a hardcoded Dart list, and any user-declared custom edge (self/duplicate/cycle-validated on add) persisted to that one device's `SharedPreferences`. The roadmap named the gap directly under 0.4.3j: "Server-side canonical topology." A topology declaration like "Docker host is powered by the UPS" is homelab-wide infrastructure fact, not a personal preference -- unlike ADR 099's manual context override (deliberately kept client-only), it should be visible from any session against the same backend, the same reasoning ADR 100/101's incident lifecycle already applied.

"Arbitrary custom nodes" is a separate, larger, not-yet-designed roadmap item (letting a user declare a node this fixed catalog doesn't know about) -- this change does not touch it. The node/built-in-edge catalog stays a fixed, hardcoded list on both sides.

## Decision

New backend module `apps/backend/app/api/digital_twin.py` mirrors `DependencyGraph`'s node-id catalog and built-in edges exactly, and re-implements its self/cycle validation in Python (ported 1:1 from the same DFS active-set algorithm). `GET /api/v1/digital-twin/topology` returns built-in edges plus all persisted custom edges; `POST /api/v1/digital-twin/edges` validates and appends (idempotent on an exact duplicate -- returns the existing edge rather than erroring, matching the Dart client's prior no-op-on-duplicate behavior); `DELETE /api/v1/digital-twin/edges/{key}` removes one; `DELETE /api/v1/digital-twin/edges` clears all (backing the existing "reset topology" UI action, which had no prior single-edge-only backend equivalent). Same JSON-file-persisted, atomic-write, JWT-bearer-authenticated shape as `recommendations.py`/`incidents.py`, with a `MAX_CUSTOM_EDGES = 200` bound.

`DependencyGraph` keeps its node catalog, downstream-impact traversal and cycle-detection logic untouched -- only its persistence source changed, from `SharedPreferences` to a new `DigitalTwinService` HTTP layer (`apps/mobile/lib/src/services/digital_twin_service.dart`), matching the constructor-injected-service pattern `ProjectContextProvider` already established for `core/` classes that need I/O. `addCustomEdge` still runs its local cycle check first for instant feedback, but the server independently re-validates against its own current state -- important now that the topology is shared, since another session could have changed it since this client last fetched. A `@visibleForTesting debugService` setter on the singleton lets `dependency_graph_test.dart` inject an in-memory fake rather than hitting a real backend; the existing test assertions (cycle rejection, downstream impacts, dedup) carry over unchanged, since the public API (`load`/`addCustomEdge`/`removeCustomEdge`/`resetCustomEdges`) kept its exact prior signature and `DependencyGraphException` contract.

## Consequences

- A topology backend that's unreachable or unconfigured degrades to built-in edges only (`_refetch` catches and clears rather than propagating) -- the same fail-open posture every other integration in this app already has, not a new pattern.
- Cross-device consistency: declaring "Docker depends on the UPS" from one session is now visible from any other against the same backend, closing the gap incident lifecycle (ADR 101) already closed for a different feature.
- `DependencyEdge.toJson()` was dead code once `SharedPreferences` persistence was removed (nothing else called it) and was deleted rather than kept around unused.
- Backend: 11 new tests (`test_digital_twin.py`) covering auth, an empty starting topology, adding a valid edge, self-dependency rejection, unknown-node rejection, duplicate idempotency (both against a custom edge and against a built-in one), cycle rejection, single-edge removal, removing a nonexistent edge, and reset-all. Full suite: 349 tests pass.
- Flutter: `dependency_graph_test.dart` rewritten against a fake `DigitalTwinService` -- all prior assertions preserved, plus new coverage for idempotent re-add, edge removal clearing its downstream impact, and backend-unreachable degradation. `flutter analyze` clean, full suite (69 tests) passes.
