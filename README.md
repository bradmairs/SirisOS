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

SirisCore includes the typed Event Bus, Module and Widget Registries, deterministic Briefing Engine and Siris Score, Scheduler, AI Context Service, persisted settings, and event-driven Notification Centre. Significant decisions are recorded under `docs/adr/`.

## Active milestone — Sprint 0.4.2 Mission Control

### 0.4.2a — Situation Room foundation complete

The authenticated `/mission` experience includes a navigation-free shell, large live clock/date, shared registered widget grid, Siris Score, deterministic briefing, activity timeline, event-driven refresh, scheduled fallback, responsive layout, in-app launchers, and display controls.

### 0.4.2b — Adaptive runtime complete

Mission Control provides deterministic adaptive ordering, temporary enlargement for attention-worthy widgets, critical-event wake, persisted Balanced/Operations/Compact display profiles, optional clock seconds, and runtime event/refresh diagnostics. Adaptive presentation never overwrites the saved widget layout.

### 0.4.2c — Focus and ambient modes complete

Mission Control now adds:

- Persisted **All**, **Work**, **Home**, **Fitness**, and **Travel** Focus Modes
- Focus policies that select and order existing registered widgets without changing saved workspace data
- Ambient mode after 30 seconds of inactivity
- Larger clock, reduced chrome, and fewer lower-priority widgets in ambient presentation
- Automatic wake from module and notification events
- Critical events overriding ambient mode immediately
- Persisted reduced-motion preference
- Burn-in-conscious behaviour by hiding seconds and reducing continuously changing display elements in ambient mode

Focus and ambient presentation are transient views over the same SirisCore data and Widget Registry. They do not create duplicate widgets or fork business logic.

### Next: 0.4.2d — Design system and polish

- Introduce shared SirisCard, SirisMetric, SirisPanel, SirisTimeline, SirisGauge, and SirisStatusChip components
- Refine the premium red/black visual language
- Consolidate typography, spacing, transitions, and warning states
- Move Mission Control controls onto the shared design system

## Current application capabilities

- Responsive Flutter web application with persisted authentication
- FastAPI backend, PostgreSQL, and Docker Compose deployment
- Restricted Docker socket proxy
- Running logging and trends
- Gym workouts, templates, progress, and personal records
- Health Auto Export MCP integration scaffold
- Live Docker monitoring and container actions
- Host metrics, history, alerts, audit history, and logs
- Home Assistant, Plex, and Ollama diagnostics
- Global search
- Configurable workspace and dedicated adaptive `/mission` Situation Room
- Mission Control display profiles, Focus Modes, ambient display, critical wake, and diagnostics

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
