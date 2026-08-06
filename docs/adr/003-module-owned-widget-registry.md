# ADR 003: Module-owned reusable Widget Registry

## Status

Accepted

## Context

Mission Control widgets were previously identified by short hardcoded IDs and rendered through a switch inside `DashboardScreen`. That coupled the workspace to every widget implementation, made future module additions require shell changes, and prevented Dashboard and the dedicated Mission Control route from sharing one reusable widget source.

Saved layouts also used the original IDs (`briefing`, `homelab`, `running`, `gym`, `system`, and `activity`), so changing IDs without migration would discard user preferences.

## Decision

SirisOS uses a central application Widget Registry composed of module-owned registration groups.

Each registered widget provides:

- A namespaced ID such as `running.summary`
- An owning module ID
- Display metadata and default size
- A reusable builder consuming a common Mission Control context

Dashboard rendering and layout customisation resolve widgets through this registry instead of an ID switch. Legacy IDs are mapped to their canonical namespaced IDs when saved layouts are loaded, preserving order, visibility, and size preferences.

## Consequences

- New modules can contribute widgets without modifying Dashboard rendering logic.
- Dashboard and the future dedicated Mission Control route can consume the same builders.
- Widget ownership is explicit and inspectable.
- Persistent layouts remain compatible across the ID migration.
- Widget builders currently consume a dashboard summary context; this context may expand as SirisCore adds briefing, score, scheduler, and AI-context services.
