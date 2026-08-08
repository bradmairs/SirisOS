# ADR 038 — Local hybrid semantic standards retrieval

## Status
Accepted

## Context
The private Engineering Standards Library needs better recall when a user's wording differs from the wording used in a standard. SirisHydro must improve retrieval without weakening exact document/reference/edition/page provenance, introducing a cloud dependency, or making Ollama mandatory for evidence retrieval.

## Decision
SirisOS uses a local hybrid reranker for the first semantic-retrieval slice.

- Exact phrase and exact query-term matches remain the strongest signals.
- A small deterministic civil/water concept map expands common equivalent terminology such as grade/slope/gradient, buoyancy/flotation/uplift, pit/manhole/chamber, and detention/storage/basin.
- Semantic expansion contributes a bounded secondary score and cannot override strong exact wording merely because a related term appears frequently.
- Ranking remains deterministic and page-based; every selected result still resolves to the immutable local document ID and exact page.
- SirisHydro uses only active document revisions for new evidence packets. Archived and superseded revisions remain directly retrievable for historical citation review.
- The evidence response exposes the retrieval strategy so later model-assisted or vector retrieval can be distinguished from this deterministic layer.
- No cloud embedding service is introduced. Ollama/vector embeddings may be added later as an optional recall stage, but deterministic provenance and lexical fallback remain mandatory.

## Consequences
This improves civil/water terminology recall immediately with negligible runtime/deployment cost. It is intentionally narrower than general-purpose embeddings, but it is explainable, offline, regression-testable and safe as the foundation for later semantic/vector retrieval.
