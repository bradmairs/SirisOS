# SirisOS Roadmap

## Sprint 0.4.1 — SirisCore ✅ Complete

- [x] Typed Event Bus and module data-change publishers
- [x] Event-driven Notification Centre
- [x] Event-driven Mission Control/dashboard refresh with debounce
- [x] Central Module Registry
- [x] Reusable Widget Registry
- [x] Deterministic Briefing Engine and Siris Score
- [x] SirisCore Scheduler
- [x] Canonical AI Context Service
- [x] Consolidated persisted SirisCore settings
- [x] README, roadmap, ADRs, and `git pull && make up` workflow

## Sprint 0.4.2 — Mission Control ✅ Complete

- [x] Navigation-free `/mission` Situation Room
- [x] Live clock/date, shared widget grid, Siris Score, briefing, timeline
- [x] Event-driven refresh and scheduled fallback
- [x] Adaptive widget priority and critical wake
- [x] Balanced, Operations, Compact profiles
- [x] All, Work, Home, Fitness, Travel Focus Modes
- [x] Ambient and reduced-motion behaviour
- [x] Runtime diagnostics
- [x] Shared Siris design system and premium red/black theme

## Sprint 0.4.3 — Live Homelab

### 0.4.3a — Integration Framework ✅ Complete

- [x] `SirisConnector` contract
- [x] Shared connector health model
- [x] `SirisIntegrationManager`
- [x] Scheduler-backed refresh with overlap protection
- [x] Typed integration events and deterministic failure recovery
- [x] Disabled/unconfigured connector state
- [x] Server-side credential boundary
- [x] ADR 012

### 0.4.3b — Docker Connector ✅ Complete

- [x] Containers, CPU/RAM, health, logs and actions
- [x] Host metrics/history and audit history
- [x] Docker connector lifecycle
- [x] Meaningful state-change events
- [x] Image update availability and non-fatal registry diagnostics
- [x] ADR 013

### 0.4.3c — Notification Policies ✅ Complete

- [x] Duration-based activation and escalation
- [x] Stable-ID deduplication
- [x] Explicit resolution
- [x] Typed policy events
- [x] Mission Control wake, Briefing and Siris Score integration
- [x] Docker policies and unit coverage
- [x] ADR 014

### 0.4.3d — Home Assistant Connector ✅ Complete

- [x] Server-side HA credentials
- [x] HA connector lifecycle and policies
- [x] Live WebSocket `state_changed` subscription
- [x] REST fallback and server-side entity cache
- [x] Authenticated entity browser/search/filter UI
- [x] Allow-listed light/switch/input-boolean/cover controls
- [x] ADRs 015–016

### 0.4.3e — Broader infrastructure integrations ✅ Complete

Prometheus:
- [x] Optional Prometheus connector
- [x] Authenticated target-health endpoint and instant PromQL
- [x] Backend cache and scheduler refresh
- [x] Availability/down-target policies
- [x] `homelab.prometheus` Mission Control widget
- [x] ADR 017

Grafana:
- [x] Optional Grafana connector
- [x] Server-side service-account credentials
- [x] Health/version and dashboard discovery
- [x] Grafana 12+ discovery with legacy fallback
- [x] Authenticated `/grafana` browser and external launch
- [x] Availability policy and Mission Control widget
- [x] Optional bounded PNG panel proxy
- [x] ADR 018

UniFi:
- [x] Optional UniFi connector through the Integration Framework
- [x] Server-side UniFi URL/API key and optional site selector
- [x] Official local UniFi Network API integration
- [x] UniFi OS and direct local Network API root compatibility
- [x] Controller reachability and site discovery
- [x] Adopted device online/offline summary
- [x] Access-point and connected-client overview
- [x] WAN interface discovery
- [x] Backend cache and connector refresh
- [x] Controller-unavailable and device-offline Notification Policies
- [x] Registered `homelab.unifi` Mission Control widget
- [x] ADR 019

