# ADR 050 — Project ↔ Knowledge relationship contract

## Status

Accepted.

## Context

Sprint 0.6 needs projects to become context containers for notes and, later, tasks, files, calculations, events, repositories and conversations. SirisOS already has stable project UUIDs and a read-only Knowledge vault. Relationships must not mutate Markdown or rely on project names that can change.

## Decision

SirisOS stores project relationships separately from both project records and the Knowledge vault.

The first supported target type is `knowledge_note`, identified by its canonical vault-relative Markdown path. Relationship records contain their own immutable UUID, the stable project UUID, target type/id, relationship kind, manual provenance and creation time.

Supported initial kinds are:

- `contains` — the target is part of the project's working context;
- `references` — the project refers to the target without claiming ownership.

Creating a Knowledge relationship validates that the note exists and canonicalizes its vault-relative path. The note title is resolved as display metadata; the path remains the identity. Duplicate project/target/kind relationships are rejected.

Relationship persistence is an atomic JSON file alongside `projects.json`. This intentionally mirrors the first project-store boundary and can later move behind a database-backed repository without changing the public API.

## Consequences

- Renaming a project does not break relationships because project UUIDs remain stable.
- SirisOS does not write relationship metadata into the Obsidian vault.
- Missing or later-moved notes can remain visible as stale relationship evidence rather than being silently reassigned.
- Additional typed targets can be added incrementally without inventing module-specific linking systems.
