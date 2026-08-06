# SirisOS

SirisOS is a self-hosted personal operating system bringing together homelab monitoring and control, health and fitness, civil engineering tools, personal knowledge, automation, media services, and AI assistance.

The product must help the user:

1. Know something important.
2. Decide what to do next.
3. Act without leaving SirisOS.

This README is the authoritative project handover and roadmap. Future developers and AI development sessions should read it before making architectural or sequencing decisions. `docs/roadmap.md` is the matching implementation checklist. Whenever roadmap scope or status changes, update both files.

## Product direction

SirisOS is a modular platform built around **SirisCore** and a dedicated **Mission Control** experience. Modules register identity and capabilities, publish typed events, and contribute reusable widgets, notifications, briefing observations, search targets, quick actions, and AI context.

Avoid isolated feature pages when a capability should instead be a shared SirisCore service, registered module, or reusable widget.

## Stack

- Flutter frontend served by Nginx
- FastAPI backend
- PostgreSQL
- Docker Compose
- Restricted Docker socket proxy
- SharedPreferences for local UI layout preferences
- Ollama integration planned
- Obsidian hosted separately in Docker through Selkies, with future SirisOS integration planned

## Standard deployment workflow

Completed work is merged into `main` and must remain deployable with:

```bash
git pull
make up
```

`make up` creates `.env` from `.env.example` when required, creates persistent data directories, rebuilds Docker images, and starts the complete stack. Any unavoidable migration or configuration change must be documented clearly.

## Current capabilities

- Responsive Flutter web application and persisted authentication
- Configurable Mission Control-style dashboard workspace
- Persistent widget ordering, visibility, and sizing
- Namespaced widget IDs such as `running.summary`
- Module-owned widget registrations and reusable widget builders
- Automatic migration of legacy saved widget layouts
- SirisOS module registry with IDs, labels, icons, capabilities, navigation metadata, and quick actions
- Registry-driven desktop and mobile navigation
- Module-owned screen builders and availability metadata
- Consistent preview and unavailable module screens
- Typed SirisCore broadcast event bus
- Event-driven Notification Centre with severity and read/unread state
- Typed deterministic briefing observations with ranking, deduplication, expiry, and fallback assembly
- Running, Gym, Homelab, and system briefing contributors
- Running logging and fitness trends
- Gym workouts, templates, progress, and personal records
- Health Auto Export MCP integration scaffold
- Live Docker monitoring and container control
- Host metrics, history, Homelab alerts, audit history, and logs
- Home Assistant, Plex, and Ollama diagnostics
- Dashboard recommendations, deterministic briefing output, and trend sparklines
- Global search

# Authoritative development roadmap

## Sprint 0.4.1 — SirisCore

This is the current development priority. Complete SirisCore before substantial work continues on the dedicated Mission Control display.

### Event Bus

- [x] Typed broadcast event bus
- [x] Generic module data-change events
- [x] Mission Control refresh events
- [x] Notification state-change events
- [x] Running and Gym publishers
- [x] Health snapshot publisher
- [x] Homelab container-action publisher
- [x] Notification Centre subscriptions and debounced refresh
- [ ] Dashboard and Mission Control subscriptions
- [ ] Statistics, briefing, and AI-context subscriptions

### Module Registry

- [x] Central module registry
- [x] IDs, labels, descriptions, icons, and capability declarations
- [x] Dashboard, Homelab, Running, Gym, Health, and Siris definitions
- [x] Registry-driven desktop navigation rail
- [x] Registry-driven mobile navigation
- [x] Registry-driven quick actions
- [x] Module-owned route and screen builders
- [x] Preview and unavailable module handling
- [ ] Persisted module enable/disable settings

### Widget Registry

- [x] Widget metadata registry
- [x] Namespaced IDs such as `running.summary`
- [x] Reusable widget builders
- [x] Module-owned widget registration
- [x] Persistent widget visibility, ordering, and sizing
- [x] Legacy saved-layout migration
- [x] Dashboard consumption through registered builders
- [ ] Shared dedicated Mission Control consumption
- [ ] Direct drag-and-drop and resizing

### Notification Centre

- [x] Persistent events
- [x] Info, Success, Warning, and Critical severity
- [x] Module source and timestamp
- [x] Read/unread state, filters, badge, and read-all action
- [x] Live Event Bus subscriptions
- [ ] Action metadata and action buttons
- [ ] Consistent notification policies for every module

### Briefing Engine and Siris Score

