# SirisOS Roadmap

## Sprint 0.4.1 — SirisCore ✅ Complete

Released foundation:

- [x] Typed Event Bus and module data-change publishers
- [x] Event-driven Notification Centre
- [x] Event-driven Mission Control/dashboard refresh with debounce
- [x] Central Module Registry with module-owned routes, screens, quick actions, and availability states
- [x] Reusable Widget Registry with namespaced IDs, module ownership, builders, and saved-layout migration
- [x] Deterministic Briefing Engine with Running, Gym, Health, Homelab, and system contributors
- [x] Deterministic Siris Score with weighted domains and human-readable explanations
- [x] Registered `siris.score` widget
- [x] SirisCore Scheduler with guarded periodic jobs
- [x] Canonical AI Context Service derived from shared dashboard state
- [x] Consolidated persisted SirisCore settings for refresh and module availability
- [x] README, roadmap, ADRs, and standard `git pull && make up` deployment workflow

Deferred enhancements remain on the later backlog: notification action buttons, direct drag-and-drop, optional Ollama wording, and score domains whose modules do not yet exist.

## Sprint 0.4.2 — Mission Control ✅ Complete

Build the dedicated `/mission` Situation Room using SirisCore services.

### 0.4.2a — Situation Room foundation ✅ Complete

- [x] Navigation-free full-screen shell
- [x] Large live clock and date
- [x] Shared Widget Registry grid
- [x] Siris Score presentation and explanation
- [x] Deterministic briefing panel
- [x] Activity timeline
- [x] Event-driven debounced auto-refresh
- [x] Scheduled refresh fallback
- [x] Responsive second-monitor foundation
- [x] Smooth layout transitions
- [x] In-app Mission Control launcher
- [x] Persisted display controls

### 0.4.2b — Adaptive runtime ✅ Complete

- [x] Adaptive widget priority based on deterministic module severity
- [x] Automatic temporary enlargement of widgets needing attention
- [x] Preserve the saved layout while applying transient priorities
- [x] User control to disable adaptive mode
- [x] Critical-event wake behaviour with temporary visual escalation
- [x] Persisted Balanced, Operations, and Compact display profiles
- [x] Event count, latest event, and refresh latency diagnostics
- [x] Diagnostics surfaced in the header and display controls

### 0.4.2c — Focus and ambient modes ✅ Complete

- [x] Persisted Focus Modes: All, Work, Home, Fitness, and Travel
- [x] Focus policies select relevant registered widgets without mutating saved layout
- [x] Ambient display mode after 30 seconds of inactivity
- [x] Ambient mode enlarges the clock, reduces chrome, and limits lower-priority widgets
- [x] Module and notification events wake the interface from ambient mode
- [x] Critical events override ambient mode and trigger critical wake presentation
- [x] Persisted reduced-motion setting removes non-essential Mission Control transitions
- [x] Ambient mode hides clock seconds and reduces continuously changing content
- [x] Second-monitor and wall-display behaviour refined through profiles, focus, and ambient presentation

### 0.4.2d — Design system and polish ✅ Complete

- [x] Shared SirisCard, SirisMetric, SirisPanel, SirisTimeline, SirisGauge, and SirisStatusChip components
- [x] Premium red/black visual refinement
- [x] Central semantic tokens for info, success, warning, and critical states
- [x] Consistent typography, navigation, form, action, surface, and warning-state styling
- [x] Mission Control summary cards migrated to shared Siris design primitives
- [x] Design-system architecture documented in ADR 011

Existing specialised widgets may migrate incrementally as they are touched; new UI should use the shared design primitives rather than introducing parallel card/status/metric systems.

## Sprint 0.4.3 — Live Homelab

### 0.4.3a — Integration Framework ✅ Complete

