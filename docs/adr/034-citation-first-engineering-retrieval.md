# ADR 034 — Citation-first engineering retrieval

## Status
Accepted

## Context
SirisOS now stores and indexes private licensed engineering standards. Future SirisHydro answers need a stable retrieval contract that preserves document identity and page provenance before any LLM is introduced.

## Decision
- Add an authenticated page-text endpoint for indexed standards.
- Every retrieved page carries a deterministic citation built from reference/title, edition, authority and page number.
- The Engineering Standards UI can open the exact extracted source page and copy its citation.
- Extracted text is retrieval material, not a replacement for the licensed PDF. Users are reminded to inspect the PDF when layout, figures or tables matter.
- Future SirisHydro/Ollama integration must consume these citation-bearing retrieval objects and keep the local standard as the source of truth.
- The model may summarize or explain retrieved material, but must not invent a standards citation or silently substitute model knowledge for unavailable source text.

## Consequences
This establishes a deterministic evidence layer before semantic search or generative answering. OCR, chunk ranking and embeddings can be added later without changing the provenance boundary.
