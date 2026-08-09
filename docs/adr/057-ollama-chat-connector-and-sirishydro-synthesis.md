# ADR 057 — Ollama chat connector and SirisHydro answer synthesis

## Status

Accepted.

## Context

Sprint 0.6 closed with SirisHydro as a pure retrieval tool: it ranks and returns evidence excerpts from the private Standards library, but never generates prose — the human still has to read the excerpts and form an answer. Sprint 0.7 opens with the architecture direction already agreed for SirisAI: connect directly to an Ollama server the user runs on their own homelab, rather than routing through Open WebUI or another intermediary, so the model connection stays simple and under SirisOS's own control. `knowledge_semantic_search.py` (ADR 046) already established the pattern for talking to Ollama optionally and failing open — an `OLLAMA_URL` embeddings client used to rank Knowledge notes — but nothing in SirisOS yet calls Ollama for actual chat/completion.

SirisHydro's evidence assembly already builds a fully-grounded prompt: `_context_text()` produces a numbered evidence block plus an explicit "answering rule" instructing that claims must cite the evidence and that unsupported questions should be admitted rather than answered from invented knowledge. That text was written for a human reader, but it is already exactly the shape of prompt a model needs to answer safely.

## Decision

SirisOS gains a small, general-purpose `OllamaChatClient` (`app/services/ollama_service.py`) configured via `OLLAMA_URL` and `SIRISOS_OLLAMA_CHAT_MODEL`, calling Ollama's `/api/chat` endpoint. It is fail-open by construction: disabled configuration, network errors, and malformed responses all resolve to `None` rather than raising, so no caller's existing behaviour can be broken by an unreachable or unconfigured Ollama server. This mirrors the embeddings client's fail-open contract exactly, so both connectors reason about "Ollama is optional infrastructure" the same way.

SirisHydro's `/evidence` endpoint is the connector's first caller: when evidence is sufficient, the existing `_context_text()` grounding block is sent to the chat client under a system prompt that repeats the same non-invention rule, and the result is returned as an additional `synthesized_answer` field. When evidence is insufficient, or Ollama is not configured, or the call fails, `synthesized_answer` is `None` and the response is otherwise unchanged — the evidence-only experience Sprint 0.6 shipped remains the fallback, not a special case.

## Consequences

- SirisHydro can now produce a direct, cited answer instead of only excerpts, without introducing a second retrieval or grounding mechanism — synthesis reuses the same evidence and non-invention rule the UI's "Copy context" already exposed.
- The chat connector is deliberately generic (system + prompt in, text out) so it can be reused by other Sprint 0.7 consumers — SirisPM, briefings, semantic search — without SirisHydro-specific assumptions baked into it.
- No new failure mode is introduced for users without Ollama configured: the connector's `enabled` check and fail-open error handling mean an absent or unreachable Ollama server is indistinguishable, from the caller's perspective, from choosing not to use one.
- This is model routing for a single feature, not the shared model routing/profile system Sprint 0.7 anticipates — that remains a follow-on once a second consumer exists to design the shared contract against.
