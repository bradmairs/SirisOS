# ADR 040 — Read-only Knowledge vault foundation

## Status
Accepted

## Context
Sprint 0.5.0 introduces a personal Knowledge Platform. The first requirement is to make an existing Markdown/Obsidian-compatible vault useful inside SirisOS without creating a second source of truth or risking accidental note modification.

## Decision
- Mount the configured host vault read-only into the unified `sirisos` container at `/app/data/knowledge`.
- Keep Markdown files as the canonical source of truth; no database copy is required for the foundation slice.
- Expose authenticated overview, search and single-note read endpoints under `/api/v1/knowledge`.
- Ignore hidden directories such as `.obsidian` during normal note discovery.
- Bound per-note reads and total scanned files through configuration.
- Resolve requested note paths beneath the configured vault root and reject traversal outside it.
- Extract lightweight metadata required by future features: first H1 title, frontmatter tags, daily-note classification and Obsidian-style `[[wikilinks]]`.
- Keep the first Flutter Knowledge module read-only. Editing, write-back, backlink traversal, graph visualization and semantic indexing are separate follow-on decisions.

## Consequences
SirisOS can immediately browse and search a local or host-mounted Obsidian-compatible vault while preserving the user's existing note workflow. A Synology-hosted vault can be exposed through an existing host mount and then referenced by `SIRISOS_KNOWLEDGE_HOST_PATH`. Future indexing or AI retrieval must retain the Markdown path as provenance rather than silently replacing the vault with a separate knowledge store.
