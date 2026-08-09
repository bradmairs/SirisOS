# ADR 054 — Local Knowledge Graph UI

## Status

Accepted.

## Context

ADR 043 established a deterministic, local Knowledge Graph contract — a bounded projection centered on the open note, built from the same read-only wikilink/backlink/tag/folder scan used by related-note ranking. The backend `GET /api/v1/knowledge/graph` endpoint and the Flutter `KnowledgeGraph`/`KnowledgeGraphNode`/`KnowledgeGraphEdge` client models existed, but no screen rendered them; the graph was reachable by API only.

## Decision

The Knowledge note viewer gains a "View Knowledge Graph" action that opens `KnowledgeGraphScreen`, a dialog showing the same radial node/edge visualization pattern already established by the Project Context Graph (ADR 052): a `CustomPaint` layout centered on the current note, with typed edges (outgoing link, backlink, shared tag, same folder) distinguished by icon and stroke weight, plus a relationship list below the canvas for small screens and for actually opening a related note.

The graph remains read-only and local to the centered note; tapping a related note opens it directly rather than silently re-centering the graph, keeping navigation explicit. No new backend surface was needed — this slice only adds the Flutter rendering layer over the existing contract.

## Consequences

- Sprint 0.5.0's "Graph visualization" item is now genuinely complete rather than backend-only.
- The visualization pattern (radial `CustomPaint` layout, legend chips, list fallback) is now shared verbatim between Knowledge and Projects, reducing future maintenance if either evolves.
- No new persistence, indexing, or inference is introduced; the graph remains bounded and deterministic per ADR 043.
