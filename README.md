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

Production now uses one **`sirisos` application container** for both Flutter web and FastAPI. Nginx serves the UI on port `6464` and reverse-proxies `/api/*` to Uvicorn inside the same container. PostgreSQL, docker-socket-proxy and node-exporter remain separate infrastructure containers because they have distinct persistence, privilege and host-access boundaries. Flutter resolves the API from the browser's current origin, so moving SirisOS to a different host/IP no longer requires recompiling a server-specific API address. ADR 039.

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

### Deterministic civil/water calculator library

The calculator surface now uses a mobile-friendly category/selector model rather than an ever-growing tab strip. Current tools:

- Full circular-pipe Manning capacity and velocity
- Part-full circular-pipe Manning capacity, velocity and flow area
- Minimum full-pipe grade for a target Manning flow
- Rectangular open-channel Manning capacity
- Trapezoidal open-channel Manning capacity
- Rectangular-channel critical depth and critical velocity
- Rational Method peak flow using mm/h and hectares
- Rectangular free-flow weir discharge
- Circular orifice discharge
- Hazen–Williams pressure-pipe headloss
- Darcy–Weisbach headloss with Reynolds number and friction factor
- Minor-loss (K-value) fitting/valve/bend headloss from an entered sum of K coefficients
- Pump hydraulic/input power estimate
- Buried-pipe buoyancy screening
- Constant-flow detention storage screening

The calculation core is pure Dart and regression-tested. Inputs, units and assumptions remain explicit. Empirical coefficients remain user inputs rather than hidden defaults tied to a standard. Screening helpers do **not** claim standards compliance or replace project-specific criteria, detailed hydraulic modelling or manufacturer data. ADR 032.

Any calculation result can be saved via an authenticated `/api/v1/engineering/calculations` record — exactly the inputs and outputs shown on screen, nothing hidden or recomputed later — and attached to a Project from the Project Context Graph, alongside Knowledge notes and Engineering Standards. ADR 055.

A saved calculation can optionally cite the exact standard document/edition it was designed to, picked from the private Standards library; the citation label is resolved fresh on every read and survives the cited standard later being archived or removed. ADR 056.

### Private Standards Library / Search

The Engineering module now has a **Calculators / Standards / SirisHydro** hub.

SirisOS can store and search standards PDFs that the administrator is entitled to use:

- Authenticated PDF upload from the Flutter web UI
- Raw PDFs persisted privately under `data/standards`
- Default per-file limit of 100 MB, configurable with `SIRISOS_STANDARDS_MAX_UPLOAD_MB`
- Metadata for title, authority/publisher, reference and edition/revision
- Page-level local text extraction using `pypdf`
- Local OCR fallback with OCRmyPDF/Tesseract for scanned/image-only standards, while preserving original PDFs and page numbering
- Ranked local text search with short snippets and page provenance
- Local hybrid semantic reranking for civil/water terminology while exact wording remains the strongest ranking signal
- Citation-bearing page retrieval
- Citation-safe document lifecycle: archive, restore, replace-as-new-revision, immutable document IDs and supersedes/superseded-by lineage
- Normal search returns active revisions; archived/superseded revisions can be included explicitly for historical citation review
- Authoritative source shortcuts for Standards Australia, WSAA, Sydney Water, Austroads and Australian Rainfall & Runoff
- SirisOS does not scrape or redistribute protected standards content

ADRs 033–034 define the private/citation-first retrieval boundary, ADR 036 defines local OCR, ADR 037 defines the immutable revision lifecycle, and ADR 038 defines local hybrid semantic retrieval.

### SirisHydro evidence retrieval v1

SirisHydro now has an evidence-first retrieval workspace backed by the private standards library.

Current behavior:

