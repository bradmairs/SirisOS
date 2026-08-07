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

The authenticated `/mission` Situation Room now provides:

- Navigation-free full-screen Mission Control
- Large live clock and date
- Shared Widget Registry grid
- Siris Score, deterministic briefing, activity timeline, and module summaries
- Event-driven refresh plus scheduled fallback
- Adaptive widget prioritisation and temporary enlargement
- Critical-event wake behaviour
- Persisted Balanced, Operations, and Compact display profiles
- Runtime event and refresh diagnostics
- Persisted All, Work, Home, Fitness, and Travel Focus Modes
- Ambient mode after inactivity with automatic event wake
- Reduced-motion and burn-in-conscious display behaviour
- Shared SirisOS design-system primitives
- Premium black/red visual language and semantic status colours

Mission Control presentation remains a transient view over shared SirisCore data and user-owned layout settings. Adaptive priority, profiles, focus, ambient mode, and critical wake do not overwrite the saved workspace.

### SirisOS design system

Shared Flutter primitives now live in `widgets/siris_design_system.dart`:

- `SirisCard`
- `SirisPanel`
- `SirisMetric`
- `SirisStatusChip`
- `SirisGauge`
- `SirisTimeline`

The global theme owns the premium dark red/black visual language, typography, navigation, forms, actions, and semantic status tokens. Mission Control summary cards are the first existing widgets migrated to these primitives. New UI should prefer the shared components, while specialised legacy widgets can migrate incrementally when touched.

Architecture is documented in ADRs 007–011.

## Active milestone — Sprint 0.4.3 Live Homelab

### 0.4.3a — Integration Framework complete

SirisOS has a reusable integration layer for external systems rather than treating Docker, Home Assistant, Obsidian, UniFi, and future services as unrelated one-off implementations.

Core pieces:

- `SirisConnector` contract for connector identity, lifecycle, refresh interval, and refresh logic
- Shared connector states: disconnected, connecting, healthy, degraded, failed, and disabled
- `SirisIntegrationManager` for registration, connect/refresh/disconnect lifecycle, health tracking, and scheduled refresh
- Scheduler-backed connector refresh jobs with existing overlap protection
- Typed `IntegrationHealthChanged` and `IntegrationRefreshed` events on the Siris Event Bus
- Deterministic degraded/failed transitions after repeated failures
- Non-secret connector configuration with endpoint/options and opaque credential references
- Credential values deliberately excluded from Flutter client persistence

This framework is documented in ADR 012 and is now the intended foundation for Docker, Home Assistant, Obsidian/Selkies, UniFi, Proxmox, NAS, and other external integrations.

### 0.4.3b — Docker Connector complete

Docker is the first production integration running through the framework:

- Authenticated `DockerConnector` lifecycle owned by `SirisIntegrationManager`
- Scheduled 30-second connector refreshes
- Snapshot comparison publishes Homelab events only when meaningful state changes occur
- Existing container actions, logs, CPU/RAM, health, host metrics, history, alerts, and audit history are preserved
- Registry digest checks identify newer container images
- Update checks are deduplicated per image within each Docker collection
- Available image updates are exposed through the Homelab summary model and existing Homelab alert pipeline
- Registry/update-check failures remain non-fatal and are retained as per-container diagnostics

The first implementation intentionally uses authenticated snapshot comparison rather than a direct Docker daemon event stream. This works with the existing restricted Docker proxy and keeps SirisCore decoupled from Docker-specific transport details. ADR 013 records the decision.

### 0.4.3c — Notification Policies complete

SirisCore now has a deterministic policy engine for integration conditions:

- Stable-ID rules with module ownership, title/message, severity, activation duration, optional escalation duration, and score penalty
- Conditions activate only after their configured duration
- Repeated connector refreshes are deduplicated rather than generating duplicate alerts
- Escalation changes the existing active outcome instead of creating a second notification
- Clearing a condition explicitly resolves the policy
- Policy transitions publish typed events plus existing notification/module events, reusing Mission Control wake and refresh behaviour
- Active policy messages are surfaced in the Mission Control briefing
- Active policy penalties feed the deterministic Siris Score with explainable wording
- Docker initially contributes unhealthy, stopped-container, and image-update policies
- Unit coverage verifies duration activation, escalation deduplication, and resolution

Notification policy architecture is documented in ADR 014. Active policy state is currently in-memory; persisted history and user-editable policy configuration remain later enhancements.

### 0.4.3d — Home Assistant Connector foundation

Home Assistant is now the second integration running through the shared framework:

- `HomeAssistantConnector` lifecycle owned by `SirisIntegrationManager`
- Home Assistant URL/token remain in backend environment configuration and never reach Flutter
- Authenticated backend state snapshot endpoint
- Authenticated backend service-action endpoint
- Scheduled 30-second connector refreshes
- Deterministic snapshot comparison publishes Homelab events only when entity/state availability changes
- Home Assistant unavailability policy: warning after 2 minutes, critical after 10 minutes
- Multiple unavailable/unknown entities policy: warning after 2 minutes
- Connector startup remains asynchronous so Home Assistant can never block login or the dashboard

This first slice deliberately uses bounded REST snapshots through the SirisOS backend. Direct Home Assistant WebSocket streaming and a dedicated entity browser/richer entity controls remain follow-on work; the SirisCore connector/event contract does not depend on transport choice.

### Next: finish 0.4.3d and continue 0.4.3e

Next work:

- Add direct Home Assistant WebSocket event subscription where practical
- Add a dedicated Home Assistant entity browser and richer safe controls
- Then expand Live Homelab with Prometheus/Grafana, UniFi, Proxmox, NAS, backups, and UPS

The same Integration Framework remains the foundation for the later Obsidian/Selkies Knowledge Platform.

## Current application capabilities

- Responsive Flutter web application with persisted authentication
- FastAPI backend, PostgreSQL, and Docker Compose deployment
- Restricted Docker socket proxy
- Running logging and trends
- Gym workouts, templates, progress, and personal records
- Health Auto Export MCP integration scaffold
- Live Docker monitoring and container actions
- Docker connector lifecycle, scheduled state-change detection, and image update availability
- Home Assistant connector lifecycle, state snapshots, state-change events, and safe backend service actions
- Deterministic duration/escalation Notification Policy engine
- Host metrics, history, alerts, audit history, and logs
- Home Assistant, Plex, and Ollama diagnostics
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
