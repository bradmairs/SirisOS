# SirisOS

SirisOS is a self-hosted personal operating system that unifies personal health and fitness, homelab infrastructure, engineering tools, knowledge, automation, and AI assistance.

Its purpose is to help the user:

1. Know something important.
2. Decide what to do next.
3. Act without leaving SirisOS.

This README is the authoritative project handover. `docs/roadmap.md` is the implementation checklist. Update both whenever scope or status changes.

## Product architecture

SirisOS is a modular platform built around **SirisCore**, **Mission Control**, and the emerging **Operations Center**. Core principles are one source of truth, event-driven updates, deterministic/explainable intelligence, context over raw data, reusable platform services, server-side external credentials, and a deployable `main` branch.

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

## Sprint 0.4.3 — Live Homelab

### 0.4.3a — Integration Framework complete

External systems use `SirisConnector`, shared health states, `SirisIntegrationManager`, Scheduler-backed refresh, typed events, failure recovery, disabled/unconfigured state, and server-side credential boundaries. ADR 012.

### 0.4.3b — Docker Connector complete

Docker monitoring/actions, host metrics/history, logs, image-update availability, audit history, meaningful state events, and non-fatal registry diagnostics run through the Integration Framework. ADR 013.

### 0.4.3c — Notification Policies complete

Deterministic duration-based activation, escalation, stable-ID deduplication, explicit resolution, Mission Control wake, Briefing output, and Siris Score penalties. ADR 014.

### 0.4.3d — Home Assistant Connector complete

Server-side HA credentials, live `/api/websocket` `state_changed` cache with REST fallback, authenticated entity browser, search/domain filters, safe allow-listed controls, and HA policies. ADRs 015–016.

### 0.4.3e — Broader infrastructure integrations complete

Prometheus, Grafana and UniFi are complete through the Integration Framework with server-side credentials, deterministic policies and Mission Control widgets. ADRs 017–019 document those integrations.

Storage/NAS work targets **Synology DSM**; Proxmox is intentionally not part of this installation.

Current Synology/storage capabilities:

- Vendor-neutral host filesystem monitoring through the existing node-exporter
- `homelab.storage` Mission Control widget with volume count, used/free capacity and peak utilisation
- Warning policy above 85% filesystem utilisation and critical policy above 95%
- Optional `SynologyConnector` through the Integration Framework
- DSM URL, username and password remain backend-side
- Runtime DSM WebAPI discovery and authenticated session lifecycle
- DSM model/version, disk and volume discovery/status
- Synology availability and unhealthy-storage Notification Policies
- `homelab.synology` Mission Control widget
- Runtime discovery of `SYNO.Backup.Task`
- Hyper Backup task list/status monitoring with task name, state, last result, last finish time, next-run time and destination when DSM exposes those fields
- Critical Notification Policy when one or more Hyper Backup tasks last report a failure
- Hyper Backup state changes publish standard Homelab events
- Dedicated `homelab.backups` Mission Control widget showing task/running/failed counts and recent task states
- Hyper Backup monitoring architecture documented in ADR 021

Hyper Backup fields are parsed defensively because DSM package/API versions differ. Unsupported optional task fields degrade to unavailable values rather than breaking Synology monitoring.

UPS monitoring uses **Network UPS Tools (NUT)** as the vendor-neutral interface:

- Optional `UpsConnector`; blank `NUT_HOST` disables the integration quietly
- Backend speaks the NUT text protocol; the browser never connects directly to the UPS/NUT server
- Auto-discovers the first UPS, or uses `NUT_UPS_NAME` when configured
- Monitors line/on-battery state, low-battery state, battery charge, estimated runtime, UPS load and input/output voltage when exposed by the UPS driver
- 15-second connector refresh
- Immediate warning policy when utility power is lost and the UPS is on battery
- Immediate critical policy when NUT reports low battery
- Availability policy escalates when the NUT server remains unreachable
- Registered `homelab.ups` Mission Control widget
- Architecture documented in ADR 022

### 0.4.3f — Operations Center foundation complete

The authenticated `/operations` route provides the first operational-management layer above Mission Control.

It currently provides:

- Operational overview counts for attention items, critical issues and healthy integrations
- Correlated active incidents from the deterministic Incident Engine
- Live connector status sourced from `SirisIntegrationManager`
- Prioritised "What needs attention" work queue retaining raw policy evidence
- Manual integration refresh without adding a second polling system
- Event-driven updates for policy and integration health changes
- Desktop sidebar and Quick Actions access
- Architecture documented in ADR 023

