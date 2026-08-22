# ADR 100 — SirisAgent: Chat Persistence

## Status

Accepted.

## Context

SirisAgent's chat conversation has always lived entirely client-side, stateless per call on the backend (ADR 091) -- but "client-side" meant a plain `State` field, lost the moment the screen was navigated away from or the app restarted. Closing this was the other half of the "conversation memory" option offered alongside Knowledge/Projects tools; Brad chose Knowledge/Projects first, then asked to continue SirisAI development, and this was the natural next piece already scoped in that earlier conversation.

This is deliberately scoped to *persistence* only -- restoring the same transcript across restarts -- not the separate, much larger "capture facts from conversations into Siris Memory" idea the roadmap already flags as an open, unscoped question distinct from chat history itself.

## Decision

`_ChatTurn` gained `toJson()`/`fromJson()` and the chat screen now saves the turn list to `SharedPreferences` after every message (both the user's message and the assistant's reply, so a mid-conversation app kill loses at most the in-flight request) and restores it in `initState()`. A corrupted or unparseable stored payload fails open into a fresh empty conversation rather than blocking the screen from opening, matching the fail-open convention used everywhere else in this app.

Two independent caps, for two different reasons:
- **Storage is capped at 200 turns** -- a chat transcript isn't meant to grow forever, and `SharedPreferences` isn't meant to hold an unbounded blob.
- **Only the most recent 20 turns are sent as conversation context on each request**, independent of how much history is on-screen or in storage. Without this, a persisted conversation revisited after weeks would silently send its entire history as context on every subsequent message, growing token cost and latency indefinitely -- a problem that couldn't previously exist, since in-memory-only state reset on every restart naturally bounded it.

A "clear conversation" action (a small icon next to the Ollama status chip, shown only once there's a conversation to clear) resets both the in-memory list and the stored payload, since a chat that persists forever with no way to start over would be worse than the previous restart-clears-it behaviour for anyone who wants a clean slate.

Live-verified in the browser: sent a real message, reloaded the page, confirmed the exact same conversation reappeared; cleared it, reloaded again, confirmed it stayed empty and the clear icon correctly disappeared.

## Consequences

- No backend change at all -- this is purely a client-side addition, consistent with SirisAgent's stateless-backend architecture.
- The two caps (200 stored / 20 sent as context) are independent judgment calls, not measured against real usage yet -- worth revisiting if a very long-lived conversation's context window turns out to feel too short or too expensive in practice.
- "Capture facts from SirisAI conversations into Siris Memory" remains a separate, unscoped idea -- this ADR only makes the conversation itself durable, not what Siris permanently remembers from it.
