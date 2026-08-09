# ADR 053 — Project ↔ Engineering Standard relationships

## Status

Accepted.

## Context

Sprint 0.6 already has a typed Project ↔ Knowledge relationship contract (ADR 050) and a bounded Project Context Graph projection (ADR 052). Engineering projects need to reference the exact private standards revisions they were designed against, addressed by the standard's immutable document ID (ADR 037) rather than a free-text title that could drift across revisions.

## Decision

`engineering_standard` is added as a second `TargetType` on the existing `/api/v1/projects/{project_id}/relationships` contract, alongside `knowledge_note`. A relationship target is identified by its immutable standards-library document ID and resolved to a citation-style label (reference/title, edition, and library revision when greater than one) using the same metadata the Engineering Standards API already exposes.

Engineering standard relationships are restricted to the `references` kind; a project does not "contain" a standard the way it contains a Knowledge note. Creating a `contains` relationship against an `engineering_standard` target is rejected with `422`.

The Project Context Graph projection gains a matching `engineering_standard` node type. Flutter's Projects → Graph view adds an "Attach Engineering standard" action that searches the private standards library and attaches the selected active revision as a reference edge.

## Consequences

- Project graphs can show exactly which standard revision informed a project without duplicating standards metadata into the project store.
- Because the document ID is immutable, replacing a standard as a new revision (ADR 037) does not silently reassign existing project references; a stale reference remains visible rather than being rewritten.
- Additional typed targets (tasks, files, calculations, events, repositories, conversations) can extend the same `TargetType`/node contract incrementally.
- No new persistence boundary is introduced; relationships continue to use the atomic JSON store from ADR 050.
