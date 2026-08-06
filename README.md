# SirisOS

SirisOS is a self-hosted personal operating system that brings together homelab monitoring, health and fitness, productivity, civil engineering tools, personal knowledge, automation, media services, and AI assistance.

The long-term goal is not simply to build another dashboard. SirisOS should help the user:

1. Know something important.
2. Decide what to do next.
3. Act without leaving SirisOS.

This README is the authoritative project handover and roadmap. A new developer or future AI development session should read this document before making architectural or roadmap decisions.

## Product direction

SirisOS is evolving into a modular software platform built around **SirisCore** and a dedicated **Mission Control** experience.

Modules should not communicate directly with one another. Instead, they register their capabilities and publish typed events through a central event bus. Reusable widgets, notifications, briefings, automation, and AI context should consume those common systems.

The target experience is closer to a personal command centre than a traditional collection of application pages.

## Stack

- Flutter frontend
- Nginx web server
- FastAPI backend
- PostgreSQL
- Docker Compose
- Restricted Docker socket proxy
- SharedPreferences for local UI layout preferences
- Ollama integration planned

## Standard deployment workflow

Completed development work should be merged into `main` and remain deployable with only:

```bash
git pull
make up
```

`make up` creates `.env` from `.env.example` when required, creates persistent data directories, rebuilds the affected Docker images, and starts the complete SirisOS stack.

Normal updates should not require manually running Flutter, changing branches, invoking backend commands separately, or applying ad-hoc setup steps. Any unavoidable migration or configuration change must be documented clearly in the relevant commit, pull request, and this README.

## Current capabilities

The repository currently includes:

- Responsive Flutter web application
- Authentication and persisted sessions
- Mission Control-style configurable dashboard workspace
- Persistent widget ordering, visibility, and sizing
- Mission Control widget metadata registry
- SirisOS module registry with declared capabilities
- Typed SirisCore broadcast event bus
- Running logging and fitness trends
- Gym workout logging, templates, exercise progress, and personal records
- Health Auto Export MCP integration scaffold
- Persistent cross-module activity and notifications
- Notification severity and read/unread state
- Live Docker container monitoring
- Host CPU, memory, disk, network, uptime, and history metrics
- Docker container start, stop, restart, and logs
- Homelab alerts and audit history
- Read-only Home Assistant, Plex, and Ollama diagnostics
- Dashboard recommendations and trend sparklines
- Global search
- FastAPI APIs backed by PostgreSQL
- Docker-served web UI on port `6464`

## Development philosophy

Every feature should satisfy at least one of these goals:

1. Help the user know something important.
2. Help the user decide what to do next.
3. Help the user act without leaving SirisOS.

Additional implementation principles:

- Build shared platform systems before isolated features.
- Prefer module registration over hardcoded navigation and capability checks.
- Prefer typed events over direct module-to-module calls.
- Keep deterministic logic underneath AI-generated wording.
- Keep integrations read-only until control behaviour is deliberate, secure, and auditable.
- Preserve the one-command deployment workflow.
- Deliver small, reviewable development slices and merge completed work into `main`.
- Avoid duplicating widgets or business logic between Dashboard and Mission Control.

# Authoritative development roadmap

## Sprint 0.4.1 — SirisCore

This is the current development priority. Sprint 0.4.1 must be completed before substantial work continues on the dedicated Mission Control display.

### 1. Event Bus

Introduce a central typed event system so modules no longer communicate directly.

Example flow:

```text
Run Logged
    │
    ▼
Event Bus
    ├── Dashboard refresh
    ├── Mission Control refresh
    ├── Statistics update
    ├── Notification
    ├── Briefing update
    └── AI context refresh
```

This foundation should support Running, Gym, Health, Homelab, Home Assistant, Docker, Engineering, notifications, briefings, and future automation.

Current progress:

- [x] Typed broadcast event bus foundation
- [x] Mission Control refresh events
- [x] Generic module data-change events
- [x] Notification state-change events
- [x] Running publishes events after logging a run
- [x] Gym publishes workout and template events
- [x] Activity service publishes unread/read state changes
- [ ] Health data-change publishers
- [ ] Homelab and Docker data-change publishers
- [ ] Dashboard and Mission Control subscriptions
- [ ] Statistics update subscriptions
- [ ] Notification generation subscriptions
- [ ] Briefing update subscriptions
- [ ] AI context refresh subscriptions

### 2. Module Registry

Each module should register its identity and capabilities rather than relying on hardcoded shell logic.

Conceptual structure:

```dart
class RunningModule extends SirisModule {
  @override
  String get id => 'running';

  @override
  String get title => 'Running';

  @override
  IconData get icon => Icons.directions_run;
}
```

The application shell should discover registered modules and build navigation, search targets, quick actions, and capability checks from the registry.

Current progress:

- [x] Central module registry
- [x] Module IDs, labels, descriptions, icons, and capability declarations
- [x] Homelab, Running, Gym, Health, and Siris definitions
- [ ] Registry-provided routes and screen builders
- [ ] Registry-driven desktop navigation rail
- [ ] Registry-driven mobile navigation
- [ ] Registry-driven quick actions
- [ ] Optional and unavailable module handling

### 3. Widget Registry

Dashboard cards should become reusable registered widgets instead of separate hardcoded implementations.

Conceptual structure:

```dart
SirisWidget(
  id: 'running.summary',
  title: 'Running',
  builder: ...,
)
```

Dashboard and Mission Control should consume the same registered widget implementations.

Current progress:

- [x] Mission Control widget metadata registry
- [x] Widget labels, descriptions, icons, and default sizes
- [x] Persistent widget visibility, ordering, and sizing
- [x] Existing briefing, Homelab, Running, Gym, Server, and Activity panels use the layout registry
- [ ] Namespaced widget IDs such as `running.summary`
- [ ] Reusable widget builders in registry definitions
- [ ] Module-owned widget registration
- [ ] Shared consumption by Dashboard and dedicated Mission Control
- [ ] Direct drag-and-drop and resize interactions on the workspace

### 4. Notification Centre

Build a proper event-driven notification service with:

- Severity: Info, Success, Warning, Critical
- Module source
- Timestamp
- Optional action button and target
- Persistent read/unread state
- Event Bus subscriptions

Eventually, every module should publish relevant notifications through SirisCore.

Current progress:

- [x] Persistent activity event storage
- [x] Info, Success, Warning, and Critical severity model
- [x] Module source and timestamp
- [x] Notification screen and filters
- [x] Persistent read/unread state
- [x] Unread badge and mark-all-read action
- [x] Notification state events
- [ ] Notification Centre live Event Bus subscriptions
- [ ] Automatic refresh when module events occur
- [ ] Optional action metadata and action buttons
- [ ] Consistent notification policies for each module
- [ ] Health and Homelab notification publishers

### 5. Briefing Engine

Each module should contribute deterministic observations such as:

- “Recovery is above 85%.”
- “Docker updates are available.”
- “No run has been logged in four days.”

The engine should rank, deduplicate, and assemble observations into a coherent briefing. Ollama may later rewrite the result naturally, but the underlying logic must remain deterministic and reliable.

Current progress:

- [x] Existing dashboard briefing strings and rules-based recommendations
- [ ] Standard briefing observation model
- [ ] Module briefing contributor interface
- [ ] Running observations
- [ ] Gym observations
- [ ] Health and recovery observations
- [ ] Homelab observations
- [ ] Priority and relevance scoring
- [ ] Deduplication and expiry
- [ ] Deterministic briefing assembly
- [ ] Event-driven briefing refresh
- [ ] Optional Ollama rewrite layer

### Remaining SirisCore platform systems

- [ ] Scheduler
- [ ] AI context service
- [ ] Theme and settings service consolidation

## Sprint 0.4.2 — Mission Control

After SirisCore is complete, build a dedicated full-screen Mission Control route intended for a second monitor or wall display.

Planned route:

```text
/mission
```

Planned features:

- Full-screen layout
- No navigation chrome
- Large live clock
- Live Siris Score
- Deterministic briefing panel
- Reusable widget grid
- Activity timeline
- Automatic refresh
- Smooth transitions and animations
- Persistent layouts
- Ambient display modes
- Responsive desktop and wall-display behaviour

Current progress completed early:

- [x] Configurable workspace foundation
- [x] Widget ordering, visibility, and sizing
- [x] Persistent layout preferences
- [x] Responsive card layout
- [ ] Dedicated `/mission` route
- [ ] Navigation-free display shell
- [ ] Large clock
- [ ] Siris Score
- [ ] Live event-driven widget refresh
- [ ] Activity timeline integration
- [ ] Ambient modes

## Sprint 0.4.3 — Live Homelab

Turn SirisOS into a lightweight homelab control centre using the Docker Engine API and additional integrations.

Planned capabilities:

- Live container list
- CPU and RAM usage
- Health status
- Start, stop, and restart actions
- Container logs
- Update availability
- Event publication and notifications

Longer-term integrations:

- Prometheus
- Grafana
- Home Assistant
- UniFi
- Plex
- Additional self-hosted services

Current progress:

- [x] Live Docker container list
- [x] CPU and memory metrics
- [x] Container state and health status
- [x] Start, stop, and restart actions
- [x] Container logs
- [x] Host metrics and history
- [x] Homelab alerts
- [x] Action audit history
- [x] Home Assistant, Plex, and Ollama diagnostics
- [ ] Container image update availability
- [ ] Homelab Event Bus publishers
- [ ] Event-driven Homelab notifications
- [ ] Prometheus and Grafana integration
- [ ] Expanded Home Assistant integration
- [ ] UniFi integration