- [x] Existing dashboard briefing strings and rules-based recommendations
- [x] Standard observation model and contributor interface
- [x] Running, Gym, and Homelab contributors
- [x] Health contributor registration without fabricated observations
- [x] Priority scoring, deduplication, and expiry
- [x] Deterministic briefing assembly with backend fallback
- [x] Briefing widget consumes deterministic output
- [ ] Add dedicated Health data to the shared briefing input
- [ ] Event-driven briefing refresh
- [ ] Optional Ollama rewriting layer
- [ ] Deterministic Siris Score across health, fitness, Homelab, knowledge, tasks, engineering momentum, and automation health
- [ ] Human-readable score explanation showing which domains raised or lowered the result

### Remaining SirisCore systems

- [ ] Scheduler
- [ ] AI context service
- [ ] Theme and settings consolidation

## Sprint 0.4.2 — Mission Control

Build a dedicated `/mission` route for a second monitor or wall display.

- [x] Configurable workspace foundation
- [x] Persistent ordering, visibility, and sizing
- [ ] Navigation-free full-screen shell
- [ ] Large live clock
- [ ] Siris Score
- [ ] Deterministic briefing panel
- [ ] Reusable widget grid and activity timeline
- [ ] Event-driven auto-refresh
- [ ] Smooth transitions and ambient modes

## Sprint 0.4.3 — Live Homelab

- [x] Live containers, CPU/RAM, state, health, logs, and actions
- [x] Host metrics and history
- [x] Alerts and action audit history
- [x] Home Assistant, Plex, and Ollama diagnostics
- [ ] Container image update availability
- [ ] Broader event-driven notification policies
- [ ] Prometheus, Grafana, expanded Home Assistant, and UniFi integrations

## Sprint 0.4.4 — Engineering Module

- [ ] Engineering module scaffold
- [ ] Manning equation calculator
- [ ] Pipe capacity calculator
- [ ] Rational Method calculator
- [ ] Pipe buoyancy checker
- [ ] Detention basin sizing helper
- [ ] Standards search scaffold for WSAA, Sydney Water, Austroads, Australian Standards, and authority requirements
- [ ] SirisHydro and SirisPM integration
- [ ] Project notes, AI-assisted drawing review, and Civil 3D utilities

## Sprint 0.5.0 — Knowledge Platform

Integrate the existing server-hosted Obsidian instance running in Docker through Selkies. Obsidian should become the Knowledge pillar of SirisOS rather than only an embedded application.

- [ ] Obsidian/Selkies launch integration
- [ ] Vault browser
- [ ] Recent notes and Daily Notes widgets
- [ ] Global SirisOS search across vault content
- [ ] Wikilink navigation and graph exploration
- [ ] Metadata and tag support
- [ ] AI semantic search across the vault
- [ ] Mission Control Knowledge widget
- [ ] Context-aware related note suggestions
- [ ] Cross-linking with Engineering, Homelab, Tasks, Calendar, and Briefings

Long-term examples include surfacing engineering project notes beside calculations, Homelab documentation beside infrastructure alerts, and relevant Daily Notes within the briefing engine.

## Later AI, knowledge, and personal modules

- Ollama integration and module-aware Siris assistant
- `Ctrl/Cmd + K` command palette
- Personal knowledge search and AI context service
- AI wording layered over deterministic briefings
- Tasks, calendar, briefing delivery, health trends, training plans, media integrations, and personal automations

## UI direction

- Premium dark theme with red and black accents
- Glass-style cards
- Responsive desktop layout
- Animated sparklines
- Widget-based dashboard and Mission Control
- Command palette and Notification Centre
- Smooth, restrained animations
- Clear warning and critical states

## Required sequencing

Unless deliberately revised and documented:

1. Add Health briefing input and event-driven briefing refresh.
2. Build the deterministic Siris Score foundation and explanation model.
3. Complete Scheduler, AI Context, and remaining SirisCore systems.
4. Declare Sprint 0.4.1 complete.
5. Build the dedicated Mission Control route using the shared Widget Registry.
6. Finish Live Homelab capabilities.
7. Begin the Engineering module.
8. Build the Obsidian-backed Knowledge Platform.

# Running and development

```bash
cp .env.example .env
make up
```

Web UI: `http://192.168.0.100:6464`

API: `http://192.168.0.100:8000`

API docs: `http://192.168.0.100:8000/docs`

Useful commands:

```bash
make up
make dev
make backend
make rebuild-web
make status
make logs
make restart
make stop
make clean
```

Runtime data is stored under `data/`. Back up `data/` and `.env` to preserve the installation. Docker control endpoints must remain limited, authenticated, and auditable.

# Development handover checklist

1. Read this README and `docs/roadmap.md`.
2. Inspect the latest commits on `main`.
3. Base new work on the latest `main`.
4. Follow the required sequencing.
5. Preserve `git pull` followed by `make up`.
6. Merge finished coherent slices into `main`.
7. Update both roadmap documents whenever scope or status changes.
8. Record significant architectural decisions under `docs/adr/`.
