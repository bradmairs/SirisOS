# ADR 008 — Adaptive Mission Control layout

## Status

Accepted.

## Context

Mission Control must surface urgent information without silently overwriting the user's carefully arranged workspace. A critical infrastructure event should become prominent immediately, while normal operation should continue to respect the saved layout.

## Decision

Mission Control applies a transient priority layer over the persisted widget preferences.

- The saved layout remains the source of truth for visibility, order, and preferred size.
- Adaptive mode ranks widgets using deterministic module status and fixed core priorities.
- Warning and critical widgets move forward and may temporarily expand to wide size.
- The adaptive result is never written back to layout storage.
- Users can disable adaptive mode and return to the exact saved order.
- Display preferences such as adaptive mode and clock seconds are persisted separately.

## Consequences

Mission Control can react visibly to problems without surprising users by permanently changing their configuration. Future relevance inputs may include notifications, briefing priority, focus mode, time, calendar context, and critical wake events, but they must remain deterministic and explainable.
