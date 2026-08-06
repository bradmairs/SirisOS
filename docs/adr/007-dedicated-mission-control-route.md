# ADR 007 — Dedicated Mission Control route

## Status

Accepted.

## Decision

Mission Control is exposed as a dedicated authenticated `/mission` route with a navigation-free shell. It consumes the existing DashboardService, Event Bus, Scheduler, Widget Registry, Siris Score, Briefing Engine, saved widget layout, and activity timeline.

## Rationale

A second-monitor or wall-display experience requires different chrome and information density from the normal application shell. Reusing the shared registries and deterministic services prevents Mission Control from becoming a separate dashboard implementation with duplicated logic.

## Consequences

- The normal app and Situation Room render the same registered widgets.
- Module events refresh both experiences through the same SirisCore mechanisms.
- Saved widget preferences currently apply to both workspaces.
- Mission Control-specific layout persistence, adaptive prioritisation, focus modes, and ambient behaviour can be added without changing module implementations.
- The route remains authenticated and does not expose a separate unauthenticated display surface.
