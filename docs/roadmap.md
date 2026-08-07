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
- [ ] Persist backup observations for 30-day success rate, duration trends and failure history
- [ ] Optional schedule-aware staleness policy after persistent history exists

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

Proxmox is intentionally not part of the SirisOS roadmap because this installation does not use it. All broader integrations remain optional; blank configuration reports disabled and creates no alert noise. Credentials remain server-side. Hyper Backup monitoring uses runtime API discovery and degrades gracefully when optional task fields are unavailable. The same Integration Framework is the foundation for the later Obsidian/Selkies Knowledge connector.

### Homelab follow-on backlog

- [ ] Persist backup observations and build 30-day protection analytics
- [ ] Safe UPS power-event automation and graceful shutdown orchestration
- [ ] Operations Center for incidents, integrations, updates, backups and maintenance actions
- [ ] Further Flutter web performance work: isolate Mission Control clock state and throttle pointer-hover activity

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
