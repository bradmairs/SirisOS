# ADR 048 — Typed Knowledge contexts and explicit production API entrypoint

## Status
Accepted

## Context

Knowledge is becoming a cross-module substrate for SirisOS. The first Engineering and Homelab links used an Obsidian-visible `siris/<module>` tag and queried the generic Knowledge search endpoint. That was useful, but a search filter is not a durable relationship contract.

A separate integration risk also became visible: modular FastAPI routers can exist and pass isolated tests without necessarily being mounted by the production Uvicorn application.

## Decision

SirisOS defines an explicit Knowledge context relationship that may be authored either as frontmatter:

```yaml
---
siris: [engineering, homelab]
---
```

or as an Obsidian-visible tag such as `#siris/engineering`.

The authenticated `/api/v1/knowledge/context` endpoint resolves these explicit relationships and returns exact vault-relative note identities. No AI or inferred relationship is persisted as a durable context link.

Production Uvicorn starts `app.entrypoint:app`. That entrypoint layers modular API routers onto the legacy core `app.main` application. CI guards both the supervisor target and the expected router registry so a feature API cannot be silently omitted from the production app while still passing isolated module tests.

## Consequences

- Engineering/Homelab panels depend on a typed context API rather than general search semantics.
- Markdown remains the relationship source of truth and the vault remains read-only.
- The same context contract can later be consumed by Tasks, Calendar, Briefings and Projects when those modules have authoritative object models.
- Production startup has one explicit modular API registration point.
- `app.main` can be incrementally decomposed later without blocking feature work.
