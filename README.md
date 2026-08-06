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

SirisCore now includes:

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
- Canonical AI Context Service built from the same dashboard state used by briefings and scoring
- Consolidated persisted SirisCore settings for refresh behaviour and module availability
- Event-driven Notification Centre
- Architecture Decision Records under `docs/adr/`

Deferred enhancements such as notification action buttons, direct workspace drag-and-drop, event diagnostics, and Ollama wording remain on the later roadmap and do not block Sprint 0.4.1 completion.

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
- Configurable Mission Control-style workspace

## Next milestone — Sprint 0.4.2 Mission Control

Build a dedicated `/mission` Situation Room for a second monitor or wall display:

- Navigation-free full-screen shell
- Large clock
- Shared registered widget grid
- Siris Score and explanation
- Deterministic briefing
- Activity timeline
- Event-driven refresh
- Focus modes for Work, Home, Fitness, and Travel
- Ambient display modes and restrained animations

After Mission Control, continue with Live Homelab, Engineering, the Obsidian/Selkies Knowledge Platform, Projects and Context Graph, Intelligence and Automation, and the Plugin SDK. See `docs/roadmap.md` for the authoritative sequence.

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