- Authenticated `/api/v1/engineering/sirishydro/evidence` endpoint
- Deterministic hybrid lexical + civil/water semantic page ranking across uploaded/indexed standards
- Related terminology such as grade/slope/gradient and buoyancy/flotation/uplift can improve recall without replacing exact-match priority
- New evidence packets use active document revisions only; archived/superseded revisions remain available for historical citation review
- Bounded excerpts with document/reference/edition/authority/page provenance
- Stable human-readable citations
- Explicit `sufficient_evidence` state
- Retrieval strategy exposed in the evidence packet/context
- Copyable context packet for Ollama/SirisAI composition
- Clear refusal boundary when the local library does not support a standards requirement
- "View source page" deep link from each evidence item, opening the exact cited page through the same page-viewer dialog the Standards Library uses

When a directly-connected Ollama server is configured (`OLLAMA_URL` + `SIRISOS_OLLAMA_CHAT_MODEL`), SirisHydro also returns a `synthesized_answer`: a grounded, cited answer generated from the same evidence packet and non-invention rule the context packet already exposed. The local standard remains the source of truth — synthesis is fail-open, so an unconfigured or unreachable Ollama server leaves the evidence-only experience unchanged, and the model is never allowed to answer beyond what the retrieved evidence supports. ADRs 033–035, 038 and 057.

Every question is now recorded to a persistent history — question, evidence citations, synthesized answer — reachable from a "Past questions" sheet on the SirisHydro screen, with re-ask and delete actions. This is the first concrete step toward SirisHydro as an agent with memory, not yet conversational context: history isn't (yet) read back into future answers. ADR 059.

Planned Engineering follow-ons:

- Optional local vector/embedding recall stage while preserving deterministic lexical fallback and page provenance
- Traceable authority/assumption profiles for calculators
- Shared model routing so SirisPM, briefings and semantic search reuse the same Ollama connector
- SirisPM integration
- Project notes and drawing review
- Civil 3D utilities
- Engineering Context provider

## Build validation

GitHub Actions CI now runs on pull requests and `main` pushes. It validates:

- Python source compilation
- Backend pytest suite
- Flutter dependency resolution
- Flutter analysis
- Flutter tests
- Flutter release web build
- Full production `sirisos` Docker image build

The goal is to prevent dependency/API/deployment regressions from reaching `main` while preserving the normal self-hosted deployment workflow.

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

## Sprint 0.5.0 — Knowledge Platform 🚧 in progress

Knowledge is now a first-class SirisOS module backed by a read-only Obsidian-compatible Markdown vault.

Current foundation:

- Authenticated `/api/v1/knowledge` overview/search/note/graph APIs
- Read-only host vault mount with Markdown remaining the source of truth
- Recent Notes and Daily Notes surfaces
- Vault content/title/path search
- Folder browsing and filtering
- Frontmatter plus inline Obsidian `#tag` browsing/filtering
- Deterministic `[[wikilink]]` resolution with explicit ambiguity handling
- Clickable wikilinks in the Knowledge note viewer
- Backlinks built from the same deterministic link-resolution rules
- Hidden `.obsidian` internals excluded from scanning
- Path traversal blocked and note reads bounded by configuration
- One bounded in-memory link index per relationship request; no database/indexing daemon yet
- Global SirisOS search across vault content, blended into `/api/v1/search` alongside Docker/running/gym/activity, Projects, saved Engineering calculations, the Standards library and Siris Memory — each source degrades gracefully on its own, so one corrupted store can't take down search entirely. ADR 062.
- Deterministic, explainable related notes (outgoing links, backlinks, shared tags, folder proximity) surfaced in the note viewer
- Optional Ollama semantic search, transparently blended into search ranking alongside deterministic lexical matching
- Mission Control Knowledge widget
- Optional `SIRISOS_OBSIDIAN_URL` launcher for a self-hosted Obsidian/Selkies front end, registered as a Knowledge connector in the Integration Framework
- Contextual cross-links surfacing Knowledge notes from the Engineering and Homelab modules via explicit `siris:` frontmatter/tag relationships
- A Knowledge Graph view centered on the open note, reachable from the note viewer, sharing the same radial visualization pattern as the Project Context Graph

