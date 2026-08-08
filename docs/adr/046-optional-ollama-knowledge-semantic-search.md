# ADR 046 — Optional Ollama semantic search for Knowledge

## Status
Accepted

## Context
SirisOS Knowledge already provides deterministic local search over note titles, paths, tags and Markdown content. Broader recall is useful when a query and a relevant note use different wording, but Knowledge must remain usable when local AI is unavailable or unconfigured.

## Decision
Add an optional semantic reranking layer backed by Ollama's local embeddings API.

- Semantic search is enabled only when both `OLLAMA_URL` and `SIRISOS_KNOWLEDGE_EMBEDDING_MODEL` are configured.
- Deterministic lexical search continues to scan the full bounded vault and remains the fallback.
- Exact title/path/tag/content matches retain substantially higher lexical weights, so semantic similarity supplements rather than replaces explicit matches.
- Semantic-only matches may enter global SirisOS search when their embedding similarity is positive.
- Note embeddings are cached in memory using vault path, modification time and size as the cache identity. Editing a note naturally invalidates its cached vector.
- Semantic work is bounded by `SIRISOS_KNOWLEDGE_SEMANTIC_MAX_NOTES`; recent notes are preferred when the vault exceeds that bound.
- Ollama failures, timeouts, missing models or malformed embedding responses fail open to lexical search.
- No cloud embedding provider or external vector database is introduced.

## Consequences
The Knowledge Platform gains broader local recall while preserving offline deterministic behavior and Markdown as the source of truth. The first query after a restart may be slower while document embeddings are populated. A persistent/vector index can be introduced later if vault scale warrants it, without changing the lexical fallback contract.
