# ADR 052 — Project Context Graph projection

## Status

Accepted.

## Context

Sprint 0.6 now has stable project identities, explicit current-project context, and typed Project ↔ Knowledge relationships. The next step is to make those relationships visible as a graph without introducing inferred edges or a separate graph database prematurely.

## Decision

SirisOS exposes a bounded authenticated `GET /api/v1/projects/{project_id}/graph` projection over the authoritative project record and its stored typed relationships.

The first graph contains:

- one project root node;
- Knowledge note nodes addressed by canonical vault-relative path;
- `contains` and `references` edges;
- manual provenance carried on every edge.

The projection is derived at request time from the existing project and relationship stores. It is bounded to 100 relationships per project for the first implementation. No graph database, background indexer, vector store or AI-generated relationship is introduced.

Flutter adds a Projects → Graph view centered on the explicitly selected current project. The visual graph is a local deterministic rendering of the backend projection and includes a relationship list beneath it so the graph remains understandable on small/mobile screens.

## Consequences

- Users can see the first real SirisOS Project Context Graph immediately.
- The graph cannot silently invent project membership.
- Future typed targets such as calculations, tasks, files, events, repositories and conversations can extend the same node/edge contract.
- A richer semantic Knowledge Graph can be layered later without replacing authoritative typed relationships.
