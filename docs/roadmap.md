# SirisOS Roadmap

This is the implementation checklist for SirisOS. `README.md` is the authoritative handover. Keep both synchronized whenever scope or sprint status changes.

## Sprint 0.4.1 — SirisCore ✅ Complete

- [x] Typed Event Bus
- [x] Module Registry
- [x] Widget Registry
- [x] Notification Centre
- [x] Deterministic Briefing Engine
- [x] Explainable Siris Score foundation
- [x] Scheduler
- [x] AI Context Service
- [x] Persisted SirisCore settings
- [x] Standard `git pull && make up` deployment workflow

## Sprint 0.4.2 — Mission Control ✅ Complete

- [x] Navigation-free `/mission` Situation Room
- [x] Live clock/date, briefing, Siris Score, widget grid and activity timeline
- [x] Event-driven refresh with scheduled fallback
- [x] Adaptive widget priority and critical wake
- [x] Balanced, Operations and Compact profiles
- [x] Work/Home/Fitness/Travel focus modes
- [x] Ambient and reduced-motion behaviour
- [x] Runtime diagnostics
- [x] Shared dark red/black SirisOS design system

## Sprint 0.4.3 — Live Homelab ✅ Platform foundation complete

### 0.4.3a — Integration Framework ✅
- [x] `SirisConnector` contract
- [x] Integration health model and `SirisIntegrationManager`
- [x] Scheduler-backed refresh and deterministic failure recovery
- [x] Disabled/unconfigured state
- [x] Server-side credential boundary
- [x] ADR 012

### 0.4.3b — Docker ✅
- [x] Container list/status/actions/logs
- [x] CPU/RAM and host metrics/history
- [x] Image update availability
- [x] Audit history
- [x] ADR 013

### 0.4.3c — Notification Policies ✅
- [x] Activation, duration and escalation rules
- [x] Stable-ID deduplication and explicit resolution
- [x] Mission Control wake, Briefing and Siris Score integration
- [x] ADR 014

### 0.4.3d — Home Assistant ✅
- [x] Server-side credentials
- [x] WebSocket state-change subscription with REST fallback
- [x] Entity browser/search/filter
- [x] Allow-listed controls
- [x] ADRs 015–016

### 0.4.3e — Infrastructure integrations ✅

Prometheus:
- [x] Target health and instant PromQL
- [x] Policies, caching and Mission Control widget
- [x] ADR 017

Grafana:
- [x] Health/version and dashboard discovery
- [x] Dashboard launch and optional bounded render proxy
- [x] ADR 018

UniFi:
- [x] Controller/site/device/AP/client/WAN overview
- [x] Controller/device policies and Mission Control widget
- [x] ADR 019

Storage / Synology:
- [x] Host filesystem monitoring and storage policies
- [x] Synology DSM discovery, disks and volumes
- [x] Hyper Backup task/result monitoring
- [x] Hyper Backup failure policy and Mission Control widget
- [x] ADR 021

UPS / NUT:
- [x] Vendor-neutral NUT connector
- [x] Battery/runtime/load/voltage/power state
- [x] On-battery, low-battery and availability policies
- [x] Mission Control UPS widget
- [x] ADR 022

### 0.4.3f — Operations Center ✅
- [x] Authenticated `/operations` route
- [x] Operational overview, incidents and attention queue
- [x] Integration health and manual refresh
- [x] Event-driven updates
- [x] ADR 023

### 0.4.3g — Generic History Engine ✅ Foundation
- [x] PostgreSQL `time_series_observations`
- [x] Generic source/metric/dimensions identity
- [x] Numeric/text observations
- [x] Retention/sample throttling
- [x] Authenticated history API and Flutter client
- [x] Storage, Synology, Hyper Backup and UPS producers
- [x] ADR 024
- [ ] Bridge legacy Docker/host history into generic contract
- [ ] UniFi client/outage history
- [ ] "What changed?" queries per object (since yesterday / this week / since I last looked) backed by the History Engine, generalizing beyond storage/backup metrics

### 0.4.3h — Backup Protection Analytics ✅
- [x] Discrete Hyper Backup completion events
- [x] 1–90 day deterministic protection analytics
- [x] 30-day Operations Center panel
- [x] Per-task success/failure rates
- [x] ADR 025
- [ ] Schedule-aware overdue backup policy
- [ ] Duration analytics when DSM exposes reliable per-run duration

### 0.4.3i — Incident Engine ✅ Foundation
- [x] Deterministic incident grouping
- [x] Power-outage correlation anchored by UPS state
- [x] Compute/storage/network/observability grouping
- [x] Explicit correlation reasons and raw evidence retention
- [x] ADR 026
- [ ] Persist incident lifecycle/history
- [ ] Acknowledge/assign/resolve workflow

