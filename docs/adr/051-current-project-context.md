# ADR 051 — Explicit current project context

## Status

Accepted.

## Context

Sprint 0.6 has stable project identities and typed Project ↔ Knowledge relationships. SirisCore still needs an authoritative answer to “which project is current?” before project-aware briefings, recommendations, SirisHydro/SirisPM workflows or SirisAI context can be added safely.

Inferring a current project from recently opened notes, browser activity or timestamps would violate the existing context rule that context claims require provider-backed provenance.

## Decision

SirisOS stores one optional **current project** selection on the backend and exposes it through authenticated `GET/PUT /api/v1/projects/current` endpoints.

The selection is manual, persists independently from Flutter, and records selection time plus `manual` provenance. Only active or paused projects may be selected. Completing or archiving the selected project clears the selection automatically.

Flutter exposes the selection under Projects → Current. A `ProjectContextProvider` contributes the selected project to SirisCore with explicit `projects.manual_selection` provenance. Engineering projects map to the Engineering context domain, Homelab projects to Homelab, and other project kinds to Personal.

Project context priority is intentionally below critical operational states such as UPS power events or degraded infrastructure. It enriches normal context without masking urgent evidence-backed conditions.

## Consequences

- Mission Control and other SirisCore consumers can use an explicit current project without guessing.
- Future backend/Hermes consumers can share the same persisted selection.
- Switching projects is a deliberate user action and immediately refreshes SirisCore context.
- Project selection does not mutate the read-only Knowledge vault.
- Automatic project inference remains out of scope until an explicit evidence/provenance design exists.
