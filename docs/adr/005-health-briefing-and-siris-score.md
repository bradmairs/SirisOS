# ADR 005: Health briefing input and deterministic Siris Score

## Status

Accepted

## Context

The Briefing Engine previously had no dedicated Health data in its shared input, and the planned Siris Score required a deterministic, explainable foundation before any Mission Control presentation was added.

## Decision

- `DashboardSummary` may carry an optional `HealthSnapshot`.
- `DashboardService` fetches the Health snapshot as part of the combined dashboard refresh and degrades gracefully when Health is unavailable.
- The Health briefing contributor emits observations only from supported snapshot data.
- The first Siris Score model uses weighted Health, Running, Gym, Homelab, and system domains.
- Every score contribution includes a plain-language explanation.
- Missing Health configuration is treated neutrally rather than as a failure.
- Knowledge, Tasks, Engineering, and Automation domains will be added only when those modules expose reliable deterministic inputs.

## Consequences

The briefing and score now share one consistent input model. Health data failures do not break Mission Control, and the score remains auditable rather than becoming an opaque AI-generated number.

The score is currently a core calculation only. Its widget and dedicated Mission Control presentation are separate roadmap items.
