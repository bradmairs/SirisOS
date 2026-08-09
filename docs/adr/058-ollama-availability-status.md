# ADR 058 — Ollama availability status

## Status

Accepted.

## Context

ADR 057's chat connector is deliberately fail-open: if `OLLAMA_URL` is unset, the configured model isn't installed on the server, or the server is unreachable, SirisHydro silently falls back to its evidence-only behaviour. That's the right default — a broken model connection must never break evidence retrieval — but it leaves the user with no way to tell *why* a synthesized answer isn't appearing. A misconfigured `SIRISOS_OLLAMA_CHAT_MODEL` (e.g. a typo, or a model that was never pulled) looks identical, from the UI, to Ollama not being configured at all.

## Decision

`OllamaChatClient` gains a `status()` method that queries Ollama's `/api/tags` endpoint (the list of models actually present on the server) and reports four states: not configured, configured but unreachable, reachable but the configured model isn't installed, or fully working. This is exposed at `GET /api/v1/intelligence/ollama-status` — the existing `intelligence` module, which already aggregates cross-module AI-adjacent surfaces (recommendations), rather than a SirisHydro-specific endpoint, since availability is a property of the shared connector (ADR 057), not of any one caller.

The Flutter SirisHydro screen fetches this once per visit and renders a compact status chip: what's missing (not configured / unreachable / model not found) or, when healthy, which model is answering. This is purely informational — the chip never blocks or delays evidence retrieval, and evidence-only behaviour is unaffected by its result.

## Consequences

- The same silent-fallback design from ADR 057 is preserved; this only adds visibility into *why* it fell back, not a new failure mode.
- `status()` reuses the connector's existing `enabled`/timeout/error-handling conventions rather than introducing a second configuration surface.
- Placing this under `/intelligence` rather than `/sirishydro` means future Ollama consumers (briefings, semantic search, SirisPM) can reuse the same status check without it looking SirisHydro-specific.
- Model-name matching tolerates the common `name:tag` form Ollama's `/api/tags` returns (e.g. configuring `llama3.1` matches a server-reported `llama3.1:latest`).