ADRs 040–043, 045–048 and 054 define the vault, relationship-resolution, global search, Obsidian launch, semantic search, typed context and graph UI boundaries.

Planned Knowledge follow-ons:

- Cross-links into Tasks, Calendar and Briefings once those modules have authoritative object models

## Sprint 0.6 — Projects and Context Graph 🚧 in progress

SirisOS now has a first-class Projects module.

Current foundation:

- Authenticated `/api/v1/projects` API with stable UUID project identities, kind (`engineering`, `homelab`, `travel`, `fitness`, `personal`, `other`) and lifecycle status (`active`, `paused`, `completed`, `archived`)
- Atomic JSON persistence boundary, ready to migrate behind the same API contract later
- Typed Project ↔ Knowledge note relationships (`contains`/`references`) with manual provenance, addressed by canonical vault-relative path
- Explicit, manually-selected current project exposed through `GET/PUT /api/v1/projects/current`, contributing project context to SirisCore with `projects.manual_selection` provenance
- Bounded `GET /api/v1/projects/{project_id}/graph` projection and a Flutter Projects → Graph view centered on the current project
- Typed Project ↔ Engineering Standard relationships addressed by immutable standards-library document ID, restricted to `references` (a project does not "contain" a standard) and attachable directly from the Project Context Graph view
- Typed Project ↔ Engineering Calculation relationships (`contains`/`references`), attachable directly from the Project Context Graph view alongside Knowledge notes and Engineering Standards
- A saved calculation can cite the exact standard document/edition it was designed to, resolved fresh on every read

ADRs 049–053, 055 and 056 define the project model, Knowledge relationship contract, current project context, graph projection, Engineering Standard relationships, saved Engineering Calculation relationships and standard citation on a saved calculation.

Planned Sprint 0.6 follow-ons:

- Relationships to tasks, files, events, repositories and conversations
- Context containers for engineering, homelab, travel, fitness and personal projects
- Siris Knowledge Graph semantic layer above the Digital Twin

## Sprint 0.7 — SirisAI, Intelligence and Automation

SirisAI deliberately separates orchestration, agent execution and inference.

### SirisAI

Owns identity, context assembly, policy, approvals, audit, routing and UI.

### Hermes Agent

Planned optional server-side tool-using runtime for diagnostics and controlled administration. Initial integration will be read-only, later expanding to allow-listed least-privilege actions. High-impact operations require explicit approval and audit. SirisOS will never enable Hermes dangerous-command approval bypass modes.

### Ollama

Reusable local inference layer for SirisHydro, SirisPM, briefings, semantic search and deterministic-output rewriting. Hermes may use Ollama as a model backend, but other SirisAI features do not depend on Hermes.

SirisOS connects directly to a user-run Ollama server (`OLLAMA_URL`), not through Open WebUI or another intermediary. A general-purpose, fail-open chat connector (`app/services/ollama_service.py`) is the first shared piece of this layer; SirisHydro answer synthesis (ADR 057) is its first caller, alongside the existing optional Knowledge semantic-search embeddings client (ADR 046).

`GET /api/v1/intelligence/ollama-status` reports whether Ollama is configured, reachable, and whether the configured model is actually installed on the server — surfaced as a status chip on the SirisHydro screen so a silent fail-open fallback (no `OLLAMA_URL`, wrong model name, unreachable server) is visible rather than indistinguishable from "not configured." ADR 058.

ADR 029 records this boundary; ADR 057 records the chat connector; ADR 058 records availability status.

### Siris Memory

Siris's own accumulated understanding — distinct from Knowledge (documents), Projects (structured relationships) and SirisHydro history (evidence-grounded Q&A). v1 ships six memory classes (Fact, Preference, Episode, Decision, Observation, Conversation), manually entered with free-text content and an optional free-text source, backed by the same atomic-JSON persistence pattern as every other SirisOS record store. Reachable from More → Siris, which previously showed only a "planned for later" placeholder.

