# ADR 002: Module-owned route and screen registration

## Status

Accepted

## Context

The Module Registry already owned navigation metadata and quick-action declarations, but `AppShell` still contained a switch statement mapping module IDs to screen widgets. That left the shell coupled to every module and required central edits whenever a module was added or changed.

SirisOS is intended to support many future modules, including Engineering, Knowledge/Obsidian, Tasks, Calendar, Home Assistant, UniFi, and additional AI tools. A shell-level screen switch would become increasingly brittle and would undermine the goal of self-contained modules.

## Decision

Introduce an application module registration layer that pairs each core `SirisModuleDefinition` with:

- a screen builder;
- runtime screen context where required;
- an availability state;
- an optional unavailable or preview explanation.

`AppShell` consumes these registrations and no longer imports or selects individual module screens.

Availability is represented explicitly as:

- `available` — normal screen builder is used;
- `preview` — module appears in navigation with a consistent preview screen;
- `unavailable` — module appears with a consistent unavailable state and explanation.

Quick actions are only generated for registrations that are currently available.

## Consequences

### Positive

- New modules can provide screen ownership without changing `AppShell`.
- Navigation, screen creation, availability, and quick actions use shared registration data.
- Planned modules can appear as previews without one-off placeholder screens.
- Unavailable integrations fail visibly and consistently.
- The shell remains focused on layout and navigation rather than module implementation.

### Trade-offs

- The application registration layer imports concrete screens and therefore sits above the core metadata registry.
- Some modules require runtime context, such as incrementing Running and Gym form-request counters.
- Persisted user enable/disable settings remain future work.

## Follow-up

- Add persisted module enable/disable settings.
- Move reusable widget ownership into module registrations.
- Add module-owned search targets, briefing contributors, and notification policies.
- Use the same availability model for future Engineering and Obsidian Knowledge modules.
