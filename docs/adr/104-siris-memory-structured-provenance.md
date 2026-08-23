# ADR 104 — Siris Memory: Structured Provenance

## Status

Accepted.

## Context

Siris Memory's `source` field (ADR 061) was a plain free-text string from day one -- both the manual "Remember" dialog and, later, the chat-suggestion save path (ADR 103) just wrote a caller-supplied sentence with nothing behind it. The roadmap flagged this as a gap since ADR 061: "Structured (not free-text) provenance per memory record — typed source object reference, confidence — matching the citation standard already set by SirisHydro and Context." A free-text source can't be resolved, can't be validated, and can't stay current if the thing it names changes.

The established precedent for this already exists in the codebase: `project_relationships.py`'s `ProjectRelationshipRecord` uses a typed `target_type: Literal[...]` + `target_id: str`, resolved server-side into a fresh `target_label` via `_canonical_target()` -- the label is never trusted from the caller, it's looked up live against the real object every time one is created. This ADR applies that exact pattern to Memory's `source`.

## Decision

`Memory.source` changed from `str | None` to a structured `MemorySource | None`:

```python
MemorySourceType = Literal["manual", "conversation", "project"]

@dataclass(frozen=True)
class MemorySource:
    source_type: MemorySourceType
    source_id: str | None
    source_label: str
    confidence: float = 1.0
```

Scoped to three source types rather than the full set of objects a memory could conceivably reference (Knowledge notes, Engineering standards, calculations, SirisHydro history) because those are the only three anything in the app can actually produce today. Building resolution machinery for object types no caller can invoke yet would be exactly the kind of half-finished feature this project avoids -- extending to more types later is a small, additive change once a real caller exists for one.

- **`manual`** and **`conversation`** have no addressable SirisOS object behind them -- `source_id` stays `None`, and `source_label` is just whatever the caller supplied (a free-text note, or the fixed "Suggested from SirisAI chat" tag ADR 103 already writes).
- **`project`** is the one type backed by a real object: `source_id` is validated against `ProjectService.get_project()` and `source_label` is always the project's *current* name, re-resolved on every write rather than trusted from the caller -- the same resolve-don't-trust rule `_canonical_target()` already established. An unknown project id raises a new `MemorySourceNotFoundError`, surfaced as 404; a `project` source with no `source_id` is a 422.

`confidence` is fixed at `1.0` on every path that exists today, since Save always requires an explicit human tap (ADR 103) before anything is ever persisted -- there's no write path yet that records a memory without that confirmation, so a lower value would be fake precision. The field is there for a future write path that could.

**Back-compatibility**: existing stored records have `source` as a plain string (or `null`). `_load()` now wraps a bare string into `MemorySource(source_type="manual", source_id=None, source_label=<string>)` rather than crashing the whole store on an old record -- a one-time format-upgrade shim, not a feature flag, since old data has to keep loading.

Mobile: the manual "Remember" dialog's single free-text "Source" field became a typed picker -- None / "A note in my own words" (free text, same as before) / "A project" (a dropdown of real projects fetched from `ProjectService`, picked by id). The chat-suggestion save path (ADR 103) now tags saves with `source_type: conversation` instead of a bare string. The Memory tab renders a `project`-sourced record as "Project: {name}", matching the label style `project_relationships.py`'s own UI already uses.

## Verification

Backend: 374/374 tests passing (13 new: manual/conversation/project source creation, project name always re-resolved fresh even after the project is renamed, unknown project id raises, missing `source_id` for a `project` source raises, and both back-compat loading cases -- a string source and a null source).

Live-verified in the browser: created a real project via the API, then used the "Remember" dialog to save a memory linked to it -- the Memory tab correctly showed "Project: Penrith treatment plant"; saved a second memory as "A note in my own words" -- correctly showed the free-text note with no "Project:" prefix; confirmed a pre-existing chat-suggested memory (saved before this change, stored as a bare string) still loaded and displayed correctly after the schema change, proving the back-compat shim works against real data, not just the test fixture that exercises the same code path.

## Consequences

- Only `project` is a real, resolvable reference today. Knowledge notes, Engineering standards, calculations, and SirisHydro history remain free-text-only (via `manual`) until each has an actual caller wanting to link a memory to one -- deliberately not pre-built.
- `confidence` carries no real signal yet -- every current write path sets it to `1.0`. Worth revisiting once a write path exists that records a memory Siris is less than certain about (e.g. an unconfirmed extraction, distinct from today's always-human-confirmed Save).
- This is the second cross-object-reference pattern in the codebase now (`project_relationships.py`'s target/label, and Memory's source) -- if a third shows up, it's worth asking whether they should share one implementation rather than duplicating the resolve-and-validate logic a third time.