Cross-object traversal (e.g. Project → calculation → standard → SirisHydro question → decision) and automatic capture from SirisAI conversations remain future work — v1 is deliberately just the record store and manual-entry UI. ADR 061.

### Universal Command Palette

Cmd+K / Ctrl+K opens a lightweight dialog overlay from any screen, reusing the global search endpoint (ADR 062) rather than a new search implementation — arrow-key highlight navigation, Enter to open the highlighted result, Escape to close, click/tap to navigate. The desktop sidebar's "Search" entry opens the palette directly (with a `⌘K` hint); the full-screen `GlobalSearchScreen` remains the mobile Quick Actions entry point, where a dialog is a worse fit than dedicated touch targets. ADR 063.

### Recommendation Engine v1

Deterministic Observation → Recommendation → Evidence pipeline: `GET /api/v1/recommendations` maps the existing `GET /api/v1/homelab/alerts` output 1:1 into Recommendation records (title, rationale, severity, evidence source/id, a free-text suggested next step), reconciled against an atomic-JSON store so a pending/dismissed/acted status survives across polls, and self-pruning — a recommendation disappears once its underlying alert clears rather than lingering forever. Surfaced as a new panel in Operations Center. The original plan was to evaluate the client-side Incident Engine/Notification Policy engine, but neither has any backend representation to read from; v1 deliberately scopes to the real, already-deterministic `homelab_alerts` endpoint instead. ADR 064.

### Action Framework v1

Server-side capability registry (`GET /api/v1/actions`, `POST /api/v1/actions/{capability_id}/execute`) binding stable capability IDs — `docker.start`/`stop`/`restart` — to the execution primitives that already existed and were already audited (`DockerMonitor.action()`). Medium-risk capabilities require the caller to explicitly set `confirm: true`; the server rejects execution without it rather than trusting a client-side dialog alone. The Flutter `SirisCapabilityRegistry` (ADR 030) stays discovery-only and unconnected to this for now — wiring a Recommendation's suggested action to a real capability, and bringing Home Assistant control into the registry, are both deliberately deferred rather than guessed at under time pressure. Also fixed along the way: Home Assistant device-control actions previously executed with zero audit trail; they now record an activity event on every outcome, matching the pattern Docker actions already had. ADR 065.

Planned automation stack:

- Structured provenance (typed source object reference, confidence) and cross-object traversal for Siris Memory
- Palette results blending live state, related Knowledge/Projects and available actions per query; contextual "Ask Siris" on individual objects
- Siris Inbox — a unified attention/decision queue distinct from Operations Center and Notification Policies
- Extend Recommendation sources beyond `homelab_alerts` once Incidents/Notification Policies have a real backend representation
- Wire a Recommendation's suggested action to a specific capability ID; bring Home Assistant control into the capability registry
- Playbook Engine
- Context-aware recommendations
- n8n integration
- Event-driven Siris Automations
- Shared approval/audit policy

## Sprint 0.9 — SirisRun & SirisGym Intelligence

Running and Gym have been fully shipped, DB-backed modules (session logging, per-exercise PR rollups, workout templates, an EWMA running fitness trend) since early in the project, but never had a roadmap section — see `docs/roadmap.md` for the full incorporated brainstorm and sequencing. The signature goal is running, lifting, recovery and schedule informing each other rather than living in silos: general fitness apps already have great loggers; the differentiator is something like "your last five interval sessions performed best when they were at least 48 hours after legs, so I've moved Thursday's run to Friday."

One real gap found while auditing the existing modules before starting: the workout form's progressive-overload suggestion (+2.5 kg when the last session hit target reps at RIR ≥ 2) was a **client-side-only** Dart heuristic with no backend representation, no persistence, and no handling for a struggled previous session — the same category of gap already found and fixed twice this sprint (Recommendation Engine, Action Framework).

### Automatic Progressive Overload v1