### 0.4.3j — Digital Twin ✅ Configurable foundation
- [x] Directed dependency graph
- [x] Transitive downstream impact traversal
- [x] Built-in Synology → Hyper Backup → Backup Protection chain
- [x] Editable local topology with duplicate/self/cycle protection
- [x] Incident downstream impact enrichment
- [x] ADRs 027–028
- [ ] Server-side canonical topology
- [ ] Arbitrary custom nodes
- [ ] Authoritative dependency discovery
- [ ] Interactive graph visualization
- [ ] Dependency-aware recommended actions

### 0.4.3k — Capability Framework ✅ Foundation
- [x] Stable capability IDs
- [x] Provider/kind/risk/confirmation metadata
- [x] Live availability from Integration Manager
- [x] Fail-closed control semantics
- [x] Operations Center capability panel
- [x] ADR 030
- [ ] Provider-owned dynamic capability registration
- [ ] Capability argument schemas and authorization requirements
- [ ] Server-side capability endpoint
- [ ] Bind executable capabilities to Action Framework

### Homelab / Operations follow-on backlog
- [ ] Operations Planner
- [ ] Action Framework
- [ ] Playbook Engine
- [ ] Safe UPS graceful shutdown orchestration
- [ ] Explainable Siris Score contribution history
- [ ] Further Flutter web performance work: isolate Mission Control clock state and throttle pointer-hover activity

## Sprint 0.4.4 — SirisCore Context Service ✅ Foundation complete

- [x] Typed context facts/domains/priorities/provenance
- [x] Modular context-provider interface
- [x] Deterministic current snapshot and primary context
- [x] Event Bus context updates
- [x] Bounded context transition timeline
- [x] Operational contexts for power, backup, network, storage and compute state
- [x] `siris.context` Mission Control widget
- [x] Operations Center current-context surface
- [x] ADR 031
- [ ] Persist context timeline through History Engine
- [ ] Manual context override with expiry/provenance
- [ ] Health Data Export context provider
- [ ] Home Assistant presence provider
- [ ] Calendar/work/project context providers
- [ ] Context-aware Briefing Engine and Siris Score
- [ ] Context-aware UI: reprioritize (never hide) module/screen prominence by current context — work, home, gym, morning, evening — so Mission Control reflects the user's actual current context
- [ ] Authenticated context API for backend/Hermes consumers
- [ ] Presence Engine

Context claims remain evidence-based; SirisOS must not infer working/sleeping/travelling/focused states without authoritative inputs.

## Sprint 0.4.5 — Engineering Module 🚧 In progress

### Engineering calculators ✅ Expanded civil/water foundation
- [x] First-class Engineering module through Module Registry
- [x] Mobile-friendly calculator category/selector surface
- [x] Full circular-pipe Manning capacity and velocity
- [x] Part-full circular-pipe Manning capacity, velocity and flow area
- [x] Minimum full-pipe grade for a target Manning flow
- [x] Rectangular open-channel Manning capacity
- [x] Trapezoidal open-channel Manning capacity
- [x] Rectangular-channel critical depth and velocity
- [x] Rational Method peak flow using mm/h and hectares
- [x] Rectangular free-flow weir discharge
- [x] Circular orifice discharge
- [x] Hazen–Williams pressure-pipe headloss
- [x] Darcy–Weisbach headloss with Reynolds number and friction factor
- [x] Pump hydraulic/input power estimate
- [x] Buried-pipe buoyancy screening helper
- [x] Constant-flow detention screening helper
- [x] Minor-loss (K-value) fitting/valve/bend headloss, entered K coefficients rather than a hidden fitting catalogue
- [x] Input validation and numerical regression tests
- [x] Engineering navigation and Quick Action
- [x] ADR 032
- [ ] Traceable standards/authority assumption profiles per calculator
- [x] Save/share calculation records into project context (ADR 055)
- [x] Cite an exact standard revision on a saved calculation (ADR 056)
- [ ] Multi-stage detention routing / stage-storage-discharge helper
- [ ] Pit/inlet capture and gutter-flow helpers once authority assumptions are profile-driven

