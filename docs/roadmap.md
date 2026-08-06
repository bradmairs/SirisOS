# SirisOS Roadmap

## Milestone 1 — Foundation

- Repository scaffold
- FastAPI service and health endpoint
- PostgreSQL development service
- Docker Compose environment
- Flutter application scaffold
- Configuration and secrets model
- Automated backend tests

## Milestone 2 — Dashboard and Homelab

- Dashboard API and card layout
- Docker container status
- Home Assistant status
- Plex server status
- Integration settings
- Read-only alerts and summaries
- Read-only Home Assistant, Plex, and Ollama diagnostics API

## Milestone 3 — Personal Modules

- Tasks and calendar
- Gym workout logging
- Health data import
- Trends and progress charts
- Morning briefing

## Milestone 4 — SirisCore and Mission Control

- [x] Mission Control widget registry
- [x] Namespaced widget IDs
- [x] Module-owned widget registration
- [x] Reusable widget builders
- [x] Legacy layout ID migration
- [x] Persistent widget visibility, ordering and sizing
- [x] Existing dashboard panels rendered through registered builders
- [x] Module registry with declared capabilities
- [x] Typed broadcast event bus
- [x] Mission Control refresh events
- [x] Running and Gym data-change event publishers
- [x] Health snapshot refresh event publisher
- [x] Homelab container action event publisher
- [x] Notification unread/read state events
- [x] Notification Centre live event subscriptions
- [x] Automatic debounced Notification Centre refresh
- [x] Registry-driven desktop navigation
- [x] Registry-driven mobile navigation
- [x] Registry-driven module quick actions
- [x] Module-owned route and screen builders
- [x] Preview and unavailable module handling
- [x] Typed briefing observation model and contributor interface
- [x] Running, Gym, Homelab, and system briefing contributors
- [x] Dedicated Health snapshot in the shared briefing input
- [x] Deterministic Health briefing observations for availability, sleep, steps, and resting heart rate
- [x] Deterministic briefing ranking, deduplication, expiry, and assembly
- [x] Briefing widget consumes deterministic output with backend fallback
- [x] Siris Score deterministic weighted domain model
- [x] Human-readable Siris Score contribution explanations
- [ ] Event-driven briefing refresh subscriptions
- [ ] Siris Score widget and Mission Control presentation
- [ ] Shared dedicated Mission Control consumption
- [ ] Module enable/disable settings and persisted availability
- [ ] Drag-and-drop layout directly on the workspace
- [ ] Notification action metadata and action buttons
- [ ] Consistent module notification policies
- [ ] Dashboard and Mission Control event subscriptions
- [ ] Scheduler
- [ ] AI context service
- [ ] Ambient display modes

## Milestone 5 — AI and Knowledge

- Ollama integration
- Command palette
- Personal knowledge search
- AI-generated daily briefing
- Integration diagnostics UI

## Milestone 6 — Engineering

- Hydraulic calculators
- Standards knowledge library
- SirisHydro integration
- SirisPM integration
- Project notes and tools

## Sprint 0.5.0 — Knowledge Platform

Integrate the existing server-hosted Obsidian instance running in Docker through Selkies and make the vault a first-class SirisOS knowledge source.

- [ ] Obsidian/Selkies launch integration
- [ ] Vault browser
- [ ] Recent notes widget
- [ ] Daily Notes integration
- [ ] Global SirisOS search across vault content
- [ ] Wikilink navigation and graph exploration
- [ ] Metadata and tag support
- [ ] AI semantic search across the vault
- [ ] Mission Control Knowledge widget
- [ ] Context-aware related note suggestions
- [ ] Cross-linking with Engineering, Homelab, Tasks, and Briefings
