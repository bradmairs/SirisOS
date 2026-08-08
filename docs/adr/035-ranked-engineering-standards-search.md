# ADR 035 — Ranked engineering standards search

## Status
Accepted

## Decision
Engineering standards keyword retrieval uses a deterministic local ranking layer before semantic search is introduced.

- Exact phrase occurrences receive the strongest score.
- Individual normalized query terms add bounded supporting score.
- Up to several page hits can be returned from one document rather than stopping at the first match.
- Every page hit retains document metadata, page number, score, snippet and deterministic citation.
- Results remain local and explainable; no LLM is involved in ranking.

## Rationale
This materially improves recall for engineering phrases such as `minimum cover` while keeping retrieval transparent and citation-safe. Optional embeddings can later augment recall without replacing deterministic provenance.
