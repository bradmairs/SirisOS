# ADR 097 — Recommendation Ollama Synthesis v1

## Status

Accepted.

## Context

The roadmap's "Broader intelligence / automation" section named this directly: "Ollama's role is explaining a recommendation in natural language, not inventing it." The pattern this calls for already has two proven instances in the codebase — SirisHydro answer synthesis (ADR 057) and the Coach weekly report headline (ADR 090): a deterministic fact is always computed and always returned; Ollama's only job is an optional rephrase on top, with a fail-open contract (`synthesized_*` stays `null` whenever Ollama is unconfigured, unreachable, or returns nothing usable). This is that same pattern's third application, not a new one.

## Decision

`Recommendation` gains `synthesized_rationale: str | None = None`. In `_reconcile()`, a synthesis call (`chat_client.complete()` with a new `RECOMMENDATION_SYSTEM_PROMPT` — same "rephrase only, do not add facts" shape as the Ask Siris and Coach prompts) is made only when a recommendation is first detected as new, not on every subsequent poll for the same still-open recommendation. `GET /api/v1/recommendations` reconciles fresh alert state against the persisted store on every call (ADR 064), so without this guard a chatty Operations Center screen polling every few seconds would re-call Ollama for the same unchanged recommendation indefinitely — wasteful against a real model, and unlike Coach's single per-request call or SirisHydro's per-question call, this endpoint's own existing polling behavior made that a real risk worth designing around up front rather than discovering live. The persisted `synthesized_rationale` is carried over unchanged on every later reconcile for an existing recommendation, including across a dismiss/act status change.

Flutter: `RecommendationRecord.displayRationale` (`synthesizedRationale ?? rationale`) replaces the raw `item.rationale` read in the Operations Center panel — same additive-not-replacement contract as Coach's `synthesizedHeadline ?? headline` (ADR 090), reusing the exact getter-based fallback shape rather than inventing a new one.

## Consequences

- Zero fabrication risk: Ollama only ever receives the already-correct deterministic title/rationale/suggested-action as its entire prompt, with an explicit "do not add causes, container names, values or claims that are not already there" instruction — the same constraint every prior instance of this pattern has run under with no incident.
- This dev environment has no Ollama server configured, so the synthesis path itself could only be verified with a fake `chat_client` in tests (5 new tests: synthesis on first detection, fallback when unconfigured, fallback when nothing usable returned, no repeated calls on later polls, survives a dismiss). The fail-open path (`synthesized_rationale: null`, deterministic rationale shown) was verified live in the running app, matching how ADR 090 was itself verified.
- The "only synthesize once, at first detection" rule is specific to this endpoint's poll-and-reconcile shape and isn't a general rule for the pattern — Coach and SirisHydro don't need it because they're called once per explicit user action, not polled.
- Backend: 300 tests pass (5 new). Flutter: unchanged test count, `flutter analyze` clean.
