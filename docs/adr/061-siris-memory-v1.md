# ADR 061 — Siris Memory v1

## Status

Accepted.

## Context

SirisOS's information surfaces are all either documents (Knowledge) or structured relationships between objects (Projects, Engineering Standards, saved calculations, SirisHydro history). None of them are Siris's own accumulated understanding — the facts, preferences, decisions and observations that would let it eventually answer "why did I decide to use Class 3 pipe on that project?" rather than only "what does this document say?". A development brainstorm this project incorporated into the roadmap named this gap explicitly and proposed a Memory Service with distinct classes (Facts, Preferences, Episodes, Decisions, Observations, Conversation memories) as the foundational piece several other planned features (Recommendation Engine, Siris Inbox, richer Briefing) would eventually draw on.

The full vision — cross-object traversal (Project → calculation → standard → SirisHydro question → decision), automatic capture from SirisAI conversations, confidence scoring — has no natural v1 slice on its own: there is no SirisAI conversation surface yet to auto-populate Conversation memories from, and cross-object traversal needs the Project Context Graph's relationship model extended in ways that deserve their own design pass rather than being bolted on here.

## Decision

Ship the smallest useful slice: a generic `MemoryRecord` (memory class, free-text content, optional free-text source, timestamp) with an atomic JSON store — identical persistence pattern to every other record type in SirisOS (ADR 049, 055, 059) — and CRUD API (`GET/POST /api/v1/siris/memory`, `DELETE .../{id}`, list filterable by class). No object-reference linking yet; `source` is a free-text hint ("Project: Sydney Water rising main"), not a typed relationship, so this doesn't presuppose or foreclose the eventual Knowledge Graph-based traversal design.

The existing `'siris'` module — previously a `preview`-only placeholder reading "The Siris AI command centre is planned for a later sprint" — now builds this screen directly rather than gaining a new module slot, since the module's own description ("AI context, recommendations and personal knowledge tools") already named exactly this. It intentionally does not claim to be the full command centre yet; Memory is its first real content, not its final shape.

## Consequences

- SirisOS has a place to manually record the kind of decision/preference/fact that would otherwise live only in the user's head or scattered Knowledge notes — usable immediately, without waiting for automatic capture or traversal to exist.
- The 6 memory classes are enforced at the API layer (a `Literal` type) so future consumers (a Recommendation Engine, a richer Briefing) can rely on the class vocabulary being stable, even before those consumers exist.
- Cross-object traversal, confidence scoring, and automatic capture from SirisAI conversations remain explicitly out of scope and unchecked on the roadmap — this ADR covers only the foundational record store and manual-entry UI.
- `/app/data/siris-memory.json` is automatically covered by the generic `/app/data` volume mount (ADR 060) — no additional deployment wiring was needed.
