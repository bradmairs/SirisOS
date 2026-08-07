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

## Sprint 0.4.2 — Mission Control

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

### 0.4.2d — Design system and polish

- [ ] Shared SirisCard, SirisMetric, SirisPanel, SirisTimeline, SirisGauge, and SirisStatusChip components
- [ ] Premium red/black visual refinement
- [ ] Consistent typography, spacing, animations, and warning states
- [ ] Consolidate Mission Control controls into shared Siris design components

## Sprint 0.4.3 — Live Homelab

- [x] Live containers, CPU/RAM, state, health, logs, and actions
- [x] Host metrics and history
- [x] Alerts and action audit history
- [x] Home Assistant, Plex, and Ollama diagnostics
- [ ] Container image update availability
- [ ] Broader notification policies
- [ ] Prometheus and Grafana integrations
- [ ] Expanded Home Assistant integration
- [ ] UniFi, Proxmox, NAS, backup, and UPS integrations

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
