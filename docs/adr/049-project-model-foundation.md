# ADR 049 — General project model foundation

## Status

Accepted.

## Context

Sprint 0.6 needs a stable project identity before SirisOS can safely relate notes, tasks, calculations, events, repositories and conversations. Those relationships should point to an authoritative project object rather than free-text project names.

## Decision

SirisOS introduces an authenticated `/api/v1/projects` API with stable UUID project IDs, explicit project kind and lifecycle status, bounded tags, timestamps and descriptions.

The first persistence boundary is a small atomic JSON store under `/app/data/projects.json` (configurable with `SIRISOS_PROJECTS_PATH`). Writes use same-directory temporary files followed by atomic replacement. This keeps the initial model deployable without introducing a second database schema before relationship semantics are proven.

Project kinds are `engineering`, `homelab`, `travel`, `fitness`, `personal` and `other`. Lifecycle states are `active`, `paused`, `completed` and `archived`.

This slice deliberately does not infer project membership and does not yet attach Knowledge notes or other objects. Relationship records will be a separate typed contract with provenance.

## Consequences

- Future relationships can target immutable project IDs.
- Project lifecycle is explicit rather than inferred from activity.
- The persistence implementation can later migrate to PostgreSQL behind the same API contract.
- Project writes do not change the read-only Knowledge vault boundary.
