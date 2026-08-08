# ADR 043 — Deterministic related notes and local Knowledge Graph

## Status
Accepted

## Decision

SirisOS derives context-aware related notes from the same bounded, read-only Markdown scan and wikilink index used by Knowledge relationship resolution. No database, background indexing daemon, embedding service or model call is required for this foundation.

Related-note ranking is deterministic and explainable. Resolved outgoing links receive the strongest weight, followed by backlinks, shared tags and same-folder proximity. Each result carries the reasons that contributed to its score so the UI can explain why a note is related.

The first Knowledge Graph is intentionally local rather than vault-wide. It centers on the open note and projects a bounded set of the highest-ranked related notes plus typed relationship edges. This keeps rendering and API work bounded on desktop and mobile while establishing a graph contract that can grow later.

## Safety and source of truth

The vault remains read-only and Markdown remains the source of truth. Graph nodes use vault-relative note paths as stable identities. Ambiguous wikilinks are never silently converted into graph relationships.

## Consequences

Knowledge can now surface useful context without AI and without introducing another persistence layer. Optional semantic/vector recall can later contribute additional explainable candidates behind the same related-note and graph contracts, while deterministic links, backlinks and tags remain available as a fallback and provenance layer.
