# ADR 009: Mission Control wake state, profiles, and diagnostics

## Status

Accepted.

## Context

Mission Control needs to react visibly to critical conditions, support different second-monitor densities, and expose enough runtime information to diagnose stale or slow refresh behaviour. These features must not overwrite the user's saved widget layout.

## Decision

- Critical status values create a temporary 30-second wake state.
- Wake state forces adaptive prioritisation and adds a visible critical banner, but does not persist layout changes.
- Display profiles are persisted separately from widget layout:
  - Balanced: normal general-purpose density.
  - Operations: higher information density.
  - Compact: limits the display to the four highest-priority visible widgets.
- Runtime diagnostics are held in memory and show event count, latest event type, and last dashboard refresh latency.
- User-owned order, visibility, and widget sizes remain the canonical layout source.

## Consequences

Mission Control can escalate urgent conditions and support multiple display contexts without corrupting customisation. Diagnostics reset when the application reloads, which is acceptable for this first operational visibility layer. Persistent event history remains the responsibility of the existing activity and notification services.
