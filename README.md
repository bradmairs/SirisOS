# SirisOS

SirisOS is a self-hosted personal operating system that unifies personal health and fitness, homelab infrastructure, engineering tools, knowledge, automation, and AI assistance.

Its purpose is to help the user:

1. Know something important.
2. Decide what to do next.
3. Act without leaving SirisOS.

This README is the authoritative project handover. `docs/roadmap.md` is the implementation checklist. Update both whenever scope or status changes.

## Product architecture

SirisOS is a modular platform built around **SirisCore** and the **Mission Control** experience. Modules register identity, capabilities, screens, quick actions, widgets, notifications, briefing observations, search providers, and AI context.

Core principles:

- One source of truth
- Event-driven updates
- Deterministic and explainable intelligence
- Context over raw data
- Reusable platform services instead of isolated pages
- `main` remains deployable

## Standard deployment workflow

Completed work is merged into `main` and deployed with:

```bash
git pull
make up
```

`make up` creates missing local configuration and data directories, rebuilds the Docker images, and starts the stack.

## Sprint 0.4.1 — SirisCore complete

SirisCore includes:

- Typed broadcast Event Bus
- Module data-change and notification events
- Event-driven, debounced Mission Control refreshes
- Central Module Registry
- Module-owned screens, routes, quick actions, and availability states
- Reusable Widget Registry with namespaced IDs
- Persisted widget order, visibility, and sizing
- Legacy layout migration
- Deterministic Briefing Engine
- Running, Gym, Health, Homelab, and system briefing contributors
- Deterministic Siris Score with weighted domains and plain-language explanations
- Registered `siris.score` widget
- Shared Scheduler for guarded recurring jobs
- Canonical AI Context Service built from shared dashboard state
- Consolidated persisted SirisCore settings
- Event-driven Notification Centre
- Architecture Decision Records under `docs/adr/`

## Active milestone — Sprint 0.4.2 Mission Control

### Situation Room foundation

The dedicated Mission Control experience is available at `/mission` and includes:

- Navigation-free full-screen shell
- Large live clock and date
- Shared registered widget grid
- Siris Score, deterministic briefing, module summaries, and activity timeline
- Event-driven debounced refreshes
- Five-minute scheduled refresh fallback
- Responsive layouts for desktop, tablet, and narrow screens
- Smooth layout transitions
- Explicit refresh and exit controls
- In-app launchers in the desktop shell and quick-actions menu

### Adaptive runtime foundation

Mission Control now supports persisted display controls for:

- Adaptive prioritisation on or off
- Optional clock seconds

Adaptive mode applies a transient deterministic priority layer over the saved layout:

- Siris Score and briefing remain prominent
- Warning and critical module widgets move forward
- Attention-worthy widgets may temporarily expand
- The user's stored widget order and sizes are never overwritten
- Disabling adaptive mode immediately restores the saved presentation

This rule is documented in `docs/adr/008-adaptive-mission-control-layout.md`.

Next within Sprint 0.4.2:

- Add critical-event wake behaviour
- Add Mission Control-specific display profile persistence
- Add event diagnostics and refresh latency visibility
- Add Focus Modes for Work, Home, Fitness, and Travel
- Add ambient mode and second-monitor refinements
- Complete the SirisOS design system and visual polish

## Current application capabilities

- Responsive Flutter web application with persisted authentication
- FastAPI backend and PostgreSQL
- Docker Compose deployment
- Restricted Docker socket proxy
- Running logging and trends
- Gym workouts, templates, progress, and personal records
- Health Auto Export MCP integration scaffold
- Live Docker monitoring and container actions
- Host metrics, history, alerts, audit history, and logs
- Home Assistant, Plex, and Ollama diagnostics
- Global search
- Configurable Mission Control workspace
- Dedicated `/mission` Situation Room with adaptive prioritisation

## Long-term pillars

- **Personal:** Health, recovery, running, gym, sleep, and nutrition
- **Infrastructure:** Docker, Home Assistant, UniFi, Proxmox, NAS, backups, UPS, Plex
- **Engineering:** SirisHydro, SirisPM, calculators, standards, Civil 3D, project tools
- **Knowledge:** Obsidian, documents, notes, search, semantic memory
- **Intelligence:** Briefings, Siris Score, recommendations, Ollama, agents, context
- **Automation:** n8n, schedules, triggers, scripts, workflows, notifications

## Development handover checklist

1. Read this README and `docs/roadmap.md`.
2. Inspect the latest commits on `main`.
3. Follow the documented sprint order.
4. Keep finished slices deployable with `git pull && make up`.
5. Update README and roadmap together.
6. Record significant architecture decisions in `docs/adr/`.
7. Prefer reusable SirisCore services over one-off feature code.

## Local endpoints

- Web UI: `http://192.168.0.100:6464`
- Mission Control: `http://192.168.0.100:6464/#/mission`
- API: `http://192.168.0.100:8000`
- API docs: `http://192.168.0.100:8000/docs`

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

Runtime state is stored under `data/`. Back up `data/` and `.env` to preserve the installation.
