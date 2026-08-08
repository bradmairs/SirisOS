# ADR 031 — SirisCore Context Service

## Status
Accepted

## Context
SirisOS now has multiple reliable state sources: integrations, Notification Policies, incidents, history, capabilities, Mission Control and Operations Center. Future planners, playbooks, presence logic and SirisAI need a shared answer to "what is happening right now?" without polling every subsystem independently or duplicating inference rules.

## Decision
Introduce `SirisCoreContextService` as the deterministic context aggregation layer.

- Context is represented as typed `SirisContextFact` values with stable IDs, domains, priorities, sources and optional details.
- Providers implement `SirisContextProvider` and contribute facts without owning global resolution.
- The service sorts active facts by priority and exposes a single `SirisContextSnapshot`; the highest-priority fact is the current primary context.
- Context transitions are recorded in a bounded in-memory timeline and published through the existing Event Bus using `ContextSnapshotChanged`.
- Context enrichment is non-blocking: provider failure must not break authentication, integrations or the application shell.
- The first provider is intentionally operational and derives only contexts SirisOS can justify from existing integration health and Notification Policy state: power event, backup attention, degraded network/storage/compute, or nominal homelab state.
- Personal, engineering and AI contexts will only be activated when authoritative providers exist (for example Health Data Export, Home Assistant presence, calendar/project state, Ollama/Hermes task state).
- `siris.context` is a reusable Mission Control widget and the same context panel is surfaced in Operations Center.

## Consequences
The platform now has a shared, deterministic current-context contract that future planners, playbooks, notification suppression, SirisAI and presence logic can consume. The initial timeline is runtime-only; canonical persistence/history remains follow-on work. Context is explicitly evidence-based and must not infer personal states from weak signals.

## Follow-on
- Persistent context timeline through the generic History Engine
- Manual context override with expiry and provenance
- Health Data Export and Home Assistant presence providers
- Calendar/work/project providers
- Context-aware Briefing Engine and Siris Score
- Context API for backend/Hermes consumers
- Presence Engine built on top of context providers rather than parallel state
