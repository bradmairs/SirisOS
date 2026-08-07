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

## Sprint 0.4.2 — Mission Control complete

The authenticated `/mission` Situation Room provides a navigation-free full-screen Mission Control with live clock/date, shared Widget Registry grid, Siris Score, deterministic briefing, activity timeline, adaptive prioritisation, critical wake, display profiles, Focus Modes, ambient mode, diagnostics, reduced-motion behaviour, and the shared SirisOS design system.

Architecture is documented in ADRs 007–011.

## Active milestone — Sprint 0.4.3 Live Homelab

### 0.4.3a — Integration Framework complete

External systems use the shared `SirisConnector` contract and `SirisIntegrationManager` for lifecycle, health, scheduler-backed refresh, typed events, and non-secret configuration. External integration startup is asynchronous and must never block authentication or the core dashboard. ADR 012 documents the framework.

### 0.4.3b — Docker Connector complete

Docker runs through the Integration Framework with live container state, CPU/RAM, logs/actions, host metrics/history, alerts, audit history, image update availability, snapshot-based state-change events, and server-side registry checks. ADR 013 documents the connector architecture.

### 0.4.3c — Notification Policies complete

SirisCore has deterministic duration/threshold rules, escalation, stable-ID deduplication, resolution, Mission Control wake hooks, Briefing integration, and explainable Siris Score penalties. ADR 014 documents the policy engine.

### 0.4.3d — Home Assistant Connector complete

Home Assistant is the second production integration running through the shared framework:

- Home Assistant URL/token remain in backend environment configuration and never reach Flutter
- Backend state snapshot and allow-listed service-action endpoints
- Server-side WebSocket connection to Home Assistant `/api/websocket`
- Authenticates with the configured access token and subscribes specifically to `state_changed`
- Live entity cache updates immediately from Home Assistant events
- REST `/api/states` remains the initial-state and reconnect fallback path
- Five-second Siris connector refreshes read the local cache rather than repeatedly querying Home Assistant
- Deterministic Home Assistant state changes publish Homelab events through SirisCore
- Home Assistant unavailability policy: warning after 2 minutes, critical after 10 minutes
- Multiple unavailable/unknown entities policy: warning after 2 minutes
- Authenticated `/home-assistant` entity browser with live cached state
- Entity search and domain filtering
- Allow-listed actions for lights, switches, input booleans, and covers
- Arbitrary Home Assistant service execution is rejected server-side

ADR 015 documents the connector foundation and ADR 016 documents live state streaming and the entity-control boundary.

### Next: 0.4.3e — Broader infrastructure integrations

Next work expands Live Homelab with Prometheus/Grafana and then additional integrations such as UniFi, Proxmox, NAS, backups, and UPS. The same Integration Framework remains the foundation for the later Obsidian/Selkies Knowledge Platform.

## Current application capabilities

- Responsive Flutter web application with persisted authentication
- FastAPI backend, PostgreSQL, and Docker Compose deployment
- Restricted Docker socket proxy
- Running logging and trends
- Gym workouts, templates, progress, and personal records
- Health Auto Export MCP integration scaffold
- Live Docker monitoring and container actions
- Docker image update availability and notification policies
- Home Assistant WebSocket state stream, entity browser, and safe controls
- Host metrics, history, alerts, audit history, and logs
- Plex and Ollama diagnostics
- Reusable Siris Integration Framework for external systems
- Global search
- Configurable workspace and dedicated adaptive `/mission` Situation Room
- Mission Control display profiles, Focus Modes, ambient display, critical wake, diagnostics, and shared design system

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
8. Prefer shared Siris design components over new parallel card/status/metric implementations.
9. New external-system integrations should implement the Integration Framework rather than inventing bespoke lifecycle/polling code.
10. Integration alert behaviour should use Notification Policies rather than emitting repeated notifications directly from connector refresh loops.
11. External integration startup and enrichment must never block authentication or core dashboard rendering.
12. External credentials remain server-side; Flutter consumes authenticated SirisOS APIs rather than third-party secrets.

## Local endpoints

- Web UI: `http://192.168.0.100:6464`
- Mission Control: `http://192.168.0.100:6464/#/mission`
- Home Assistant browser: `http://192.168.0.100:6464/#/home-assistant`
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