### Standards Library / Search ✅ Expanded foundation
- [x] Engineering hub with Calculators and Standards surfaces
- [x] Authenticated private PDF upload
- [x] Persistent local storage under `data/standards`
- [x] Configurable `SIRISOS_STANDARDS_MAX_UPLOAD_MB` limit
- [x] Title, authority, reference and edition/revision metadata
- [x] Page-level local text extraction with `pypdf`
- [x] Ranked local text search with page/snippet provenance
- [x] Citation-bearing page retrieval
- [x] Scanned/image PDFs accepted and handled by local OCR fallback
- [x] OCRmyPDF/Tesseract indexing for scanned/image-only PDFs with native text preferred
- [x] Immutable document IDs for citation provenance
- [x] Archive/restore lifecycle without destructive deletion
- [x] Replace-as-new-revision workflow with supersedes/superseded-by lineage
- [x] Historical/archived revision search for citation review
- [x] Local hybrid civil/water semantic reranking with exact lexical priority
- [x] Authoritative discovery links for Standards Australia, WSAA, Sydney Water, Austroads and Australian Rainfall & Runoff
- [x] No scraping/republication of protected standards content
- [x] ADR 033 private standards library and citation/provenance boundary
- [x] ADR 034 citation-first retrieval boundary
- [x] ADR 036 local OCR boundary
- [x] ADR 037 immutable document lifecycle/versioning
- [x] ADR 038 local hybrid semantic retrieval
- [ ] Optional explicit irreversible purge/export workflow for administrators
- [ ] Optional local vector/embedding index for broader semantic recall
- [ ] Traceable standards/authority assumption profiles for calculators

### SirisHydro retrieval v1 ✅ Evidence foundation
- [x] Authenticated `/api/v1/engineering/sirishydro/evidence` endpoint
- [x] Deterministic cross-document page ranking
- [x] Bounded evidence excerpts
- [x] Exact document/reference/edition/authority/page provenance
- [x] Deterministic human-readable citations
- [x] Explicit sufficient/insufficient evidence state
- [x] Copyable evidence context packet for future model use
- [x] Dedicated SirisHydro Engineering tab
- [x] Backend evidence-assembly regression tests
- [x] Hybrid semantic retrieval reranking while retaining deterministic provenance
- [x] Active-revision-only evidence assembly for new answers
- [x] Retrieval strategy included in evidence context
- [x] Ollama-backed answer composition over retrieved evidence (ADR 057)
- [x] Answer UI with source-supported vs general-reasoning distinction
- [x] Source-page deep links from SirisHydro results, sharing the Standards Library's page viewer
- [x] Persistent query history — question, evidence citations, synthesized answer (ADR 059)
- [ ] Conversation/session context
- [ ] Optional vector/embedding reranking while retaining deterministic lexical fallback

### Engineering follow-ons
- [ ] SirisPM integration
- [ ] Project notes, drawing review and Civil 3D utilities
- [ ] Engineering context provider for active project/design mode

## Deployment architecture ✅ Unified application container

- [x] One production `sirisos` application container for Flutter web + FastAPI
- [x] Nginx serves Flutter and reverse-proxies same-origin `/api/*` to loopback Uvicorn
- [x] Production API no longer requires a host/IP compiled into Flutter
- [x] End-to-end Nginx → FastAPI `/health` container healthcheck
- [x] Preserve OCRmyPDF/Tesseract inside the unified application image
- [x] Keep PostgreSQL, docker-socket-proxy and node-exporter as separate infrastructure boundaries
- [x] Remove obsolete standalone web/API production Dockerfiles
- [x] ADR 039
- [x] iOS platform target — `apps/mobile/ios/` scaffolded and buildable/launchable on the iOS Simulator via `flutter run`, ahead of SirisOS eventually shipping as a native iOS app rather than only Flutter web (ADR 076)
- [x] iOS sign-in UI test — a `RunnerUITests` XCUITest target verifies the sign-in flow via `xcodebuild test`, independently of Claude Code's own (currently disabled) simulator tooling; confirmed against the real backend (ADR 077)

## Build validation ✅ Foundation

- [x] GitHub Actions workflow on pull requests and `main`
- [x] Python compile check
- [x] Backend pytest suite
- [x] Flutter analyze
- [x] Flutter test
- [x] Flutter release web build
- [x] Full unified production `sirisos` Docker image build
- [ ] Require CI status checks in branch protection once repository policy is configured

## Health Data Export REST ingestion

