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

## Build validation ✅ Foundation

- [x] GitHub Actions workflow on pull requests and `main`
- [x] Python compile check
- [x] Backend pytest suite
- [x] Flutter analyze
- [x] Flutter test
- [x] Flutter release web build
- [x] Full unified production `sirisos` Docker image build
- [ ] Require CI status checks in branch protection once repository policy is configured

## Health Data Export REST sidestep — planned

- [ ] `POST /api/v1/health/import` ingestion endpoint
- [ ] Dedicated unattended bearer token
- [ ] Idempotent daily metric imports
- [ ] Steps, sleep, HRV, resting HR and workouts first
- [ ] Canonical Health Store / History integration
- [ ] Event Bus refresh and Health summary API
- [ ] Health Data Export context provider
- [ ] Keep MCP as an optional future query/interface layer rather than canonical ingestion

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
- [ ] Operations Planner and recommendation engine — deterministic pipeline first: Observation → Rule/Policy → Recommendation → Evidence → Capability → Action. Ollama's role is explaining a recommendation in natural language, not inventing it
- [ ] Action Framework bound to capabilities
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
