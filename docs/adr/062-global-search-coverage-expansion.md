# ADR 062 — Global search coverage expansion

## Status

Accepted.

## Context

`GET /api/v1/search` (ADR 042) was built during the Knowledge Platform sprint and has covered Docker containers, running history, gym workouts, Knowledge notes and recent activity ever since. Every module added afterward — Projects, saved Engineering calculations, the Standards library, and now Siris Memory — was never added to it. A user searching SirisOS globally could not find a Project, a saved calculation, an uploaded standard, or a remembered fact/decision, even though each of those has its own reasonably capable in-module search or list view. This is exactly the kind of coverage gap that undermines "Search SirisOS" living up to its name, and it would only have grown with every future module.

## Decision

Extend the existing aggregator with the same lightweight, in-process substring-match pattern already used for Docker/running/gym (no new search infrastructure, no new dependency): call each module's own private `_load()`/metadata-glob functions directly (matching the cross-module private-helper convention already established, e.g. `engineering_calculations.py` importing `engineering_standards._load_metadata`), filter in-process, and map into the existing generic `SearchResult` shape.

Each new source is wrapped so a corrupted store degrades that source to zero results rather than failing the whole `/search` call — `projects._load()`, `engineering_calculations._load()` and `siris_memory._load()` all raise on a malformed JSON store, and search aggregates five-plus independent sources in one request; one bad file must not make search for everything else disappear too. This mirrors the fail-open principle already used for Ollama (ADR 057) and SirisHydro history recording (ADR 059), applied here at the "one source among many" level rather than "one optional feature."

Results continue to navigate to the owning module (`target`), not a specific object within it — the same coarse-grained navigation every existing search result already uses. Deep-linking to the exact object (the roadmap's `siris://` scheme, Sprint 0.6) is separate, later work.

## Consequences

- Every substantial SirisOS record type is now discoverable from one search box, not just the ones that existed when `/search` was first built.
- Future modules that follow the same `_load()`-returns-a-list convention are cheap to add to search — a few lines, no new pattern to invent.
- Search's reliability no longer regresses as new record-store modules are added; a corrupted `siris-memory.json` (for example) reduces search to "everything except memory," not "search is broken."
- No change to the existing search UI's navigation model — the Universal Command Palette (Sprint 0.7, not yet built) can reuse this same endpoint and coverage rather than needing its own.