- [x] `POST /api/v1/health/ingest` ingestion endpoint
- [x] Dedicated unattended bearer token (`SIRISOS_HEALTH_INGEST_TOKEN`)
- [x] Idempotent metric imports, keyed on metric/timestamp/source/value/unit
- [x] Steps, sleep, HRV, resting HR and workouts first (any Health Auto Export metric is accepted)
- [x] Canonical `health_metric_samples` / `health_workouts` store, workouts upserted by id
- [x] `GET /api/v1/health/status` sync summary (`last_sync`, `records_received`, `last_error`)
- [x] Health summary API — `GET /api/v1/health/summary` reads back the ingested HRV/resting-HR/sleep (any metric type present) with a trailing 14-day baseline ratio, mirroring the same "vs your own history" pattern as weekly training load. Generic over metric type, not hardcoded to specific metrics. Surfaced as a "Recovery vs your baseline" section on the Health screen (ADR 072). This is the prerequisite that was blocking Training Conflict Detection, Run Readiness and the Smart Weekly Planner
- [x] Event Bus refresh on new sync v1 — `HealthSyncWatcher` polls the existing `GET /health/status` every 5 minutes (no backend push mechanism exists anywhere in this app, so this is the poll-then-publish pattern `SirisIntegrationManager` already uses for its own connectors) and publishes `ModuleDataChanged(moduleId: 'health')` only when `last_sync`/`records_received` actually change. Health and Coach screens subscribe and refresh automatically -- verified live with a temporarily shortened poll interval (ADR 075)
- [ ] Health Data Export context provider
- [x] Keep MCP as an optional interactive/debug query layer rather than canonical ingestion

## Sprint 0.5.0 — Knowledge Platform 🚧 In progress

- [x] Obsidian/Selkies launch integration
- [x] Obsidian connector through Integration Framework
- [x] First-class Knowledge module
- [x] Read-only Obsidian-compatible Markdown vault mount
- [x] Authenticated overview/search/note APIs
- [x] Recent Notes and Daily Notes surfaces
- [x] Vault title/path/content search
- [x] Folder browsing and filtering
- [x] Frontmatter and inline Obsidian tag browsing/filtering
- [x] Deterministic wikilink resolution
- [x] Explicit ambiguous-wikilink candidate selection
- [x] Clickable wikilink navigation in note viewer
- [x] Backlink discovery and navigation
- [x] Bounded per-request in-memory link index
- [x] Global SirisOS search across vault content
- [x] Global search coverage extended to Projects, saved Engineering calculations, the Standards library and Siris Memory, with per-source graceful degradation so one corrupted store can't take down search for everything else (ADR 062)
- [x] Mission Control Knowledge widget
- [x] Context-aware related notes with explainable ranking
- [x] Optional Ollama AI semantic search, blended transparently into ranking
- [x] Cross-link Engineering and Homelab Knowledge context
- [x] ADR 040 read-only Knowledge vault foundation
- [x] ADR 041 knowledge relationship resolution
- [x] ADR 042 global search and Mission Control widget
- [x] ADR 043 related notes and local graph contract
- [x] ADR 045 Obsidian launch integration
- [x] ADR 046 optional Ollama semantic search
- [x] ADR 047 contextual Knowledge cross-links
- [x] ADR 048 typed Knowledge context and API entrypoint
- [x] Flutter UI for the local Knowledge Graph
- [x] ADR 054 Knowledge Graph UI
- [ ] Cross-link Tasks, Calendar and Briefings once those modules have authoritative object models

## Sprint 0.6 — Projects and Context Graph 🚧 In progress

- [x] General project model with stable UUID identities, kind and lifecycle status
- [x] Typed Project ↔ Knowledge note relationships (`contains`/`references`)
- [x] Explicit manually-selected current project context with SirisCore integration
- [x] Bounded Project Context Graph projection and Flutter Projects → Graph view
- [x] Typed Project ↔ Engineering Standard relationships (`references` only), attachable from the Project Context Graph
- [x] ADR 049 project model foundation
- [x] ADR 050 project-knowledge relationship contract
- [x] ADR 051 current project context
- [x] ADR 052 project context graph projection
- [x] ADR 053 project-engineering standard relationships
- [x] Typed Project ↔ Engineering Calculation relationships (`contains`/`references`), attachable from the Project Context Graph
- [x] ADR 055 saved calculation records and project relationships
- [x] ADR 056 cite an exact standard revision on a saved calculation
- [ ] Relationships between tasks, files, events, repositories and conversations
- [ ] Context containers for engineering, homelab, travel, fitness and personal projects
- [ ] Siris Knowledge Graph semantic layer unifying the Digital Twin (operational infrastructure relationships) and the Project Context Graph (information/work-object relationships) into one traversable graph spanning Projects (Notes/Standards/Calculations/Decisions), Homelab (Servers/Services/Incidents), Knowledge, Health, Calendar and Conversations — so SirisAI traverses known relationships before retrieving supporting information, rather than performing generic RAG
- [ ] `siris://` deep link URI scheme (project, knowledge note, engineering calculation, homelab service, incident, action) so notifications, Knowledge notes, Siris responses, Briefings and automation outputs can all point to real SirisOS objects
- [ ] Migrate project/relationship persistence from atomic JSON store to PostgreSQL behind the same API contract

