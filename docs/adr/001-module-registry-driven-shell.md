# ADR 001: Module Registry-Driven Application Shell

- Status: Accepted
- Date: 2026-08-07

## Context

Desktop navigation, mobile navigation, search targets, and quick actions were previously maintained as separate hardcoded lists in `AppShell`. Adding or reordering a module required coordinated edits in several places, creating drift and making future optional modules difficult to support.

## Decision

The SirisOS module registry is the single source of truth for module identity, navigation order, navigation icons, capabilities, and primary quick-action metadata.

`AppShell` derives desktop and mobile navigation and module quick actions from the registry. Screen construction remains in the shell for this slice and will move into module-owned route builders in a later SirisCore increment.

## Consequences

- New navigation modules can be introduced with substantially less duplicated shell code.
- Desktop and mobile navigation remain aligned automatically.
- Quick actions are capability-driven and use module metadata.
- The registry now includes the Dashboard as a shell module.
- Route builders and optional/unavailable module handling remain explicit follow-up work.
