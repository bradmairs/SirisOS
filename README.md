# SirisOS

SirisOS is a self-hosted personal operating system spanning personal health/fitness, homelab operations, civil engineering tools, knowledge, automation and AI assistance.

Its product rule is simple:

1. Help you know something important.
2. Help you decide what to do next.
3. Help you act without leaving SirisOS.

This README is the authoritative project handover. `docs/roadmap.md` is the implementation checklist. **Update both whenever scope or sprint status changes.**

## Standard deployment workflow

```bash
git pull
make up
```

`make up` creates missing local data/config directories, rebuilds the Docker images and starts the stack. Finished slices should keep `main` deployable through this workflow.

## Current architecture

SirisOS is built around reusable platform layers rather than isolated dashboards:

```text
Modules / Widgets
      ↓
Event Bus
      ↓
Notification Policies / Context
      ↓
History Engine
      ↓
Incident Engine
      ↓
Digital Twin
      ↓
Capability Framework
      ↓
Future Planner / Actions / Playbooks
      ↓
SirisAI / Hermes / Ollama
```

Mission Control answers **“what is happening right now?”**. Operations Center answers **“what needs my attention?”**.

## Completed platform foundations

### Sprint 0.4.1 — SirisCore ✅

- Typed Event Bus
- Module Registry
- Widget Registry
- Notification Centre
- Deterministic Briefing Engine
- Explainable Siris Score foundation
- SirisCore Scheduler
- AI Context Service
- Persisted core settings

### Sprint 0.4.2 — Mission Control ✅

Authenticated `/mission` Situation Room with live clock/date, briefing, Siris Score, shared widget grid, activity timeline, adaptive priority, critical wake, profiles, focus modes, ambient mode, reduced motion and diagnostics.

### Sprint 0.4.3 — Live Homelab ✅ platform foundation

The Integration Framework now supports Docker, Home Assistant, Prometheus, Grafana, UniFi, host storage, Synology DSM/Hyper Backup and NUT UPS monitoring. External credentials remain backend-side.

Operational platform services added during 0.4.3:

- Deterministic Notification Policies
- `/operations` Operations Center
- Generic PostgreSQL time-series/history engine
- 30-day Hyper Backup protection analytics
- Deterministic Incident Engine
- Configurable Digital Twin dependency graph
- Capability Framework with fail-closed control semantics

Important architecture ADRs: 012–030.

### Sprint 0.4.4 — SirisCore Context Service ✅ foundation

SirisOS now maintains a deterministic current context with typed facts, priorities and provenance. Initial operational contexts include power events, backup attention, network/storage/compute degradation and nominal homelab state.

The service publishes `ContextSnapshotChanged` through the Event Bus, keeps a bounded transition timeline, and appears in Mission Control and Operations Center. Personal states such as sleeping, working or travelling are not guessed; they remain deferred until authoritative Health Data Export, Home Assistant presence, calendar or project providers exist. ADR 031.

## Sprint 0.4.5 — Engineering Module 🚧 in progress

Engineering is now a first-class SirisOS module.

### Deterministic calculator foundation

Current tools:

- Full circular-pipe Manning capacity and velocity
- Rational Method peak flow using mm/h and hectares
- Buried-pipe buoyancy screening
- Constant-flow detention storage screening

The calculation core is pure Dart and regression-tested. Inputs/units/assumptions remain explicit. Screening helpers do **not** claim standards compliance or replace project-specific design checks. ADR 032.

### Private Standards Library / Search

The Engineering module now has a **Calculators / Standards** hub.

SirisOS can store and search standards PDFs that the administrator is entitled to use:

- Authenticated PDF upload from the Flutter web UI
- Raw PDFs persisted privately under `data/standards`
- Default per-file limit of 100 MB, configurable with `SIRISOS_STANDARDS_MAX_UPLOAD_MB`
- Metadata for title, authority/publisher, reference and edition/revision
- Page-level local text extraction using `pypdf`
- Private full-text search with short snippets and page provenance
- Scanned/image-only PDFs are accepted but marked **Stored · not indexed** rather than rejected
- Authoritative source shortcuts for Standards Australia, WSAA, Sydney Water, Austroads and Australian Rainfall & Runoff
- SirisOS does not scrape or redistribute protected standards content

The library is designed as the future retrieval base for **SirisHydro**. Future AI answers should cite the exact local document/reference/edition/page wherever possible; Ollama may explain retrieved material but does not become the authority. ADR 033.

Planned Engineering follow-ons:

- OCR for scanned standards
- Better lexical ranking and multi-page hits
- Semantic/vector indexing
- Document replacement/version management
- Traceable authority/assumption profiles for calculators
- Citation-first SirisHydro retrieval
- SirisPM integration
- Project notes and drawing review
- Civil 3D utilities
- Engineering Context provider

## Planned Health Data Export REST ingestion

The earlier MCP scaffold remains optional, but canonical Apple Health ingestion is planned to move to a dedicated REST endpoint from Health Data Export.

Planned flow:

```text
Apple Health
   ↓
Health Data Export
   ↓ HTTPS POST
SirisOS Health Ingest API
   ↓
Canonical Health Store / History
   ↓
Health module / Context / Briefing / Siris Score / SirisAI
```

Initial metrics will target steps, sleep, HRV, resting heart rate and workouts with idempotent imports and an unattended bearer token.

## Sprint 0.5.0 — Knowledge Platform

Planned Obsidian/Selkies integration:

- Launch integration
- Obsidian connector
- Vault browser
- Recent Notes / Daily Notes widgets
- Global vault search
- Wikilink navigation and graph exploration
- Metadata/tags
- Semantic search
- Mission Control Knowledge widget
- Context-aware related notes
- Cross-links into Engineering, Homelab, Tasks, Calendar and Briefings

## Sprint 0.6 — Projects and Context Graph

Planned general project model plus relationships between notes, tasks, files, calculations, events, repositories and conversations. This is also where the richer Siris Knowledge Graph can grow above the Digital Twin.

## Sprint 0.7 — SirisAI, Intelligence and Automation

SirisAI deliberately separates orchestration, agent execution and inference.

### SirisAI

Owns identity, context assembly, policy, approvals, audit, routing and UI.

### Hermes Agent

Planned optional server-side tool-using runtime for diagnostics and controlled administration. Initial integration will be read-only, later expanding to allow-listed least-privilege actions. High-impact operations require explicit approval and audit. SirisOS will never enable Hermes dangerous-command approval bypass modes.

### Ollama

Reusable local inference layer for SirisHydro, SirisPM, briefings, semantic search and deterministic-output rewriting. Hermes may use Ollama as a model backend, but other SirisAI features do not depend on Hermes.

ADR 029 records this boundary.

Planned automation stack:

- Operations Planner
- Action Framework bound to stable capability IDs
- Playbook Engine
- Context-aware recommendations
- n8n integration
- Event-driven Siris Automations
- Shared approval/audit policy

## Long-term pillars

- **Personal OS:** health, sleep, recovery, running, gym, calendar
- **HomeLab OS:** Docker, Home Assistant, Prometheus/Grafana, UniFi, Synology, backups, UPS, Plex
- **Engineer OS:** SirisHydro, SirisPM, calculators, standards, projects, Civil 3D
- **Knowledge OS:** Obsidian, documents, search, metadata, semantic memory
- **Intelligence OS:** Context, Knowledge Graph, Planner, SirisAI, Hermes, Ollama
- **Automation OS:** capabilities, actions, playbooks, schedules, triggers, workflows, approvals

## Development rules / handover checklist

1. Read this README and `docs/roadmap.md` before continuing development.
2. Inspect the latest commits on `main`.
3. Follow the documented sprint order unless the user explicitly sidesteps it.
4. Keep completed slices deployable through `git pull && make up`.
5. Update README and roadmap together whenever scope/status changes.
6. Record significant architecture decisions under `docs/adr/`.
7. Prefer reusable SirisCore services over feature-specific plumbing.
8. External integrations use the Integration Framework.
9. Integration alert logic uses Notification Policies.
10. External integration startup must never block login/core dashboard rendering.
11. Credentials stay server-side; Flutter consumes authenticated SirisOS APIs.
12. UI widgets must not start new network requests from `build()`.
13. Mission Control is ambient status; Operations Center is focused operational work.
14. Low-frequency operational observations use the generic History Engine; high-frequency telemetry remains Prometheus territory.
15. Historical analytics must use actually observed events/samples, not polling-frequency assumptions.
16. Incident correlation must expose its evidence and must not be presented as causal without dependency evidence.
17. Digital Twin downstream claims require explicit built-in or user-declared dependencies.
18. Context claims require provider-backed provenance.
19. Planners/playbooks/agents target stable capability IDs rather than connector-specific implementations.
20. Control capabilities fail closed when providers are unhealthy.
21. SirisAI keeps Hermes execution separate from Ollama inference; SirisOS owns approvals/policy/audit.
22. Server-control AI actions must be allow-listed/least-privilege where practical, auditable, and must not use approval bypasses.
23. Engineering calculations expose units/assumptions and must not claim authority compliance without traceable profiles.
24. Licensed standards remain private local content; never scrape or redistribute protected standards content.
25. SirisHydro retrieval should cite exact document/reference/edition/page wherever possible.

## Local endpoints

- Web UI: `http://192.168.0.100:6464`
- Mission Control: `http://192.168.0.100:6464/#/mission`
- Operations Center: `http://192.168.0.100:6464/#/operations`
- API: `http://192.168.0.100:8000`
- API docs: `http://192.168.0.100:8000/docs`
- History API: `http://192.168.0.100:8000/api/v1/history`
- Backup Protection API: `http://192.168.0.100:8000/api/v1/history/backup-protection`
- Engineering Standards API: `http://192.168.0.100:8000/api/v1/engineering/standards`

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

Runtime state is stored under `data/`. Back up `data/` and `.env` to preserve the installation, including uploaded private engineering standards.