## Sprint 0.7 — SirisAI, Intelligence and Automation

Suggested internal sequencing: Ollama connector → Siris Memory → recommendation engine → Action Framework → Playbooks → Siris Inbox. Hermes should not receive meaningful write/control capability until the deterministic layers ahead of it (Planner, Action Framework, approvals) are solid — automation must stay explainable and approved, not just fast.

### Ollama / local inference
- [x] Ollama connector/provider with server-side configuration (ADR 057)
- [x] SirisHydro answer synthesis grounded in retrieved evidence, fail-open when Ollama is unavailable (ADR 057)
- [ ] Shared model routing for SirisHydro, SirisPM, briefings and semantic search
- [ ] Per-module model/profile selection and context budgets
- [x] Model availability monitoring (ADR 058)
- [ ] Preserve deterministic outputs beneath optional LLM rewriting

### Siris Memory
- [x] Siris Memory Service v1 — Facts, Preferences, Episodes, Decisions, Observations and Conversation memory classes; manual entry with free-text content + optional source, atomic JSON persistence, CRUD API filterable by class (ADR 061)
- [x] Wired into the `Siris` module (previously a "planned for later" placeholder), reachable from More → Siris
- [ ] Structured (not free-text) provenance per memory record — typed source object reference, confidence — matching the citation standard already set by SirisHydro and Context
- [ ] Cross-object traversal (e.g. Project → calculation → standard → SirisHydro question → meeting note → decision) so SirisAI can answer "why did I decide X?", not just "what does X say?"
- [ ] Automatic capture from SirisAI conversations, once a conversational surface exists
- [ ] Distinct from, and complementary to, Knowledge (documents), Projects (structured relationships) and SirisHydro history (evidence-grounded Q&A) — Memory is Siris's own accumulated understanding, not a fourth copy of the same content

### Universal Command Palette & contextual "Ask Siris"
- [x] Cmd+K / Ctrl+K command palette reusing the global search endpoint (ADR 062) — arrow-key navigation, Enter to open, Escape to close, reachable from any screen, with a `⌘K`-hinted entry point in the desktop sidebar
- [ ] Palette results blend live state, related Knowledge notes/projects and available actions for a single query (e.g. "plex" → status + notes + project + restart/logs actions)
- [ ] Contextual "Ask Siris" / "Explain this" affordance on individual objects — server, project, calculation, standard, incident, Knowledge note — not only inside one dedicated chat screen
- [ ] Keep a global Siris chat alongside contextual entry points, not instead of them

### Siris Inbox
- [ ] Unified attention queue distinct from Operations Center (investigate) and Notification Policies (alert) — Inbox is where Siris surfaces things it thinks deserve a human decision
- [ ] Each item exposes why Siris noticed it → evidence → suggested action → dismiss/snooze/act
- [ ] Sits between Notification Policies, the Incident Engine and the Operations Planner/recommendation engine below

### Hermes Agent / server runtime
- [ ] Optional Hermes Agent connector/runtime adapter
- [ ] Integrate Hermes into SirisAI as tool-using server agent
- [ ] Keep Hermes endpoint/authentication server-side
- [ ] Permit Hermes to use Ollama without making Hermes mandatory for other AI features
- [ ] SirisAI action broker with allow-listed operations
- [ ] Explicit confirmation for destructive/high-impact actions
- [ ] Never enable Hermes dangerous-command approval bypass
- [ ] Audit prompts, approvals, commands/actions and results
- [ ] Feed Operations Center incidents and Digital Twin context into tasks
- [ ] Read-only diagnostics before write capabilities
- [ ] Least-privilege Docker/service/file actions
- [ ] Agent task/status/history surface

