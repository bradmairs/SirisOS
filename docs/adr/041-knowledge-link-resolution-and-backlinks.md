# ADR 041 — Knowledge link resolution and backlinks

## Status
Accepted

## Context
The read-only Knowledge vault foundation exposes Obsidian-style `[[wikilinks]]`, but a useful knowledge system needs deterministic navigation and backlinks without silently resolving ambiguous note names to the wrong file.

## Decision
- Keep Markdown files in the mounted vault as the source of truth.
- Resolve a wikilink in this order: explicit vault-relative path, source-note-relative path, then a unique filename stem or note title match.
- If filename/title matching produces multiple candidates, return an ambiguous result and require the user to choose rather than guessing.
- Build backlinks from resolved wikilinks using the same resolution rules.
- Build one bounded in-memory link index per relationship request rather than introducing a persistent database/indexing daemon at this stage.
- Support both frontmatter tags and inline Obsidian `#tags` for browse/filter surfaces.
- Folder and tag browsing remain read-only views over the vault.

## Consequences
Wikilink and backlink navigation has deterministic provenance and can later feed graph visualization, related-note ranking and SirisAI context. A persistent index may be introduced when vault size or semantic search warrants it, but it must preserve these resolution semantics and the vault-as-source-of-truth boundary.