- [x] Reusable `SirisConnector` contract
- [x] Shared connector health/state model
- [x] Central `SirisIntegrationManager`
- [x] Connector lifecycle: register, connect, refresh, disconnect, unregister
- [x] Scheduler-backed per-connector refresh intervals with overlap protection inherited from SirisScheduler
- [x] Typed integration health and refresh events on the Siris Event Bus
- [x] Deterministic degraded/failed health transitions after repeated refresh failures
- [x] Non-secret connector configuration contract with opaque credential references
- [x] Credential values explicitly excluded from Flutter client persistence
- [x] Integration Framework architecture documented in ADR 012

### 0.4.3b — Docker Connector ✅ Complete

- [x] Existing live containers, CPU/RAM, state, health, logs, and actions
- [x] Host metrics and history
- [x] Alerts and action audit history
- [x] Docker migrated behind the `SirisConnector` contract
- [x] Authenticated connector lifecycle managed by `SirisIntegrationManager`
- [x] Scheduler-backed Docker refreshes
- [x] Meaningful Docker state changes publish Homelab events through SirisCore
- [x] Container image update availability via registry digest comparison
- [x] Update checks deduplicated per image within each collection
- [x] Image updates surfaced through Homelab alert policy and Docker summary model
- [x] Update-check failures are non-fatal and preserved as per-container diagnostics
- [x] Docker connector architecture documented in ADR 013

A direct Docker daemon event-stream subscription remains an optional later optimisation; the current connector uses deterministic snapshot comparison so it works through the existing authenticated API and restricted Docker proxy.

### 0.4.3c — Notification Policies

- [ ] Reusable integration notification policy model
- [ ] Duration/threshold-based policies (for example unhealthy for five minutes)
- [ ] Severity escalation and deduplication
- [ ] Mission Control wake integration
- [ ] Briefing and Siris Score policy hooks

### 0.4.3d — Home Assistant Connector

- [x] Existing Home Assistant diagnostics
- [ ] Migrate Home Assistant behind the SirisConnector contract
- [ ] WebSocket/event subscription support
- [ ] Expanded Home Assistant entities, states, and actions

### 0.4.3e — Broader infrastructure integrations

- [x] Existing Plex and Ollama diagnostics
- [ ] Prometheus and Grafana integrations
- [ ] UniFi, Proxmox, NAS, backup, and UPS integrations

The Integration Framework is also the intended foundation for the later Obsidian/Selkies Knowledge connector and other external systems.

## Sprint 0.4.4 — Engineering Module

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

Integrate the server-hosted Obsidian instance running through Selkies as the Knowledge pillar.

- [ ] Obsidian/Selkies launch integration
- [ ] Obsidian connector implemented through the Integration Framework
- [ ] Vault browser
- [ ] Recent notes and Daily Notes widgets
- [ ] Global SirisOS search across vault content
- [ ] Wikilink navigation and graph exploration
- [ ] Metadata and tag support
- [ ] AI semantic search
- [ ] Mission Control Knowledge widget
- [ ] Context-aware related notes
- [ ] Cross-linking with Engineering, Homelab, Tasks, Calendar, and Briefings

## Sprint 0.6 — Projects and Context Graph

- [ ] General project model
- [ ] Relationships between notes, tasks, files, calculations, events, repositories, and conversations
- [ ] Context containers for engineering, homelab, travel, fitness, and personal projects

## Sprint 0.7 — Intelligence and Automation

- [ ] Ollama-backed rewriting over deterministic outputs
- [ ] Recommendation engine
- [ ] Semantic context and memory
- [ ] n8n workflow integration
- [ ] Automation schedules, triggers, and action audit

## Sprint 0.8 — Plugin SDK

- [ ] External module contract
- [ ] Plugin routes, widgets, notifications, briefing contributors, search providers, actions, and AI context providers
- [ ] Versioned public APIs and compatibility policy

## Sprint 1.0 — Personal Operating System

Stable daily platform across Mission Control, Personal, Infrastructure, Engineering, Knowledge, Intelligence, and Automation.