### Broader intelligence / automation
- [x] Recommendation Engine v1 — deterministic Observation → Recommendation → Evidence pipeline over `GET /api/v1/homelab/alerts`, with a pending/dismissed/acted lifecycle and an Operations Center panel (ADR 064). Cross-source correlation (the full Incident Engine's capabilities) and escalation-duration-aware rules remain future work — see ADR 064's Consequences
- [ ] Extend recommendation sources beyond `homelab_alerts` once Incidents/Notification Policies have a real backend representation to evaluate
- [x] Action Framework v1 — server-side capability registry (`docker.start`/`stop`/`restart`) bound to already-audited execution primitives, with server-enforced confirmation for medium-risk actions (ADR 065). Home Assistant device-control actions are now audited too, though not yet onboarded as capabilities
- [x] Wire a Recommendation's `suggested_action` to a specific capability ID — `container-*-stopped`/`-unhealthy` alerts bind to `docker.start`/`docker.restart`, giving those recommendations a "Run" button in Operations Center that executes the real, audited capability and auto-marks the recommendation acted on success. Every other recommendation stays descriptive-only, honestly, rather than a capability being force-fit where none is registered (ADR 068)
- [ ] Bring Home Assistant device control into the capability registry
- [ ] Ollama's role is explaining a recommendation in natural language, not inventing it
- [ ] Playbook Engine — multi-step diagnostic/operational workflows (e.g. internet-outage or service-down triage). Siris walks the user through steps first; Hermes performs approved diagnostic steps later; full automation ("Siris, fix Plex") only once capabilities and approvals are proven — observability → recommendations → assisted operations → automation
- [ ] Context Engine consumers
- [ ] n8n integration
- [ ] Event-driven Siris Automations
- [ ] Human approval policies shared by Hermes and other automation
- [x] ADR 029: SirisAI orchestration vs Hermes runtime vs Ollama inference

## Sprint 0.8 — Plugin SDK

- [ ] External module contract
- [ ] Plugin routes/widgets/notifications/briefing/search/actions/context providers
- [ ] Versioned public APIs and compatibility policy

## Sprint 0.9 — SirisRun & SirisGym Intelligence

Running and Gym have been fully shipped, DB-backed modules since early in the project but never had a roadmap section of their own — this sprint gives them one, incorporating a dedicated brainstorm into a single training-intelligence direction rather than two apps that happen to live in the same shell. The signature goal (per the brainstorm's own framing): general fitness apps have great loggers; a self-hosted system's edge is saying *"your last five interval sessions performed best when they were at least 48 hours after legs, so I've moved Thursday's run to Friday"* — running, lifting, recovery and schedule informing each other, not living in silos.

Suggested internal sequencing, adapted from the brainstorm's own recommended order to reflect what's already real: Progressive overload → PR/record tracking → weekly training load → Siris Coach summaries → Ask Siris training queries → conflict detection → adaptive planning → correlation/predictive features. Apple Health recovery data (HRV, sleep, resting HR) is a hard dependency for readiness-aware features (Run Readiness, deload detection, conflict detection) and doesn't exist yet — see the existing "Health Data Export REST sidestep" section above, which this sprint depends on rather than duplicates.

### Baseline (already shipped, not part of this brainstorm)
- [x] Gym session logging — exercise/weight/reps/RIR sets, workout notes, volume and Epley-estimated 1RM computed per set
- [x] Workout templates with target sets/reps/RIR, prefilling a new workout
- [x] Per-exercise rollups (`GET /gym/exercises`) — best weight, best e1RM, best set volume, full history, computed live each call
- [x] ~~Client-side-only progressive overload heuristic~~ — replaced by Automatic Progressive Overload v1 below (ADR 066); noted here as the gap that motivated it
- [x] Running session logging — distance, pace, heart rate, outdoor/treadmill, a per-run effort score and an EWMA fitness-score trend
- [x] Live Apple Health snapshot (steps, resting HR, sleep, body mass, active energy, VO₂ max) via on-iPhone MCP pull — ephemeral only, nothing persisted or historized (see Health Data Export REST sidestep)

### SirisGym
- [x] Automatic Progressive Overload v1 — deterministic backend suggestion (`GET /gym/exercises/{name}/suggestion`) reasoning from the exercise's own most recent session, with a stated reason and correct handling of the "struggled" case (dropping reps / RIR ≤ 1 → repeat the load, not increase it). Surfaced in the workout form's template prefill and a new "Next session suggestion" card on the Exercise Intelligence page (ADR 066)
- [x] Personal Records v1 — a real PR-achieved event (heaviest weight, best estimated 1RM, best set volume, each checked independently per exercise) fires the moment a workout beats a prior best, with an ActivityService event and an understated in-app callout (ADR 067). Running PR tracking (fastest splits, longest run, best negative split) remains separate future work — `RunRecord` doesn't capture splits today
- [x] Automatic deload detection v1 — per-exercise signal on the Exercise Intelligence page: falling first-set reps, rising RIR-implied effort and a declining e1RM trend, all required to show a genuine non-bouncing decline across the exercise's last 3 logged sessions before flagging. Falls back to e1RM + reps alone when RIR wasn't recorded for one of the sessions. Deliberately rare/high-confidence rather than chatty (ADR 078)
- [ ] Strength score — aggregate + per-muscle-group breakdown from historical performance, explicitly framed as personal/relative rather than a universal absolute number
- [ ] Muscle map / weekly workload by muscle group — requires exercise → muscle-group tagging that doesn't exist yet
- [x] Training volume heatmap v1 — daily calendar-style grid combining gym volume and running effort into one self-relative intensity per day (each modality expressed as a fraction of the athlete's own all-time best day, summed and capped), on both the Gym and Running screens. Muscle-group breakdown remains unbuilt -- no exercise taxonomy exists yet (ADR 080)
- [ ] Smart rest timer that learns per-exercise-category rest duration from observed set-to-set performance dropoff
- [ ] Set-by-set live coaching during a workout (next-set suggestion, rest-length nudge) — natural extension once Progressive Overload v1's reasoning is real
- [ ] AI workout generator grounded in actual recent training (deterministic candidate selection first; Ollama's role, if any, is explaining the choice, not inventing the program — matching the SirisHydro/ADR 057 pattern)

### SirisRun
- [x] Personal running records v1 — longest run and lowest heart rate recorded at a comparable pace (±15 sec/km), both detected the moment a run is saved and surfaced with the same `🏆 New record` callout Gym Personal Records already uses. Fastest splits, best negative split and highest-elevation week remain explicitly deferred -- `RunRecord` captures no GPS/splits/elevation, so building them now would mean approximating rather than real evidence (ADR 079)
- [ ] Race predictor from actual run history rather than a generic VO₂max formula, with an explainable "you're relatively stronger over X than Y" comparison
- [ ] Run readiness — distinct from general recovery because someone can be HRV-recovered while their legs are wrecked from squats; needs both Health recovery data and recent gym leg volume as inputs, so depends on both the Health import pipeline and the training-load work below
- [ ] Post-run AI analysis grounded in pace/HR-drift/splits versus the runner's own recent history (second instance of the SirisHydro/ADR 057 deterministic-evidence-plus-optional-Ollama-synthesis pattern)
- [ ] Running fitness score breakdown (aerobic/speed/endurance/consistency), replacing the single EWMA effort trend with an explainable multi-factor score
- [ ] Live pace strategy for a goal time, and planned-vs-actual pacing comparison afterward
- [ ] Route generator and shoe tracking/correlation — both depend on data SirisOS doesn't capture today (GPS/elevation, shoe per run) and need a capture-side decision before they're buildable

### Unified training
- [x] Weekly training load v1 — running (`effort_score`) and gym (`total_volume_kg`) weekly totals each expressed as a percentage of the athlete's own trailing 8-week baseline, summed into one `combined_index` (100 = a typical week). Requires at least 2 qualifying baseline weeks per modality before showing a ratio, so a new user correctly sees "not enough history yet" rather than a distorted number. Surfaced as a shared `TrainingLoadCard` on both the Gym and Running screens (ADR 069)
- [x] Training conflict detection v1 — recovery-based: flags when HRV/resting heart rate is notably worse than your trailing baseline (Health Summary API) on a day you also trained, via a "Today" card on the Coach screen (ADR 073). The brainstorm's own literal example (heavy-leg-day-before-intervals sequencing) remains future work — it needs workout-name/run-intensity heuristics this v1 deliberately avoided in favour of a real signal with none
- [ ] Smart weekly planner balancing recovery, running load and historical performance, with drag-to-rearrange
- [x] "Can I train today?" / "Should I run tonight?" v1 — a new Ask Siris question pattern composing the existing Training Conflict Detection guidance and Weekly Training Load assessment into one answer; no new UI, no new inference, works through the existing free-text Ask Siris box (ADR 081)

### Siris Coach and Ask Siris
- [x] Siris Coach as a first-class section — "this week" shipped as a new `Coach` navigation destination (deterministic report; ADR 070). "Today" (readiness/recommendation) explicitly deferred — needs the still-unbuilt Health summary API (see the Health Data Export section above) and a planned/scheduled session to react to, neither of which exist yet
- [x] Weekly coach report v1 — deterministic week-over-week deltas (running distance/count, gym volume/session count), new-bests-this-week, and the existing weekly training load assessment, composed into one headline sentence. Optional Ollama narrative synthesis on top is deliberately deferred to a follow-up slice (ADR 070) rather than built alongside v1
- [x] Ask Siris natural-language training queries v1 — deterministic pattern matching (not an NLU classifier) over a fixed set of recognized question shapes (exercise progress/max, last-time-at-weight, most-improved-exercise, best-distance, training counts, weekly summary), each routed to the exact service call that answers it; optional Ollama rephrasing only after a deterministic answer already exists, never for fact-finding. Surfaced as an "Ask Siris" card on the Coach screen (ADR 071). "What's my strongest muscle group" and sleep/recovery correlation questions are out of scope -- they need data (exercise-to-muscle-group tagging, the Health summary API) that doesn't exist yet

### Gamification (kept understated per the brainstorm's own instinct)
- [x] Achievements v1 — 8 concrete, evidence-backed milestones (100kg club on bench/squat/deadlift/overhead press, Million Kilo Club lifetime volume, sub-25 5K, 8-consecutive-week consistency streak, 5-consecutive-session progressive-overload streak), each a real recorded fact crossing a real threshold, shown with progress toward the next unlock (ADR 074). "Climber" (elevation) excluded -- not captured by `RunRecord`
- [ ] A training level derived from historical strength/endurance/consistency/recovery data, not a game-style XP grind — deliberately deferred (ADR 074): Endurance/Consistency have a real basis in existing data, but Strength has no defensible basis without bodyweight or strength-standards data this app doesn't have, and building one would be this app's first fabricated (non-evidence-based) number

### Apple Watch / iPhone
- [ ] Focused watch-face-style views (current set/target/rest during a workout; pace/target/HR/distance during a run) once a native or watchOS-companion surface exists — an iOS platform target now exists (see Deployment architecture, ADR 076), but no watchOS-companion surface does, so this remains gated on that decision, not just a screen redesign

### Experimental (explicitly speculative, not scheduled)
- [ ] Training Digital Twin — model the user over time to project outcomes of a proposed training change before they make it
- [ ] Correlation Explorer — surface observed correlations between sleep/recovery/training variables and performance, always as correlation with its evidence shown, never presented as causation (matching the Digital Twin/incident-correlation rule already in force elsewhere in this document)
- [ ] What-If Planner — simulate a proposed training-load change against current recovery data
- [ ] Plateau Detective — when an exercise stalls, examine frequency/volume/intensity/sleep/bodyweight for likely explanations
- [ ] Personal Fatigue Model — learn the user's own recovery timeline per training stimulus rather than applying a generic recovery window
- [ ] Auto Periodisation — build concurrent training blocks toward a stated dual goal (e.g. a strength number and a race time)

## Sprint 1.0 — Personal Operating System

Stable daily platform spanning Mission Control, Operations Center, Personal, Infrastructure, Engineering, Knowledge, Intelligence and Automation.

- [ ] Richer Morning Briefing synthesizing Siris Score, homelab health/projections, calendar and active-project status into a natural-language summary — every sentence must remain traceable to evidence, matching the SirisHydro/Context provenance standard rather than becoming free-form generation
- [ ] Health, Calendar and Tasks as first-class context providers and Briefing inputs

The direction: observe → understand → remember → recommend → act. SirisOS should not become twenty dashboards bolted together; it should become the intelligence and control layer connecting them.

## Explicit exclusions / rules

- Proxmox is intentionally not part of this installation.
- External credentials remain server-side.
- `main` must remain deployable through `git pull && make up`.
- Production Flutter uses same-origin API routing through the unified `sirisos` container; avoid host-specific compiled API URLs unless explicitly required for development.
- Historical analytics must come from observed data, not polling-frequency guesses.
- Incident correlation is not causation without dependency evidence.
- Digital Twin causal/downstream claims require explicit dependencies.
- Context claims require provider-backed provenance.
- Engineering calculations must expose assumptions/units and must not claim standards compliance unless traceable authority profiles justify it.
- Licensed standards remain private local documents; SirisOS does not scrape or redistribute protected standards content.
- SirisHydro source-supported claims require exact evidence provenance and must not invent missing clauses/values.
- Provenance is a SirisOS-wide UX standard, not one feature's behavior: any AI-adjacent claim (recommendation, projection, Briefing sentence, Memory-derived answer) should expose a "Why?" affordance to its underlying evidence/data/confidence, matching the standard already set by SirisHydro and Context.
- Standards document IDs are immutable evidence identities; replacement creates a linked new revision rather than overwriting historical source material.
- Semantic/vector retrieval may improve recall but must preserve exact page provenance and a deterministic lexical fallback.
- Knowledge vault access remains read-only until a write/editing design is explicitly approved; ambiguous wikilinks must not be silently resolved.
- Pull requests should pass backend, Flutter and production-container CI before merge except for explicit emergency hotfixes.
