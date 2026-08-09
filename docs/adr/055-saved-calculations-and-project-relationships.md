# ADR 055 — Saved Engineering calculation records and Project relationships

## Status

Accepted.

## Context

Engineering calculators (ADR 032) are pure, stateless Dart functions — a result exists only in the current widget's state and is lost on navigation. Sprint 0.4.5's roadmap has long carried "save/share calculation records into future project context" as a follow-on, deferred until a project object existed to hold that context. Sprint 0.6 now has one (ADR 049), plus a typed relationship contract already extended once for Engineering Standards (ADR 053). A calculation record is the next natural target type: unlike a standard, which is an external reference document a project does not "contain," a calculation is genuinely project work product.

## Decision

SirisOS adds an authenticated `/api/v1/engineering/calculations` API with stable UUID calculation IDs, storing the calculator identifier, a user-entered title, the raw numeric inputs, the formatted result labels/values, and optional notes. Persistence is an atomic JSON store (`/app/data/engineering-calculations.json`), mirroring the Projects/Standards persistence boundary rather than introducing a new one.

`calculation` is added as a third `TargetType` on the existing Project relationship contract (ADR 050, extended by ADR 053). Unlike Engineering Standard relationships, calculation relationships are not restricted to `references` — a project can `contain` a calculation it produced, or `reference` one done elsewhere, matching the same semantics already used for Knowledge notes.

The Engineering module gains a "Save calculation" action after computing a result, and the Project Context Graph gains an "Attach calculation" action that searches saved calculations, mirroring the Engineering Standard attach flow (ADR 053) so both typed-target attach flows share one interaction pattern.

## Consequences

- Calculation records remain deterministic, auditable artifacts — no calculator hides its inputs; a saved record is exactly the same inputs and outputs the user saw on screen.
- Projects can now visibly accumulate the calculations that informed them, without inventing a second "workspace" concept outside the Project Context Graph.
- Additional typed targets (tasks, files, events, repositories, conversations) can extend the same `TargetType`/node contract incrementally, as already anticipated by ADR 052.
- No new persistence boundary or database schema is introduced; calculation records use the same atomic-JSON pattern already established for Projects and relationships.
