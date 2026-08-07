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

The authenticated `/mission` Situation Room provides a navigation-free full-screen shell, live clock/date, shared Widget Registry grid, Siris Score, deterministic briefing, activity timeline, event-driven refresh, adaptive priority, critical wake, display profiles, Focus Modes, ambient mode, reduced-motion behaviour, diagnostics, and the shared red/black SirisOS design system.

## Active milestone — Sprint 0.4.3 Live Homelab

### 0.4.3a — Integration Framework complete

External systems use the reusable `SirisConnector` contract, shared connector health states, `SirisIntegrationManager`, Scheduler-backed refreshes, typed integration events, failure recovery, and server-side credential boundaries. ADR 012 documents the framework.

### 0.4.3b — Docker Connector complete

Docker runs through the Integration Framework with container state, CPU/RAM, health, logs, actions, host metrics/history, image-update availability, action audit history, meaningful state-change events, and non-fatal registry diagnostics. ADR 013 records the design.

### 0.4.3c — Notification Policies complete

SirisCore has deterministic duration-based policy activation, escalation, stable-ID deduplication, explicit resolution, Mission Control wake integration, Briefing output, and explainable Siris Score penalties. Docker and later connectors consume the same policy engine. ADR 014 documents the contract.

### 0.4.3d — Home Assistant Connector complete

Home Assistant runs through `SirisIntegrationManager`. Its token remains server-side; the backend maintains live entity state through `/api/websocket` `state_changed` events with REST fallback. SirisOS provides an authenticated entity browser, search/domain filters, and allow-listed controls for lights, switches, input booleans, and covers. ADRs 015–016 document the architecture.

### 0.4.3e — Broader infrastructure integrations in progress

Prometheus is now the first broader observability integration:

- Optional `PrometheusConnector`; an empty `PROMETHEUS_URL` cleanly disables it
- Backend-only Prometheus endpoint configuration
- Authenticated target-health snapshot derived from the standard `up` metric
- Authenticated instant PromQL query endpoint for future SirisOS observability features
- Fifteen-second backend cache to prevent duplicate requests from widgets/connectors
- Fifteen-second Siris connector refreshes with meaningful Homelab events
- Notification Policies for Prometheus unavailability and scrape targets remaining down
- Registered `homelab.prometheus` Mission Control widget using shared Siris design primitives
- Prometheus diagnostics included in the existing integration status endpoint
- Architecture documented in ADR 017

Next in 0.4.3e is **Grafana dashboard discovery/launch and panel rendering where practical**, followed by UniFi, Proxmox, NAS/backups, and UPS.

The same Integration Framework remains the foundation for the later Obsidian/Selkies Knowledge Platform.

## Current application capabilities

- Responsive Flutter web application with persisted authentication
- FastAPI backend, PostgreSQL, and Docker Compose deployment
- Restricted Docker socket proxy
- Running logging and trends
- Gym workouts, templates, progress, and personal records
- Health Auto Export MCP integration scaffold
- Live Docker monitoring, actions, updates, alerts, audit history, and host metrics
- Home Assistant WebSocket live state, entity browser, safe controls, and policies
- Optional Prometheus target monitoring, PromQL queries, policies, and Mission Control widget
- Plex and Ollama diagnostics
- Reusable Siris Integration Framework for external systems
- Deterministic Notification Policy engine
- Global search
- Configurable workspace and dedicated adaptive `/mission` Situation Room
- Mission Control profiles, Focus Modes, ambient display, critical wake, diagnostics, and shared design system

## Long-term pillars

- **Personal:** Health, recovery, running, gym, sleep, and nutrition
- **Infrastructure:** Docker, Home Assistant, Prometheus/Grafana, UniFi, Proxmox, NAS, backups, UPS, Plex
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