Mission Control remains the ambient "what is happening now?" surface. Operations Center is the focused "what needs my attention?" surface.

### 0.4.3g — Generic Time-Series / History Engine foundation complete

SirisOS now has a connector-neutral persistent history layer for low-frequency operational observations:

- One PostgreSQL `time_series_observations` store using source, metric and canonical dimensions
- Numeric values and short text/status values
- Central minimum sampling intervals and 90-day default retention
- Authenticated bounded `GET /api/v1/history` query endpoint
- Shared Flutter `HistoryService` and `TimeSeriesObservation` model
- Storage peak utilisation and per-volume history
- Synology volume utilisation history
- Hyper Backup failed/running task-state history
- UPS battery charge, estimated runtime, load, voltage and power-state history
- Background persistence so history writes do not delay connector responses
- In-memory sample guards to avoid unnecessary PostgreSQL reads between due samples
- Architecture documented in ADR 024

This engine is intentionally for low-frequency SirisOS operational history. Prometheus remains the high-frequency metrics system. Existing dedicated host/Docker history will be bridged into the generic contract in a later slice rather than replaced speculatively.

### 0.4.3h — Backup protection analytics complete

SirisOS now turns observed Hyper Backup completions into deterministic protection analytics rather than estimating success from polling state.

- Each distinct Hyper Backup completion is stored once as `synology_backup/completion`
- Repeated DSM polling is deduplicated through change-based persistence
- Completion records retain finish timestamp, reported result and destination context
- Authenticated `/api/v1/history/backup-protection` endpoint calculates rolling 1–90 day summaries
- Default Operations Center view uses a 30-day window
- Overall completion, success, failure and success-rate metrics
- Per-task completion/success/failure/success-rate metrics
- Last completion and last failure timestamps retained in the summary model
- Cached and repaint-isolated Backup Protection panel in Operations Center
- Architecture documented in ADR 025

The analytics only claim runs SirisOS has actually observed. A newly deployed installation starts building trustworthy history from the latest completion DSM exposes and future completions; it does not invent older backup runs. Schedule-aware overdue detection and duration analytics remain follow-on work until those data are reliable.

### 0.4.3i — Incident Engine foundation complete

Operations Center now correlates related Notification Policy outcomes into deterministic incidents instead of treating every alert as an independent incident.

- Stable `SirisIncident` model and `IncidentEngine`
- UPS on-battery or low-battery conditions anchor a power-outage incident
- Concurrent Docker, Synology, Home Assistant, UniFi, Prometheus and Grafana failures attach as possible impacts
- Remaining outcomes group into compute, storage/backup, network, observability and Home Assistant incidents
- Unmatched policies remain visible as standalone incidents
- Each incident exposes severity, start time, source policy count, affected integrations and an explicit correlation reason
- Raw source policy outcomes remain visible in the Operations Center attention queue
- Unit coverage protects power correlation, subsystem grouping and standalone fallback
- Architecture documented in ADR 026

The Incident Engine is intentionally deterministic and explainable. Correlation is not treated as proof of causation.

### 0.4.3j — Digital Twin dependency graph and configurable topology complete

SirisOS now has a deterministic dependency graph that is separate from incident correlation:

- Typed dependency nodes and directed `dependent -> dependency` relationships
- Transitive downstream traversal with cycle/duplicate protection
- Built-in software dependency chain `Synology -> Hyper Backup -> Backup Protection Analytics`
- Incident Engine attaches graph-derived downstream impacts separately from correlated affected integrations
- Operations Center labels graph evidence as `Declared downstream`
- Editable Digital Twin topology panel in Operations Center
- Custom relationships persist through the existing Flutter local settings store
- Built-in relationships remain immutable while custom edges can be removed/reset
- Self-dependencies, duplicates and cycles are rejected before persistence
- Topology edits immediately update deterministic incident downstream impact
- Architecture documented in ADRs 027–028

Only relationships SirisOS can explicitly justify or the user explicitly declares belong in the graph. Physical relationships such as `Docker -> UPS` or `UniFi -> UPS` are never inferred merely because systems fail together. This first editable slice only links existing graph nodes and stores custom topology per browser/profile; server-side topology, arbitrary custom components, authoritative discovery and interactive graph visualization remain follow-on work.

