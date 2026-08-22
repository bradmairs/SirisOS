# ADR 103 — Siris Memory: Conversation Suggestions

## Status

Accepted.

## Context

ADR 100 deliberately scoped out "capture facts from SirisAI conversations into Siris Memory" as a separate, unscoped idea. Brad then asked for exactly that: when he chats with Siris and mentions something specific about himself or his homelab, he wants Siris to notice and offer to remember it -- not just the transcript (already persisted per ADR 100), but a standing personal-fact store Siris can draw on later, distinct from Knowledge documents and Project relationships.

Asked how saving should work, Brad chose **suggest, then confirm** over auto-save: extracted candidates are shown to him with explicit Save/Dismiss actions, never silently persisted.

This is a new risk category for this app's fail-open convention. Every other Ollama-touching feature here follows "a deterministic service computes real facts, Ollama only phrases them" -- there is no ground-truth tool result for a memory suggestion to check against, since the "fact" IS the extraction. What keeps this honest: the extraction is scoped to a single real message the user already saw on screen, with an explicit "only what was literally said, never inferred" instruction, and nothing is ever persisted from it without Brad tapping Save -- the same review step the pre-existing manual "add memory" dialog already requires for a human-authored memory.

## Decision

`SirisMemoryService.suggest(user_message, assistant_message)` (backend) calls the local Ollama model with a dedicated extraction prompt after each chat turn, capped at 3 suggestions, restricted to the `fact`/`preference`/`observation` memory classes (the other three -- `episode`/`decision`/`conversation` -- describe things that happened, which a single-message extraction can't reliably summarise; a person adding one by hand keeps that call). Suggestions are deduplicated case-insensitively against already-saved memory content before being returned. Any failure -- Ollama disabled, unreachable, or a malformed/unparseable response -- fails open to an empty list; a suggestion failure must never surface as a chat error.

On the client, `SirisAgentChatScreen` fires a suggestion fetch after each assistant reply and renders returned suggestions as small "Siris noticed: ..." chips under that reply, each with a Save (✓) and Dismiss (✕) action. Suggestions are kept in an in-memory `Map<int, List<SirisMemorySuggestion>>` keyed by turn index -- deliberately **not** part of the persisted chat history (ADR 100): a suggestion is only meaningful right after its exchange happened, and re-surfacing it after restoring a conversation days later (or even just navigating away from the chat screen and back) would be confusing, not helpful.

### Bug found in live testing: SirisAgent's own refusal silently killed extraction

Live-verifying against the real `llama3.2:3b` model (not just the fake-client unit tests) surfaced a real interaction bug between two existing features. SirisAgent's chat is scoped to data questions (ADR 091) and refuses anything else with a fixed message ("I can only answer questions about your own SirisOS training, health, homelab, knowledge and projects data."). A personal statement like "I'm a civil engineer and my homelab NAS is named vault" isn't a data question, so Siris correctly refuses it -- but the first version of the suggestion extraction fed the model *both* turns of the exchange, and the model treated Siris's refusal as proof nothing memory-worthy had been said. Direct, repeated testing against the real model confirmed this was 100% reproducible (5/5 empty results), not noise.

The first fix attempt -- rewording the extraction system prompt to explicitly say "ignore whether Siris's reply engaged with it, deflected, or refused," with a matching worked example -- did not help; re-tested at n=5 it was still 100% empty, the same failure the model had before. This is the same lesson ADR 098 already learned about this size of local model: stacking more instructions and examples onto a prompt doesn't reliably fix a small model's judgment failure, and can make things worse rather than better.

The fix that actually worked, tested at n=5 for both the refusal case (5/5 correct, up from 0/5) and a clean-reply baseline: **stop giving the model Siris's reply at all.** `suggest()` now builds its prompt from the athlete's message alone; `assistant_message` is still accepted as a parameter (the caller has it on hand from the chat turn) but is explicitly unused, documented inline as such. The system prompt was reworded from "one exchange between the athlete and Siris" to "one message an athlete sent to Siris" to match. There is no longer a refusal-vs-not distinction for the model to get confused by, because there is nothing about Siris's turn in its input at all.

### Bug found in live testing: a fixed-length list crashed Save and Dismiss

Separately, `SirisMemoryService.suggest()` on the mobile client built its returned list with `.toList(growable: false)`. Live-clicking Save or Dismiss on a real suggestion chip in the browser did nothing visible, and the browser console showed `UnsupportedError: remove` thrown from `_dismissSuggestion` / `_saveSuggestion`'s optimistic `.remove()` call on that fixed-length list -- caught by Flutter's gesture handler, so it failed silently in the UI with no visible error. Fixed by dropping `growable: false` so the returned list supports the mutation the UI already relied on. This shipped only because the initial verification pass tested that the suggestions rendered, not that Save/Dismiss worked -- a reminder that a feature with buttons needs the buttons live-clicked, not just the display state inspected.

## Verification

Backend: 342/342 tests passing (10 new `SirisMemoryService.suggest()` unit tests with fake chat clients covering disabled/error/malformed-JSON fail-open paths, class filtering, capping, and dedup; 2 new route tests for the `/suggest` endpoint).

Live, against the real `llama3.2:3b` model, after both fixes:
- Refusal-triggering personal statement -- 5/5 direct calls correctly extracted both facts (previously 0/5 and 0/9 across two prompt variants).
- Clean-reply baseline -- unaffected, still correctly extracting.
- A pure data question ("How strong am I?") -- 3/3 correctly extracted nothing.
- End-to-end in the browser: sent the refusal-triggering message, got three suggestion chips (one a redundant near-duplicate of another -- acceptable, since Brad reviews and can dismiss it); clicked Save on one and confirmed via a direct API call and the Memory tab UI that it persisted with the correct class and content; clicked Dismiss on another and confirmed it disappeared with no memory record created.

## Consequences

- Extraction quality depends entirely on a 3B local model's judgment with no ground-truth check -- occasional near-duplicate or missed suggestions (e.g. one clean-reply run out of several returned no suggestions) are expected and acceptable specifically because nothing is ever saved without Brad's explicit tap.
- `assistant_message` remains part of the public `/suggest` request contract and the mobile call site even though the service no longer uses it -- changing the API shape wasn't warranted by this fix, and the field costs nothing to keep accepted (documented inline as intentionally unused).
- This is the second time in this project that a small local model's unreliability was fixed by changing what data it's given rather than by further prompt tuning (the first was ADR 098's `search_knowledge` redesign) -- worth treating as the default first response to this failure mode rather than another round of prompt wording.
- Suggestions are intentionally ephemeral (in-memory, per turn index, cleared on navigation away from the chat screen or on "clear conversation") -- if that turns out to be too easy to lose in practice, revisit as a separate follow-up rather than expanding this ADR's scope.
