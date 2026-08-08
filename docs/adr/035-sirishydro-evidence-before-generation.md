# ADR 035 — SirisHydro evidence before generation

## Status
Accepted

## Context
SirisHydro will eventually use Ollama to explain and synthesize engineering information. Engineering standards answers are high-value and must remain traceable to the user's private licensed source library rather than model memory.

## Decision
- SirisHydro retrieval produces a deterministic evidence packet before any generative model is invoked.
- Evidence packets retain source document identity, authority, reference, edition, page, relevance score and a bounded excerpt.
- The retrieval layer exposes an explicit sufficient/insufficient evidence state.
- When evidence is insufficient, SirisHydro must not invent a standards clause, requirement or design value.
- Future Ollama composition receives the evidence packet as context and may explain or organize it, but source-supported claims must remain tied to evidence citations.
- General engineering reasoning, when later enabled, must be visibly distinguishable from standards-backed statements.
- Tables, drawings, equations and layout-sensitive content may require inspection of the original licensed PDF even when extracted text is available.

## Consequences
The retrieval contract is independently testable and useful before Ollama integration. Model changes can improve explanation quality without changing the authority boundary. Semantic retrieval or embeddings may improve recall later, but must preserve deterministic source/page provenance.
