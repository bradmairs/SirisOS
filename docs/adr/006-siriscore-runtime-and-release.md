# ADR 006 — SirisCore runtime and Sprint 0.4.1 release

## Status

Accepted.

## Decision

SirisCore owns the shared runtime services used by all modules:

- the typed Event Bus for change publication;
- the Scheduler for guarded periodic jobs;
- the deterministic Briefing Engine and Siris Score;
- the AI Context Service for canonical prompt-ready context;
- persisted SirisCore settings for refresh and module availability.

Mission Control subscribes to module and notification events, debounces bursts, and refreshes its shared dashboard input. A scheduled refresh remains as a resilience mechanism rather than the primary update path.

The Siris Score is registered through the Widget Registry as `siris.score`, ensuring Dashboard and the future dedicated Mission Control route consume the same implementation.

## Rationale

Centralising runtime behaviour prevents modules from creating independent timers, context formats, refresh loops, or scoring logic. Deterministic context, briefings, and scores remain explainable and can later be rewritten by Ollama without replacing their source logic.

## Consequences

- New modules publish events rather than directly refreshing other screens.
- Recurring client jobs must register with `SirisScheduler` and prevent overlap.
- AI features consume `SirisAIContextService` rather than querying modules independently.
- Future Mission Control work reuses registered widgets and SirisCore services.
- Optional UI enhancements do not block the SirisCore release when their underlying platform contracts are complete.