`GET /api/v1/gym/exercises/{exercise_name}/suggestion` reasons deterministically from an exercise's own most recent session (reps trend + minimum RIR, grouped by workout) to suggest either `+2.5 kg` after a comfortable session or repeating the same weight after a struggled one, with the evidence stated in the response. Replaces the client-only heuristic in the workout form's template prefill, and adds a "Next session suggestion" card to the Exercise Intelligence detail page so ad-hoc (non-template) workouts get the same suggestion. Known v1 limitation, stated rather than engineered around: it assumes straight-set training at a consistent weight per session — a pyramid session would read as "struggled" today. ADR 066.

### Personal Records v1

`POST /api/v1/gym/workouts` now detects, at the moment a workout is saved, whether it beat a prior best for any exercise — heaviest weight, best estimated 1RM and best set volume are checked independently, snapshotted before insertion so a set is never compared against itself and multiple sets of one exercise only report the session's single best per record type. Each new record fires an `ActivityService` event and an understated in-app callout, closing the same "the data already knows this, nothing ever says it" gap found and fixed twice already this sprint. Running PR tracking is explicitly separate future work. ADR 067.

## Long-term pillars

- **Personal OS:** health, sleep, recovery, running, gym, calendar
- **HomeLab OS:** Docker, Home Assistant, Prometheus/Grafana, UniFi, Synology, backups, UPS, Plex
- **Engineer OS:** SirisHydro, SirisPM, calculators, standards, projects, Civil 3D
- **Knowledge OS:** Obsidian, documents, search, metadata, semantic memory
- **Intelligence OS:** Context, Memory, Knowledge Graph, Planner, SirisAI, Hermes, Ollama
- **Automation OS:** capabilities, actions, playbooks, schedules, triggers, workflows, approvals, Inbox

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
25. SirisHydro source-supported claims must cite document/reference/edition/page evidence wherever possible and must not invent missing authority requirements.
26. Standards document IDs are immutable evidence identities; replacements create linked new revisions rather than overwriting historical source material.
27. Semantic/vector retrieval may improve recall but must preserve exact page provenance and a deterministic lexical fallback.
28. Pull requests should pass backend, Flutter and production-container CI before merge unless an explicit emergency hotfix is required.
29. Production Flutter uses same-origin API routing through the unified `sirisos` container; do not reintroduce a host-specific compiled API URL without an explicit deployment reason.
30. Knowledge vault access remains read-only until an explicit write/editing design is approved; ambiguous wikilinks must not be silently resolved.
31. Provenance is a SirisOS-wide UX standard, not one feature's behavior: any AI-adjacent claim (recommendation, projection, Briefing sentence, Memory-derived answer) should expose a "Why?" affordance to its underlying evidence/data/confidence.
32. App-wide keyboard shortcuts must use `HardwareKeyboard.instance.addHandler`, not `CallbackShortcuts`/`Focus.onKeyEvent` — the latter only fires when a subtree descendant holds focus and silently does nothing otherwise (ADR 063).

## Local endpoints

- SirisOS UI: `http://192.168.0.100:6464`
- Mission Control: `http://192.168.0.100:6464/#/mission`
- Operations Center: `http://192.168.0.100:6464/#/operations`
- API base: `http://192.168.0.100:6464/api`
- API docs: `http://192.168.0.100:6464/docs`
- History API: `http://192.168.0.100:6464/api/v1/history`
- Backup Protection API: `http://192.168.0.100:6464/api/v1/history/backup-protection`
- Engineering Standards API: `http://192.168.0.100:6464/api/v1/engineering/standards`
- SirisHydro Evidence API: `http://192.168.0.100:6464/api/v1/engineering/sirishydro/evidence`
- Knowledge API: `http://192.168.0.100:6464/api/v1/knowledge`

Useful commands:

```bash
make up
make dev
make backend
make rebuild-app
make status
make logs
make restart
make stop
make clean
```

Runtime state is stored under `data/`. Back up `data/` and `.env` to preserve the installation, including uploaded private engineering standards, historical revisions and the default local knowledge vault.