## Sprint 0.4.4 — Engineering Module

Civil engineering should be a first-class SirisOS module rather than an afterthought.

Initial planned tools:

- Manning’s equation calculator
- Pipe capacity calculator
- Rational Method calculator
- Pipe buoyancy checker
- Detention basin sizing helper
- Standards search scaffold

Initial standards and knowledge areas may include:

- WSAA
- Sydney Water
- Austroads
- Australian Standards
- NSW and Victorian authority requirements

Longer-term capabilities:

- SirisHydro integration
- SirisPM integration
- Standards knowledge library
- Project notes and tools
- AI-assisted drawing review
- Civil 3D utilities

Current progress:

- [ ] Engineering module scaffold
- [ ] Hydraulic calculators
- [ ] Standards search scaffold
- [ ] SirisHydro integration
- [ ] SirisPM integration

# Later roadmap

## AI and knowledge

- Ollama integration
- Command palette with `Ctrl/Cmd + K`
- Personal knowledge search
- AI context service
- AI-generated daily briefing built on deterministic observations
- Integration diagnostics UI
- Module-aware Siris assistant

## Personal modules

- Tasks and calendar
- Morning briefing delivery
- Health trends and recovery
- Running plans and statistics
- Gym programming and progression
- Media and entertainment integrations
- Personal automations

# UI direction

Continue evolving the application toward:

- Premium dark theme
- Red and black accents
- Glass-style cards
- Responsive desktop layout
- Animated sparklines
- Widget-based dashboard
- Dedicated Mission Control mode
- Command palette
- Notification drawer or centre
- Smooth but restrained animations
- Clear warning and critical states

The interface should feel cohesive, calm, and operational rather than like a collection of unrelated dashboards.

# Required sequencing

Unless deliberately revised and documented, development should proceed in this order:

1. Finish module data-change event publishers.
2. Add live Notification Centre subscriptions.
3. Make application navigation genuinely Module Registry-driven.
4. Complete the reusable Widget Registry.
5. Build the deterministic Briefing Engine.
6. Complete the remaining SirisCore systems.
7. Declare Sprint 0.4.1 complete.
8. Build the dedicated Mission Control route and display mode.
9. Finish Live Homelab capabilities.
10. Begin the Engineering module.

Do not continue adding isolated standalone screens when the same work should be implemented as a shared SirisCore service, registered module, or reusable widget.

# Run SirisOS

Install Docker with Docker Compose v2 and GNU Make, then run from the repository root:

```bash
cp .env.example .env
make up
```

Open SirisOS from any device on the LAN:

```text
http://192.168.0.100:6464
```

API and interactive documentation:

```text
http://192.168.0.100:8000
http://192.168.0.100:8000/docs
```

The Flutter web app is compiled inside Docker and served by Nginx. Flutter does not need to remain running on the server.

## Configuration

The browser-facing API address is compiled into the Flutter web build using `SIRISOS_API_URL` from `.env`:

```env
SIRISOS_API_URL=http://192.168.0.100:8000
```

After changing this value, rebuild the web image:

```bash
make rebuild-web
```

## Development with hot reload

For active Flutter development, install Flutter with web support and run:

```bash
make dev
```

This starts the backend services and launches Flutter's development web server at:

```text
http://192.168.0.100:6464
```

## Useful commands

```bash
make up          # Build and start the complete SirisOS stack
make dev         # Start Flutter Web with hot reload
make backend     # Start backend services only
make rebuild-web # Rebuild only the Docker-served Flutter UI
make status      # Show containers and health checks
make logs        # Follow all service logs
make restart     # Rebuild and restart the complete stack
make stop        # Stop all services
make clean       # Stop services and clean Flutter build output
```

## Persistent data

Runtime data is stored inside the repository directory:

```text
data/
├── postgres/
├── logs/
├── backups/
└── uploads/
```

Back up the `data` directory and `.env` file to preserve the installation.

## Docker access

The API does not mount the host Docker socket directly. A dedicated socket proxy exposes only the Docker endpoints required by SirisOS. The proxy still mounts `/var/run/docker.sock` because that socket belongs to the host operating system and cannot be stored inside the repository.

Control endpoints must remain limited, authenticated, and auditable.

# Development handover checklist

Before continuing development in a new chat or environment:

1. Read this README in full.
2. Inspect the latest commits on `main`.
3. Review `docs/roadmap.md` for any additional progress notes.
4. Confirm the current branch is based on the latest `main`.
5. Follow the required sequencing above.
6. Preserve `git pull` followed by `make up` as the standard user workflow.
7. Merge finished, coherent development slices into `main`.
8. Update this README whenever roadmap scope, sequencing, or implementation status materially changes.
