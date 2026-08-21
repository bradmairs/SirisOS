# ADR 092 — SirisAgent: Real Ollama Verification and Prompt Hardening

## Status

Accepted.

## Context

ADR 091 shipped the tool-calling agent honestly flagging one real gap: no Ollama server existed in this dev environment, so the tool-selection loop had only ever been exercised against a scripted fake client, never a real model. Brad asked to close that gap directly rather than keep building on an unverified foundation.

This Mac had no Homebrew and only 7.6GB of free disk. Confirmed with Brad before downloading anything: install Ollama's official macOS app directly (no package manager needed -- the app bundle already contains the CLI binary at `Ollama.app/Contents/Resources/ollama`, runnable headless via `ollama serve` with no GUI/menu-bar interaction required), and pull the smallest model with reliable tool-calling support, `llama3.2:3b` (2.0 GB), rather than a larger model that would have left almost no disk headroom.

## Decision

**The plumbing is confirmed correct.** A raw `curl` against the real server's `/api/chat` with a `tools` payload returned `message.tool_calls` in exactly the shape `OllamaChatClient._chat_with_tools()` already parsed (`[{id, function: {name, arguments}}]`) -- no code changes needed there. Feeding a real tool result back as a `{"role": "tool", ...}` message produced a coherent final answer built only from the numbers actually supplied. Through the full stack (`SirisAgentService` → real `GymService`/`TrainingLoadService`/etc. seeded with this session's own data → real Ollama), `"How strong am I right now?"` correctly called `get_strength_score` and answered with the exact seeded values (0.937 overall, 1.0 legs, 0.874 chest) -- verified against a direct API call, not eyeballed.

**Live testing against the real model surfaced two genuine model-reliability gaps**, not plumbing bugs: asked a question no tool could answer ("What is the capital of France?"), the model called an irrelevant tool anyway and then answered from its own training data despite an explicit "say so honestly, never guess" instruction. Asked a two-part question (weekly summary *and* training level), it called only one of the two needed tools and blended that tool's `combined_index` into a claim about "training level" -- a different metric it never actually fetched.

**The system prompt was hardened** (confirmed with Brad as the mitigation to try, rather than immediately reaching for a larger model): an explicit in-scope/out-of-scope boundary with a fixed refusal sentence for anything no tool can answer, a rule against blending one tool's numbers into a different metric's claim, and a rule against discarding a tool's real result in favor of the refusal sentence once a tool has actually been called. Re-testing the same questions against the same real model: the out-of-scope refusal now works correctly with zero tool calls, and the multi-part question now correctly calls both tools with a properly separated answer.

**One narrowed, documented limitation remains.** Asked whether today is a good day to run, the model correctly calls `get_training_conflict_today`, gets back a real "insufficient recovery data synced yet" result, and then discards it in favor of the fixed refusal sentence -- conflating "this tool's honest answer is 'not enough data'" with "no tool could answer this at all." One additional prompt rule aimed at this exact confusion did not resolve it. This is accepted and documented rather than chased further: distinguishing "in scope but the data itself is insufficient" from "out of scope entirely" is a genuinely subtle instruction for a 3B model to hold reliably, and further prompt-only iteration against a single small model, with no eval set, has diminishing returns. A larger model would plausibly do better -- not tested, since pulling one (~4.7GB) would leave this Mac's disk close to full.

## Consequences

- The core claim ADR 091 could only assert in theory -- that grounding actually works, not just that the code compiles against a mock -- is now demonstrated against a real model, with real seeded data, multiple times.
- `REFUSAL_MESSAGE` is a named constant with a fixed sentence the model is told to reproduce verbatim, rather than paraphrase -- this makes the refusal case reliably detectable (by a UI, or a future eval) as a distinct outcome, not just prose that happens to sound like a refusal.
- The known remaining gap (a real tool's own "insufficient data" answer sometimes getting overridden by the refusal sentence) is a real, live, observed failure mode -- not a hypothetical -- and is recorded here specifically so a future attempt to fix it doesn't have to rediscover it by hand.
- Local Ollama now runs on this Mac (`llama3.2:3b`, ~2GB, 5.0GB free remaining) for any future verification work in this environment -- not committed to the repo or required for CI, purely a local dev convenience matching how `OLLAMA_URL` has always been optional/fail-open everywhere else in this app.
- No code changes to `OllamaChatClient` were needed -- only `SirisAgentService`'s system prompt. Backend: 258 tests pass, unchanged (the prompt text itself isn't asserted verbatim in tests, only the fail-open/dispatch/loop behavior around it, which stayed correct throughout).
