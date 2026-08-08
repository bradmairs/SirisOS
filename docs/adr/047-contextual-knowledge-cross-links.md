# ADR 047 — Contextual Knowledge cross-links

## Status
Accepted

## Decision

SirisOS modules may surface Knowledge notes through explicit vault metadata rather than inferred ownership.

The first contexts are Engineering and Homelab. A note is linked to a module by adding a normal Obsidian tag:

```yaml
---
tags: [siris/engineering, stormwater]
---
```

or by using an inline tag such as `#siris/homelab`.

The module UI queries the existing read-only Knowledge search API with the relevant `siris/<module>` tag and shows a bounded set of linked notes. Selecting a result opens that exact vault-relative note.

## Rationale

- Markdown remains the source of truth.
- Links are portable and visible in Obsidian itself.
- No AI inference is required to decide whether a note belongs to a module.
- No new database relationship table or indexing daemon is needed.
- Existing Knowledge authentication, traversal protection and read limits remain in force.
- The convention can later become one input to the Sprint 0.6 Context Graph without changing note identity.

## Consequences

Cross-module panels only show notes that have been explicitly tagged. This is intentional: semantic similarity may help users discover notes elsewhere, but it must not silently create durable module relationships.

Future contexts such as Tasks, Calendar and Briefings should reuse the same convention unless a stronger typed entity relationship exists. A dedicated `siris:` frontmatter schema may be added later if richer relationship metadata is required.