Storage and Synology NAS:
- [x] Vendor-neutral host filesystem capacity snapshot from node-exporter
- [x] `homelab.storage` Mission Control widget
- [x] 85% warning and 95% critical host-storage policies
- [x] Optional Synology DSM connector through the Integration Framework
- [x] DSM credentials retained server-side
- [x] Runtime DSM WebAPI discovery and authenticated session lifecycle
- [x] DSM model/version discovery
- [x] Synology disk and volume discovery/status with DSM-version fallback handling
- [x] Synology availability and unhealthy-storage Notification Policies
- [x] Registered `homelab.synology` Mission Control widget
- [x] Detect installed Synology backup APIs
- [x] Hyper Backup task list/status monitoring through `SYNO.Backup.Task`
- [x] Task name/state plus last result, finish time, next-run time and destination when exposed by DSM
- [x] Hyper Backup failure Notification Policy
- [x] Backup state changes publish standard Homelab events
- [x] Registered `homelab.backups` Mission Control widget
- [x] Hyper Backup architecture documented in ADR 021

UPS / power:
- [x] Vendor-neutral Network UPS Tools (NUT) backend client
- [x] Optional `NUT_HOST`, port and UPS selector; blank host disables quietly
- [x] Auto-discover first UPS when no explicit UPS name is configured
- [x] Read line/battery state, battery charge, estimated runtime, load and voltages when available
- [x] `UpsConnector` through the Integration Framework with 15-second refresh
- [x] Immediate on-battery warning policy
- [x] Immediate low-battery critical policy
- [x] NUT availability escalation policy
- [x] Standard Homelab events on meaningful UPS state changes
- [x] Registered `homelab.ups` Mission Control widget
- [x] ADR 022

### 0.4.3f — Operations Center foundation ✅ Complete

- [x] Authenticated `/operations` route
- [x] Operational overview counts
- [x] Active incident presentation
- [x] Live connector health from `SirisIntegrationManager`
- [x] Prioritised operational attention queue
- [x] Event-driven refresh on policy/integration changes
- [x] Manual Integration Manager refresh action
- [x] Desktop sidebar and Quick Actions access
- [x] No independent polling/backend aggregation layer
- [x] ADR 023

### 0.4.3g — Generic Time-Series / History Engine ✅ Foundation complete

- [x] Generic PostgreSQL `time_series_observations` store
- [x] Source + metric + canonical-dimensions series identity
- [x] Numeric and short text observations
- [x] Central minimum-sample interval and 90-day default retention
- [x] Authenticated bounded `GET /api/v1/history` query API
- [x] Shared Flutter `HistoryService` and observation model
- [x] Host storage peak/volume utilisation producers
- [x] Synology volume utilisation producers
- [x] Hyper Backup failed/running task state producers
- [x] UPS battery charge/runtime/load/voltage/power-state producers
- [x] ADR 024
- [ ] Migrate/bridge existing dedicated host/Docker history into the generic history contract
- [ ] Add UniFi client/outage history producers
- [x] Add first Operations Center historical context through backup protection analytics

### 0.4.3h — Backup protection analytics ✅ Complete

- [x] Persist one discrete `synology_backup/completion` event per observed Hyper Backup completion
- [x] Deduplicate repeated DSM polling using change-based history persistence
- [x] Preserve completion finish timestamp, result and destination context
- [x] Deterministic rolling backup summary for 1–90 day windows
- [x] 30-day overall completion, success, failure and success-rate analytics
- [x] Per-task completion/success/failure/success-rate analytics
- [x] Last completion and last failure timestamps
- [x] Authenticated `GET /api/v1/history/backup-protection` endpoint
- [x] Shared Flutter backup protection model/client
- [x] Cached/repaint-isolated Backup Protection panel in Operations Center
- [x] ADR 025
- [ ] Schedule-aware overdue/staleness policy once DSM schedule semantics are reliable
- [ ] Backup duration analytics when reliable per-run duration data is available

### 0.4.3i — Incident Engine ✅ Foundation complete

- [x] Deterministic `IncidentEngine` over active Notification Policy outcomes and Integration Manager health
- [x] Stable incident IDs and severity ordering
- [x] UPS on-battery/low-battery policies anchor a correlated power-outage incident
- [x] Concurrent Docker, Synology, Home Assistant, UniFi, Prometheus and Grafana failures attach as possible power-event impacts
- [x] Subsystem grouping for compute, storage/backup, network, observability and Home Assistant conditions
- [x] Unmatched policy outcomes remain visible as standalone incidents
- [x] Correlation reason and affected integrations shown in Operations Center
- [x] Raw policy evidence remains visible in the attention queue
- [x] Unit coverage for power correlation, category grouping and standalone fallback
- [x] ADR 026
- [ ] Persist incident lifecycle/history through the History Engine
- [ ] Add incident acknowledgement/assignment/resolution workflow

