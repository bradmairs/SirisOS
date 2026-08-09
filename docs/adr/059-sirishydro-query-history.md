# ADR 059 — SirisHydro query history

## Status

Accepted.

## Context

SirisHydro (ADRs 033–035, 038, 057) has been a stateless request/response tool: each question is answered from the evidence available at that moment and then forgotten. The longer-term direction for SirisAI is to treat SirisHydro as an agent that builds memory over time, not a one-shot lookup. A persistent record of what was asked, what evidence was found, and what (if anything) was synthesized is the smallest useful step toward that — it doesn't require any conversational/multi-turn design work, but it does give SirisHydro a first, real notion of its own history.

## Decision

Every call to `GET /api/v1/engineering/sirishydro/evidence` now appends a `SirisHydroHistoryRecord` (question, whether evidence was sufficient, the evidence citations, the synthesized answer if any, and a timestamp) to an atomic JSON store, the same persistence pattern used for saved calculations (ADR 055) and every other SirisOS record store. Only the citation strings are kept, not full excerpts — the standards library remains the source of truth for that text, so history stays a lightweight index rather than a second copy of retrieved content.

History recording is best-effort and cannot fail the request it's attached to: `_record_history` swallows both the `HTTPException` `_save_history` raises for expected I/O failures and any raw `OSError` that could otherwise propagate uncaught (matching the same principle ADR 057 established for synthesis — a secondary concern must never break the primary one). `GET .../history` lists records newest-first (bounded to the last 200), and `DELETE .../history/{id}` removes one.

The Flutter SirisHydro screen exposes this as a "Past questions" sheet reachable from a history icon next to the screen title, listing each question with its outcome and answer preview; tapping a record re-asks the same question, and each has a delete action.

While implementing this, live-testing in the browser surfaced that the FastAPI CORS middleware's `allow_methods` only listed `GET` and `POST` — every `DELETE`/`PATCH`/`PUT` endpoint already shipped (calculation delete, project update/delete, and now history delete) has been silently broken from a browser since it was added, because preflight `OPTIONS` requests were rejected before the real request was ever sent. `curl`/`pytest` calls don't perform CORS preflight, so nothing in the existing test suite could have caught this. Fixed by adding the missing methods, with a regression test asserting `allow_methods` covers every HTTP method the API actually declares.

## Consequences

- SirisHydro now has a real, inspectable history — the first concrete piece of the "SirisHydro as agent with memory" direction, without committing to any conversational/context-window design yet.
- History is intentionally not evidence for future answers: nothing in `assemble_evidence` or synthesis reads from history. Whether/how past queries should inform future ones is a separate, larger design decision for later in Sprint 0.7.
- The CORS fix is unrelated in cause but was blocking in practice; every existing DELETE/PATCH/PUT endpoint now actually works from the browser, not just from tests.
