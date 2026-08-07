# ADR 010 — Mission Control focus and ambient presentation

## Status

Accepted.

## Context

Mission Control needs to adapt to the user's current context and remain useful as a second-monitor or wall display without creating separate widget implementations or modifying the user's saved workspace.

## Decision

Focus Modes and ambient mode are transient presentation layers over the existing Widget Registry and saved dashboard layout.

Focus Modes use a deterministic policy to select relevant registered widgets for All, Work, Home, Fitness, and Travel. The selected focus is persisted, but widget order, visibility, and size preferences remain user-owned and unchanged.

Ambient mode is triggered after 30 seconds of inactivity when enabled. It reduces chrome, enlarges the clock, suppresses clock seconds, and limits the number of lower-priority widgets shown. Pointer interaction, module data changes, and notification state changes wake the interface. Critical status always overrides ambient presentation and triggers the existing critical wake state.

Reduced motion is a persisted Mission Control preference and removes non-essential transition duration without changing application state or data behaviour.

## Consequences

- Future modules can join Focus Modes by registering widgets and extending the focus policy rather than adding new screens.
- Mission Control continues to consume one Widget Registry and one source of dashboard data.
- Ambient and focus presentation cannot overwrite saved layout preferences.
- Critical alerts remain visible regardless of inactivity state.
- Burn-in-conscious behaviour reduces continuously changing content during unattended display use.
