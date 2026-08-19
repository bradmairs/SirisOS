# ADR 090 — Coach Weekly Report Ollama Synthesis v1

## Status

Accepted.

## Context

ADR 070 (Weekly Coach Report v1) explicitly deferred Ollama narrative synthesis on top of the deterministic headline, as a confirmed scope decision to ship the deterministic core first -- the same sequencing Progressive Overload and Personal Records used. Ask Siris (ADR 071) and "Can I Train Today?" (ADR 081) both later established the pattern this was waiting for: a deterministic answer is always computed and always returned, and Ollama gets one narrow job -- rephrase it more naturally -- with a fail-open contract (`synthesized_answer` stays `null` whenever Ollama is unconfigured, unreachable, or returns nothing usable). Brad asked to keep building out SirisAI/Ollama integration; this is that pattern's most directly-named unbuilt application still on the roadmap.

## Decision

`GET /coach/weekly-report` now calls `chat_client.complete()` with the report's own deterministic `headline` string as the only input, using a new `WEEKLY_REPORT_SYSTEM_PROMPT` (same shape as Ask Siris's system prompt: rephrase only, never add facts). The result is returned as `synthesized_headline: str | None` -- additive to the response, alongside the untouched deterministic `headline`, not a replacement. `CoachService.weekly_report()` itself is unchanged and stays a pure deterministic function; the Ollama call lives in the route handler only, matching where `/ask`'s own synthesis call already lives, so `CoachService` has no LLM dependency to reason about or test around.

Flutter: `_HeadlineCard` shows `synthesizedHeadline ?? headline` -- the synthesized text when present, the deterministic sentence otherwise, no visual distinction between the two states beyond the wording itself (matching Ask Siris's own container-vs-plain-text treatment being an intentional exception, not a pattern to duplicate everywhere).

## Consequences

- Zero fabrication risk: Ollama only ever receives the already-correct deterministic headline as its entire prompt, with an explicit "do not add numbers, dates, exercises or claims that are not already there" instruction -- the same constraint Ask Siris's synthesis has run under since ADR 071 with no incident.
- This dev environment has no Ollama server configured, so the synthesized path itself could only be verified with a fake `chat_client` in tests (`_FakeChatClient`, three scenarios: available, returns nothing, unconfigured) -- not against a real model's actual output. The fail-open path (`synthesized_headline: null`, deterministic headline shown) was verified live in the running app.
- Backend: 244 tests pass (4 new). Flutter: 58 tests pass, unchanged.
- The other named gaps in the roadmap's "Ollama / local inference" section -- shared model routing, per-module model/profile selection -- remain unbuilt; this slice extends the *reach* of the existing single-model synthesis pattern to one more surface, not the underlying routing infrastructure.
