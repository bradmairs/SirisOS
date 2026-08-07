# SirisOS

SirisOS is a self-hosted personal operating system that unifies personal health and fitness, homelab infrastructure, engineering tools, knowledge, automation, and AI assistance.

Its purpose is to help the user:

1. Know something important.
2. Decide what to do next.
3. Act without leaving SirisOS.

This README is the authoritative project handover. `docs/roadmap.md` is the implementation checklist. Update both whenever scope or status changes.

## Product architecture

SirisOS is a modular platform built around **SirisCore** and the **Mission Control** experience. Core principles are one source of truth, event-driven updates, deterministic/explainable intelligence, context over raw data, reusable platform services, server-side external credentials, and a deployable `main` branch.

## Standard deployment workflow

```bash
git pull
make up
```

`make up` creates missing local configuration/data directories, rebuilds the Docker images, and starts the stack.

## Sprint 0.4.1 — SirisCore complete

Typed Event Bus, Module/Widget Registries, deterministic Briefing Engine and Siris Score, Scheduler, AI Context Service, persisted settings, and event-driven Notification Centre. ADRs under `docs/adr/` record significant decisions.

## Sprint 0.4.2 — Mission Control complete

The authenticated `/mission` Situation Room provides the navigation-free full-screen shell, shared Widget Registry grid, Siris Score, briefing, activity timeline, event-driven refresh, adaptive priority, critical wake, profiles, Focus Modes, ambient mode, reduced-motion behaviour, diagnostics, and shared red/black SirisOS design system.

## Active milestone — Sprint 0.4.3 Live Homelab

### 0.4.3a — Integration Framework complete

External systems use `SirisConnector`, shared health states, `SirisIntegrationManager`, Scheduler-backed refresh, typed events, failure recovery, disabled/unconfigured state, and server-side credential boundaries. ADR 012.

### 0.4.3b — Docker Connector complete

Docker monitoring/actions, host metrics/history, logs, image-update availability, audit history, meaningful state events, and non-fatal registry diagnostics run through the Integration Framework. ADR 013.

### 0.4.3c — Notification Policies complete

Deterministic duration-based activation, escalation, stable-ID deduplication, explicit resolution, Mission Control wake, Briefing output, and Siris Score penalties. ADR 014.

### 0.4.3d — Home Assistant Connector complete

Server-side HA credentials, live `/api/websocket` `state_changed` cache with REST fallback, authenticated entity browser, search/domain filters, safe allow-listed controls, and HA policies. ADRs 015–016.

### 0.4.3e — Broader infrastructure integrations in progress

Prometheus, Grafana and UniFi are complete through the Integration Framework with server-side credentials, deterministic policies and Mission Control widgets. ADRs 017–019 document those integrations.

Storage/NAS work now targets the actual homelab platform: **Synology DSM**. Proxmox has been removed from the roadmap because it is not required for this installation.

Current storage/NAS slice:

- Vendor-neutral host filesystem monitoring through the existing node-exporter
- `homelab.storage` Mission Control widget with volume count, used/free capacity and peak utilisation
- Warning policy above 85% filesystem utilisation and critical policy above 95%
- Optional `SynologyConnector` through the Integration Framework
- DSM URL, username and password remain backend-side
- Runtime DSM WebAPI discovery and authenticated session lifecycle
- DSM model/version discovery
- Synology disk and volume discovery/status where exposed by the running DSM version
- Unhealthy disk/volume Notification Policy
- Synology availability policy
- `homelab.synology` Mission Control widget
- Detection of installed Synology backup APIs to prepare Hyper Backup monitoring

Next in 0.4.3e is **Synology Hyper Backup task/history integration**, then **UPS monitoring**.

The same Integration Framework remains the foundation for the later Obsidian/Selkies Knowledge Platform.

## Current application capabilities

- Responsive Flutter web application with persisted authentication
- FastAPI backend, PostgreSQL, Docker Compose, restricted Docker socket proxy
- Running logging/trends and Gym workouts/templates/progress/PRs
- Health Auto Export MCP scaffold
- Docker monitoring/actions/updates/alerts/audit/host metrics
- Home Assistant live state/browser/safe controls/policies
- Prometheus monitoring/PromQL/policies/widget
- Grafana health/dashboard discovery/launch/render proxy support
- UniFi controller/device/AP/client/WAN overview and policies
- Host storage capacity monitoring and Synology DSM NAS monitoring
- Plex and Ollama diagnostics
- Reusable Integration Framework and deterministic Notification Policy engine
- Global search and configurable workspace
- Adaptive `/mission` Situation Room with profiles, Focus Modes, ambient display, critical wake and diagnostics

## Long-term pillars

- **Personal:** Health, recovery, running, gym, sleep, nutrition
- **Infrastructure:** Docker, Home Assistant, Prometheus/Grafana, UniFi, Synology NAS, backups, UPS, Plex
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
7. Prefer reusable SirisCore services and shared design components.
8. New external integrations implement the Integration Framework.
9. Integration alert behaviour uses Notification Policies.
10. External integration startup/enrichment must never block authentication or core dashboard rendering.
11. External credentials remain server-side; Flutter consumes authenticated SirisOS APIs.

## Local endpoints

- Web UI: `http://192.168.0.100:6464`
- Mission Control: `http://192.168.0.100:6464/#/mission`
- Home Assistant browser: `http://192.168.0.100:6464/#/home-assistant`
- Grafana browser: `http://192.168.0.100:6464/#/grafana`
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