### 0.4.3j — Digital Twin / Dependency Graph ✅ Configurable foundation complete

- [x] Deterministic dependency node/edge model
- [x] Directed `dependent -> dependency` semantics
- [x] Transitive downstream impact traversal
- [x] Cycle/duplicate protection across multiple dependency roots
- [x] Initial explicit `Synology -> Hyper Backup -> Backup Protection Analytics` chain
- [x] Incident Engine enrichment with graph-derived downstream impacts
- [x] Operations Center separates `Declared downstream` from correlated affected integrations
- [x] Editable dependency/topology configuration in Operations Center
- [x] Persist custom edges through versioned Flutter local settings
- [x] Keep built-in edges immutable and removable/resettable custom edges separate
- [x] Reject self-dependencies, duplicate edges and topology cycles
- [x] Recompute incident downstream impact immediately after topology edits
- [x] Unit coverage for transitive impact, explicit UPS mapping and cycle rejection
- [x] ADRs 027–028
- [ ] Move topology persistence server-side when multiple-client/discovered topology requires one canonical graph
- [ ] Arbitrary custom component/node creation
- [ ] Dynamic dependency discovery where authoritative APIs expose it
- [ ] Interactive Digital Twin graph visualization
- [ ] Dependency-aware recommended actions

### 0.4.3k — Capability Framework ✅ Foundation complete

- [x] Declarative `SirisCapability` model with stable capability IDs
- [x] Capability kind, provider, risk and confirmation metadata
- [x] `SirisCapabilityRegistry` independent from execution/action implementations
- [x] Live capability availability derived from `SirisIntegrationManager` health
- [x] Fail-closed control semantics when providers are degraded
- [x] Read-only capabilities may remain available during degraded provider state
- [x] Initial Docker, Home Assistant, Synology, UniFi, Prometheus, Grafana, storage and UPS capabilities
- [x] Operations Center capability availability panel
- [x] Unit coverage for healthy/degraded/disabled availability rules
- [x] ADR 030
- [ ] Provider-owned dynamic capability registration
- [ ] Capability argument schemas and authorization requirements
- [ ] Server-side capability endpoint for Hermes/external automation
- [ ] Bind executable capabilities to the future Action Framework

Proxmox is intentionally not part of the SirisOS roadmap because this installation does not use it. All broader integrations remain optional; blank configuration reports disabled and creates no alert noise. Credentials remain server-side. Hyper Backup monitoring uses runtime API discovery and degrades gracefully when optional task fields are unavailable. The same Integration Framework is the foundation for the later Obsidian/Selkies Knowledge connector.

### Homelab / Operations follow-on backlog

- [ ] Operations Planner and deterministic recommended operational actions
- [ ] Action Framework bound to stable capability IDs
- [ ] Playbook Engine composed from registered actions
- [ ] Safe UPS power-event automation and graceful shutdown orchestration
- [ ] Explainable Siris Score contribution history
- [ ] Further Flutter web performance work: isolate Mission Control clock state and throttle pointer-hover activity

## Sprint 0.4.4 — SirisCore Context Service ✅ Foundation complete

- [x] Typed `SirisContextFact` model with stable IDs, domains, priorities, sources and details
- [x] `SirisContextProvider` interface for modular context contribution
- [x] Deterministic prioritized `SirisContextSnapshot` with primary context
- [x] Event-driven refresh on integration-health and Notification Policy changes
- [x] `ContextSnapshotChanged` Event Bus publishing
- [x] Bounded in-memory context transition timeline
- [x] Non-blocking provider failure isolation
- [x] Initial evidence-based operational provider for power events, backup attention and degraded network/storage/compute state
- [x] Nominal homelab fallback when no elevated context is active
- [x] Registered `siris.context` Mission Control widget
- [x] Current Context surface in Operations Center
- [x] Unit coverage for priority resolution and enter/clear transitions
- [x] ADR 031
- [ ] Persist context timeline through the generic History Engine
- [ ] Manual context override with expiry/provenance
- [ ] Health Data Export context provider
- [ ] Home Assistant presence provider
- [ ] Calendar/work/project providers
- [ ] Context-aware Briefing Engine and Siris Score
- [ ] Authenticated context API for backend/Hermes consumers
- [ ] Presence Engine layered on top of context providers