## Planned SirisAI architecture — Hermes Agent + Ollama

SirisOS will deliberately use **Hermes Agent and Ollama for different jobs** rather than choosing one as the entire AI stack.

- **SirisAI** is the SirisOS orchestration and safety layer: identity, context, policy, approvals, audit, routing, UI and action governance.
- **Hermes Agent** will be an optional server-side tool-using agent runtime for controlled server administration, diagnostics, file/configuration work and other operational tasks.
- **Ollama** will remain the reusable local inference layer for SirisHydro, SirisPM, briefings, semantic search, deterministic-output rewriting and other domain assistants. Hermes may also use Ollama as one of its own model backends.

The planned Hermes integration will not expose unrestricted agent execution directly to the browser. High-impact actions must be brokered through SirisOS, use explicit approval/confirmation where appropriate, and be audited. SirisOS will not enable Hermes dangerous-command approval bypass modes. Initial Hermes capabilities should begin read-only, then expand to allow-listed server actions with least-privilege execution. Operations Center incidents and Digital Twin dependency context will eventually feed agent tasks so Hermes can act with SirisOS context rather than as a disconnected shell agent.

This separation means SirisHydro and other local AI features do not depend on Hermes being available, while SirisOS can still gain a powerful server-control agent later. The design is recorded in ADR 029 and scheduled under Sprint 0.7.

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
- Synology Hyper Backup task/result monitoring and Mission Control backup status
- 30-day Hyper Backup protection analytics in Operations Center
- NUT UPS monitoring for power state, battery, runtime and load
- Generic persistent operational time-series history API/client
- Deterministic Incident Engine with explainable cross-system correlation
- Configurable Digital Twin dependency graph with declared downstream impact analysis
- Reusable Integration Framework and deterministic Notification Policy engine
- Global search and configurable workspace
- Adaptive `/mission` Situation Room with profiles, Focus Modes, ambient display, critical wake and diagnostics
- `/operations` Operations Center with correlated incidents, editable topology, declared downstream impact, integration health, operational attention queue and backup protection history
- Web performance protections including cached integration widget futures and isolated widget repaint regions

## Long-term pillars

- **Personal:** Health, recovery, running, gym, sleep, nutrition
- **Infrastructure:** Docker, Home Assistant, Prometheus/Grafana, UniFi, Synology NAS, backups, UPS, Plex
- **Engineering:** SirisHydro, SirisPM, calculators, standards, Civil 3D, project tools
- **Knowledge:** Obsidian, documents, notes, search, semantic memory
- **Intelligence:** SirisAI orchestration, Ollama local inference, Hermes Agent server runtime, briefings, Siris Score, recommendations, context
- **Automation:** n8n, schedules, triggers, scripts, workflows, notifications, approval/audit policies

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
12. UI widgets must not initiate fresh network requests from `build()`; cache futures/state at widget or connector level.
13. Mission Control is ambient status; Operations Center is focused operational work.
14. Low-frequency historical observations use the generic History Engine; high-frequency telemetry belongs in Prometheus.
15. Historical analytics must be derived from observed events/samples, never inferred from polling frequency when the source data cannot support that claim.
16. Incident correlation must remain deterministic and expose its source evidence/reason; correlation must not be presented as proven causation without dependency evidence.
17. Digital Twin dependency claims must come from built-in explicit relationships or user-declared topology; never infer physical power/network dependencies solely from simultaneous failures.
18. Custom Digital Twin topology must remain cycle-safe and clearly distinguish built-in from user-declared relationships.
19. SirisAI must keep agent execution separate from inference: Hermes handles optional tool-using execution, Ollama provides reusable local inference, and SirisOS owns approvals, policy and audit.
20. Server-control AI actions must be least-privilege, allow-listed where possible, auditable, and must not use approval-bypass modes.

## Local endpoints

- Web UI: `http://192.168.0.100:6464`
- Mission Control: `http://192.168.0.100:6464/#/mission`
- Operations Center: `http://192.168.0.100:6464/#/operations`
- Home Assistant browser: `http://192.168.0.100:6464/#/home-assistant`
- Grafana browser: `http://192.168.0.100:6464/#/grafana`
- API: `http://192.168.0.100:8000`
- API docs: `http://192.168.0.100:8000/docs`
- Generic history API: `http://192.168.0.100:8000/api/v1/history`
- Backup protection API: `http://192.168.0.100:8000/api/v1/history/backup-protection`

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
