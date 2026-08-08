# ADR 042 — Knowledge global search and Mission Control integration

## Status
Accepted

## Decision

Knowledge participates in SirisOS global search through the existing authenticated search contract. Matching Markdown notes are returned with `module=knowledge`, `target=knowledge`, and the vault-relative note path as `reference_id` so the client can open the exact local note without inventing a second identity scheme.

The Mission Control Knowledge widget is registered through the shared widget registry. It reads only the bounded Knowledge overview endpoint and starts its request from widget lifecycle state (`initState` / explicit refresh), never from `build()`.

## Search ranking

Knowledge search contributions remain deterministic and local. Exact title matches outrank partial title/path/tag/body matches. This slice does not introduce embeddings or model-generated ranking.

## Safety and ownership

The vault remains read-only. Markdown remains the source of truth. Global search never edits notes, and opening a result uses the exact vault-relative path returned by the backend.

## Consequences

Knowledge is now visible outside its standalone module and can participate in the core SirisOS discovery and Mission Control surfaces. Future semantic search can improve recall behind the same result identity and provenance contract without changing how exact notes are opened.