Personal, engineering and AI context states remain evidence-based: SirisOS will not claim states such as working, sleeping, travelling or focused until authoritative providers exist.

## Sprint 0.4.5 — Engineering Module

- [ ] Engineering module scaffold
- [ ] Manning equation calculator
- [ ] Pipe capacity calculator
- [ ] Rational Method calculator
- [ ] Pipe buoyancy checker
- [ ] Detention basin sizing helper
- [ ] Standards search scaffold for WSAA, Sydney Water, Austroads, Australian Standards, and authorities
- [ ] SirisHydro and SirisPM integration
- [ ] Project notes, drawing review, and Civil 3D utilities

## Sprint 0.5.0 — Knowledge Platform

- [ ] Obsidian/Selkies launch integration
- [ ] Obsidian connector through the Integration Framework
- [ ] Vault browser
- [ ] Recent notes and Daily Notes widgets
- [ ] Global SirisOS search across vault content
- [ ] Wikilink navigation and graph exploration
- [ ] Metadata and tags
- [ ] AI semantic search
- [ ] Mission Control Knowledge widget
- [ ] Context-aware related notes
- [ ] Cross-linking with Engineering, Homelab, Tasks, Calendar, and Briefings

## Sprint 0.6 — Projects and Context Graph

- [ ] General project model
- [ ] Relationships between notes, tasks, files, calculations, events, repositories, and conversations
- [ ] Context containers for engineering, homelab, travel, fitness, and personal projects

## Sprint 0.7 — SirisAI, Intelligence and Automation

SirisAI will deliberately separate **inference**, **agent execution**, and **SirisOS policy/orchestration** rather than treating one runtime as the whole AI stack.

Ollama / local inference:
- [ ] Ollama connector/provider with server-side configuration
- [ ] Shared local model routing for SirisHydro, SirisPM, briefings, semantic search and deterministic-output rewriting
- [ ] Per-module model/profile selection and context budgets
- [ ] Health/model-availability monitoring through the Integration Framework
- [ ] Preserve deterministic SirisCore outputs underneath optional LLM rewriting

Hermes Agent / server agent runtime:
- [ ] Optional Hermes Agent connector/runtime adapter
- [ ] Integrate Hermes into SirisAI as the tool-using agent runtime for server administration
- [ ] Keep Hermes endpoint/authentication server-side
- [ ] Allow Hermes to use Ollama as one model backend without making Hermes mandatory for other SirisAI features
- [ ] SirisAI action broker with allow-listed server operations
- [ ] Explicit confirmation/approval flow for destructive or high-impact actions
- [ ] Never enable Hermes dangerous-command approval bypass from SirisOS
- [ ] Audit trail for prompts, approvals, invoked actions/commands and results
- [ ] Feed Operations Center incidents and Digital Twin dependency context into agent tasks
- [ ] Safe read-only diagnostics before write/action capabilities
- [ ] Controlled Docker/service/file-management actions with least-privilege execution
- [ ] Agent task/status/history surface in Operations Center

Broader intelligence and automation:
- [ ] Recommendation engine
- [ ] Semantic context and memory
- [ ] n8n workflow integration
- [ ] Automation schedules, triggers, and action audit
- [ ] Dependency-aware recommended operational actions
- [ ] Human approval policies shared by Hermes actions and other SirisOS automations
- [ ] ADR 029 architecture boundary: SirisAI orchestration vs Hermes runtime vs Ollama inference

## Sprint 0.8 — Plugin SDK

- [ ] External module contract
- [ ] Plugin routes, widgets, notifications, briefing contributors, search providers, actions, and AI context providers
- [ ] Versioned public APIs and compatibility policy

## Sprint 1.0 — Personal Operating System

Stable daily platform across Mission Control, Operations Center, Personal, Infrastructure, Engineering, Knowledge, Intelligence, and Automation.
