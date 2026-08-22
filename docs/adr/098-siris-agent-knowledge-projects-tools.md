# ADR 098 — SirisAgent: Knowledge and Projects Tools

## Status

Accepted.

## Context

Every prior SirisAgent tool slice (Training, Health, Homelab, Readiness) has carried the same caveat: "Knowledge and Projects remain unscoped since neither has a clean service-layer object to wrap the same way (their logic lives directly in API route handlers)." Brad chose closing that gap as the next priority for SirisAI, over conversation persistence or re-verifying existing tools against his now-working production Ollama.

Both `app/api/knowledge.py` and `app/api/projects.py` had their real logic as module-level functions and route handlers directly, not classes -- functional, well-tested, but not reusable from anywhere except a FastAPI route.

## Decision

**`KnowledgeService`** (new) wraps read-only note access: `search()` (the existing search-and-rank logic) and `read_note()` (safe path resolution + content, folded into one call). The richer navigation features -- browse, backlinks, related notes, the graph view -- stayed in `app/api/knowledge.py`, which now imports the note-scanning primitives from the service instead of keeping its own copies. `/search` and `/note` delegate to the service outright.

**`ProjectService`** (new) is a full extraction -- list, get, create, update, current-project get/set -- since the whole module was small enough that a partial extraction would mean two JSON-file-access code paths. `app/api/projects.py` now delegates every route to it.

**Both extractions hit the exact class of bug ADR 094 already found and fixed for `HomelabAlertService`**, reintroduced here because the fix wasn't yet a habit: a first pass constructed the services once at module-import time, breaking `test_knowledge.py`, `test_global_search_knowledge.py` and `test_project_relationships.py`, which monkeypatch module-level constants (`knowledge.VAULT_ROOT`, `projects.PROJECTS_PATH`) expecting the route module's own functions to read the *current* value on every call. Fixed by constructing each service fresh per request, and by keeping thin proxy functions for the several other modules (`knowledge_context.py`, `knowledge_global_search.py`, `project_relationships.py`, `search.py`) that reached into these private functions directly -- discovered only by running their tests, not by reading the diff.

**Live verification against a real local model surfaced three genuine, separate bugs -- not one -- and changed the tool design itself, not just the prompt.** With `search_knowledge` and `read_knowledge_note` added as two tools (mirroring how a person uses a vault: search, then open a hit), asking "what does my drainage note say about pipe grade" against real seeded data:

1. **Malformed tool-call arguments.** The model called `read_knowledge_note` with `{"path": "search_knowledge", "query": "..."}` -- merging both tools' parameters into one call and passing the other tool's own name as the path. `_read_knowledge_note` now falls back to treating an unresolved path as a search query and reading the top hit, rather than erroring on a call that was clearly trying to find real content.
2. **A real search algorithm gap, unrelated to the model.** The model's natural query ("drainage design pipe grade") never appears as one exact contiguous phrase in a note that separately says "Drainage Design" and "pipe grade" -- `KnowledgeService.search()`'s substring-only matching returned zero hits for it, confirmed directly against the service, independent of any model. This would affect a person typing the same multi-word phrase into the actual Knowledge search UI, not just SirisAgent. Fixed with word-level scoring alongside the existing exact-phrase scoring, so a genuine phrase match still ranks first but a same-word multi-keyword query also finds real matches.
3. **Unreliable multi-step tool chaining.** Even with the merge bug and the search gap both fixed, the model would frequently call only `search_knowledge`, then either fabricate specific technical content from the title alone (observed inventing pipe-grade slope figures that appear nowhere in the real note) or refuse outright, rather than reliably following up with `read_knowledge_note`. Three rounds of prompt hardening (an explicit rule, reordering the anti-discard rule earlier, an emphatic anti-fabrication rewrite) did not fix this reliably -- confirmed by re-testing 3-4 times after each change, matching ADR 092's own verification standard. This is a real capability limit of a small (3B) local model at multi-step tool sequencing, not a prompt-wording problem.

Rather than keep tuning wording against that limit, `search_knowledge` was redesigned to not depend on it: it now includes the best-matching note's real content directly, in `top_result_content`, alongside the title/tag hit list. `read_knowledge_note` still exists for reading a hit other than the top one. This guarantees the common case is grounded in a single call regardless of whether the model chains correctly -- re-tested 4/4 after the change, all four answers correctly citing "AS 3725" and "1 in 5 years" from the real note text, none fabricated.

The refusal-scope text (`REFUSAL_MESSAGE` and the system prompt's own description of what Siris covers) had also never been updated across three prior ADRs (091, 093, 095) to mention Homelab, Knowledge or Projects -- still read "training, health and homelab" verbatim, caught and fixed here alongside the equivalent stale copy in the Flutter chat screen.

## Consequences

- Backend: 315 tests pass (was 285 after the Ollama model-tag fix) -- covering `KnowledgeService`, `ProjectService`, the new SirisAgent tools, the multi-word search fix, and the malformed-argument recovery.
- SirisAgent's tool count goes from 13 to 17. No domain remains explicitly unscoped in the tool-comment history anymore.
- The multi-word search fix is a genuine improvement to the Knowledge search feature itself, not just a SirisAgent workaround -- found only because a model's natural phrasing exercised a real gap a human typing short keywords rarely would.
- The module-level-singleton-vs-fresh-per-call mistake has now happened twice (ADR 094, and again here before being caught) -- worth checking explicitly first on the next service extraction from a monkeypatch-tested route handler, not last.
- "Don't rely on prompt engineering to guarantee reliability a small model can't provide -- change what the tool returns instead" is the concrete lesson worth carrying into any future multi-step SirisAgent tool: this is the first slice where the fix was an architecture change rather than more prompt iteration, and it's the one that actually worked.
