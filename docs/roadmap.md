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

Deferred enhancements are not Sprint 0.4.1 blockers and remain on the later backlog: notification action buttons, direct drag-and-drop on the workspace, optional Ollama wording, event diagnostics, and score domains whose modules do not yet exist.

## Sprint 0.4.2 — Mission Control

Build the dedicated `/mission` Situation Room using SirisCore services.

- [ ] Navigation-free full-screen shell
- [ ] Large live clock
- [ ] Shared Widget Registry grid
- [ ] Siris Score presentation and detailed explanation
- [ ] Deterministic briefing panel
- [ ] Activity timeline
- [ ] Event-driven auto-refresh
- [ ] Focus modes: Work, Home, Fitness, and Travel
- [ ] Smooth transitions and ambient display modes
- [ ] Second-monitor and wall-display optimisation

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
