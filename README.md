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

## Health Data Export REST ingestion

Canonical Apple Health ingestion is a dedicated REST endpoint pushed to by the
[Health Auto Export](https://www.healthyapps.dev/) iPhone app. The earlier MCP
scaffold (`HEALTH_AUTO_EXPORT_MCP_URL`/`HEALTH_AUTO_EXPORT_MCP_TOKEN`) remains
available for interactive/debug queries, but it depends on Health Auto Export
staying foregrounded and is not the source of truth.

Flow:

```text
Apple Health
   ↓
Health Auto Export
   ↓ HTTPS POST, bearer token
POST /api/v1/health/ingest
   ↓
health_metric_samples / health_workouts (Postgres)
   ↓
Health module / Context / Briefing / Siris Score / SirisAI
```

- `POST /api/v1/health/ingest` — authenticated with `SIRISOS_HEALTH_INGEST_TOKEN`
  (not the SirisOS admin login), accepts Health Auto Export's JSON export v2
  body for both the Health Metrics and Workouts automation types, and reads
  Health Auto Export's `automation-id`/`automation-name`/`session-id` headers
  for provenance. Fails closed with 401 when the token is missing, wrong, or
  not configured.
- Metric samples are deduplicated on a deterministic key
  (`metric + timestamp + source + value + unit`), so re-sending the same
  rolling window is a no-op; a revised value lands as a new sample rather than
  silently overwriting history.
- Workouts are upserted by Health Auto Export's workout id, so an amended
  workout (e.g. heart-rate data finishing processing) replaces the earlier row.
- `GET /api/v1/health/status` (SirisOS admin session) reports `last_sync`,
  `records_received` and `last_error` for a quick health check of the pipeline.
- Generate the ingest token with `openssl rand -hex 32` and set it as
  `SIRISOS_HEALTH_INGEST_TOKEN` — see `.env.example`.

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

Server-side capability registry (`GET /api/v1/actions`, `POST /api/v1/actions/{capability_id}/execute`) binding stable capability IDs — `docker.start`/`stop`/`restart` — to the execution primitives that already existed and were already audited (`DockerMonitor.action()`). Medium-risk capabilities require the caller to explicitly set `confirm: true`; the server rejects execution without it rather than trusting a client-side dialog alone. Also fixed along the way: Home Assistant device-control actions previously executed with zero audit trail; they now record an activity event on every outcome, matching the pattern Docker actions already had. ADR 065.

### Recommendation → Action wiring

A Recommendation's `capability_id`/`capability_params` are now populated for the alert shapes that have a real registered capability behind them — `container-*-stopped` → `docker.start`, `container-*-unhealthy` → `docker.restart` — giving those recommendations a "Run" button in Operations Center instead of just descriptive text. Running it calls the same audited `/api/v1/actions/{id}/execute` endpoint Action Framework v1 already built, then auto-marks the recommendation acted on success. Every other recommendation (host resource alerts, `docker-unavailable`, image updates) stays descriptive-only, since no capability exists for them — nothing is force-fit. The Flutter `SirisCapabilityRegistry` (ADR 030) is still separate/discovery-only; this wiring goes through the backend registry directly. ADR 068.

Planned automation stack:

- Structured provenance (typed source object reference, confidence) and cross-object traversal for Siris Memory
- Palette results blending live state, related Knowledge/Projects and available actions per query; contextual "Ask Siris" on individual objects
- Siris Inbox — a unified attention/decision queue distinct from Operations Center and Notification Policies
- Extend Recommendation sources beyond `homelab_alerts` once Incidents/Notification Policies have a real backend representation
- Bring Home Assistant control into the capability registry
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

### Automatic Deload Detection v1

`GET /api/v1/gym/exercises/{exercise_name}/deload` reasons over an exercise's last 3 logged sessions and recommends a deload only when three signals -- declining estimated 1RM, falling first-set reps, and rising RIR-implied effort -- each show a genuine, non-bouncing decline across all three (a dip-then-recovery session never triggers it). Falls back to just e1RM + reps when RIR wasn't recorded for one of the sessions. Surfaced as an understated card on the Exercise Intelligence page, in the app's error-container color to visually distinguish it from the neutral Progressive Overload suggestion above it -- and, matching that card's own restraint, it renders nothing at all unless a deload is actually recommended. Confirmed scope decision: per-exercise (like Progressive Overload), not a whole-training-week signal, and deliberately strict/rare over chatty. Verified live: three sessions with genuinely declining weight/reps/RIR produced the expected card with the correct rationale. ADR 078.

### Running Personal Records v1

Gym Personal Records (ADR 067) explicitly deferred running: `RunRecord` captures distance, pace and heart rate but no GPS/splits/elevation, so several of the roadmap's own named sub-items (fastest splits, best negative split, highest-elevation week) genuinely can't be built without fabricating evidence. Confirmed scope: build only what's real. `POST /api/v1/running` now detects, at the moment a run is saved, whether it's the longest run ever logged, or whether its heart rate is lower than any prior run at a comparable pace (within 15 sec/km) -- the running equivalent of Gym's estimated-1RM record, a "same effort, less strain" fitness signal. Both reuse the exact same snapshot-before-insert discipline and `🏆 New record` callout Gym Personal Records already established. Verified live: a 5km run at 5:00/km (160 bpm) followed by an 8km run at a comparable 5:05/km pace but a lower 150 bpm correctly fired both records at once. ADR 079.

### Weekly Training Load v1

`GET /api/v1/training/weekly-load` combines running and gym into one weekly number for the first time — each modality's weekly total (running `effort_score` sum, gym `total_volume_kg` sum) is expressed as a percentage of the athlete's own trailing 8-week baseline, then summed into a `combined_index` where 100 means "a typical week." No arbitrary unit-conversion constant was needed: percentages of your own history are inherently comparable across modalities. Baseline weeks that predate a modality's first-ever logged record don't count (they're not real "zero" weeks), and at least 2 qualifying baseline weeks are required before a ratio is shown at all — a new user sees an honest "not enough training history yet" rather than a distorted number. Shown as a shared `TrainingLoadCard` on both the Gym and Running screens. ADR 069.

### Siris Coach v1

Coach is now a genuinely first-class navigation destination — not a card bolted onto Gym or Running. `GET /api/v1/coach/weekly-report` composes `RunningService`, `GymService` and `TrainingLoadService` into one deterministic weekly report: week-over-week deltas for running distance/count and gym volume/session count (`null` rather than a misleading delta when there's no prior week to compare against), a retroactive per-record-type "new bests this week" check (the same independent weight/estimated-1RM/set-volume comparison Personal Records already does at save time, ADR 067), and the existing weekly training load assessment — all folded into one headline sentence, e.g. *"New best on Bench Press. Heavier than your typical week."* When nothing notable happened, the headline just says so, matching the brainstorm's own design principle that Coach shouldn't manufacture advice to fill space. "Today" (a recovery-based readiness/recommendation view) and Ollama narrative synthesis on top of the deterministic facts are both explicitly deferred — the former needs the still-unbuilt Health summary API and a planned/scheduled session to react to; the latter was a scope decision confirmed before starting, to ship the deterministic core first the same way Progressive Overload and Personal Records did. ADR 070.

### Ask Siris Training Queries v1

An "Ask Siris" card on the Coach screen answers free-text training questions ("What's my best 5K this year?", "How much has my bench press improved since 2026-01-01?") through `GET /api/v1/coach/ask`. Unlike SirisHydro's document-ranking retrieval (which doesn't apply here — training data is structured, not text to search), `AskSirisService` uses deterministic pattern matching: a fixed set of recognized question shapes, each routed by keyword/regex to the exact `RunningService`/`GymService`/`CoachService` call that answers it. Ollama, reusing the same `chat_client` from ADR 057 unmodified, is only ever given an already-correct deterministic answer to rephrase more naturally — it never extracts or infers facts, and `synthesized_answer` stays `null` (deterministic answer shown as-is) whenever Ollama is unconfigured or unreachable, the same fail-open contract as SirisHydro. A question outside the recognized set, or naming an exercise never actually logged, gets an honest "I don't recognise that question yet" with clickable example suggestions rather than a guess. Muscle-group and sleep-correlation questions are out of scope — they need data (exercise taxonomy, the Health summary API) that doesn't exist yet. ADR 071.

### Health Summary API v1

Health Auto Export ingestion (previous PR) was write-only until now — `GET /api/v1/health/status` only ever reported sync metadata, never the actual HRV/resting-HR/sleep values. `GET /api/v1/health/summary` closes that gap: for every metric type actually present in the ingested data (generic, not hardcoded to specific metrics), it returns the latest reading plus a trailing 14-day baseline ratio — the same "latest as a percentage of your own recent history" pattern `TrainingLoadService` already uses for weekly load, gated behind a minimum-sample floor so a metric with too little history returns `null` rather than a distorted number. Surfaced as a "Recovery vs your baseline" section on the Health screen. This was the one concrete prerequisite blocking Training Conflict Detection, Run Readiness and the Smart Weekly Planner — none of those can reason about "is today different from usual" without it. Event Bus refresh (live push on new sync) remains a separate, still-open item. ADR 072.

### Training Conflict Detection v1

A "Today" card at the top of the Coach screen — above the weekly report, matching the brainstorm's own mockup ordering — flags when HRV or resting heart rate is notably worse than your trailing baseline (`GET /api/v1/health/summary`, ADR 072) on a day you also logged a workout or run. This is the recovery-based reading of "training conflict," chosen over the brainstorm's literal sequencing example (heavy-leg-day-before-intervals) because it's the actual dependency the roadmap names for this feature and needs zero new inference heuristics — just the Health Summary API's numbers compared against a fixed threshold. A subtlety worth calling out: the health summary's "latest" reading is global, not scoped to a particular day, so `TrainingConflictService` explicitly checks the reading's own date matches before treating it as "today's" signal — a stale sync (no data yet for today) correctly reports "not enough data" rather than silently using an old reading. Reduced recovery on a day nothing was trained is reported as a neutral status, not a conflict — there's nothing to warn about if you're already resting. `GET /api/v1/coach/conflict-check`. ADR 073.

### Gamification: Achievements v1

An "Achievements" card on the Coach screen shows 8 concrete, evidence-backed milestones — 100 kg club on bench/squat/deadlift/overhead press, a Million Kilo Club for lifetime lifted volume, a sub-25 5K badge, an 8-consecutive-week training-consistency streak, and a 5-consecutive-session progressive-overload streak — each a real recorded fact crossing a real threshold, never an invented point total. Locked achievements still show progress toward the next unlock (e.g. "70 / 100 kg"). `GET /api/v1/coach/achievements`. The brainstorm's companion idea, a composite "Training Level" score, was deliberately deferred rather than built alongside this: unlike every other number in this app (always expressed relative to the athlete's own history), a "Strength" sub-score has no defensible basis without bodyweight or strength-standards data SirisOS doesn't have — building one now would be this app's first fabricated, non-evidence-based number. ADR 074.

### Health Event Bus Refresh v1

The Health and Coach screens now refresh automatically when new Health Auto Export data lands, closing the last item under Health Data Export ingestion. Since Health Auto Export POSTs directly to the backend from the iPhone automation — no open Flutter session is involved in that request, and this app has no backend-push mechanism anywhere (confirmed: no WebSocket/SSE endpoint exists) — a client-side `SirisEventBus` publish had nothing to hook onto. `HealthSyncWatcher` instead polls the existing `GET /api/v1/health/status` every 5 minutes (the same poll-then-publish pattern `SirisIntegrationManager` already uses for its own connectors) and publishes `ModuleDataChanged(moduleId: 'health')` only when `last_sync`/`records_received` actually change — the first poll after app start silently establishes a baseline rather than firing a spurious refresh on launch. ADR 075.

### iOS Platform Target v1

SirisOS is intended to eventually ship as a native iOS app rather than only Flutter web, so `apps/mobile/ios/` now exists (`flutter create --platforms=ios .`), with `IPHONEOS_DEPLOYMENT_TARGET` raised to 16.0 to match the local Xcode toolchain. Verified end-to-end: `flutter run` builds, code-signs, installs and launches SirisOS on the iOS Simulator, reaching the real sign-in screen. Getting there surfaced a genuine environment issue worth recording — `codesign` reliably rejected the build with a "resource fork, Finder information... not allowed" error while the project lived under `~/Documents`. Root cause: macOS's File Provider extension (used by iCloud Drive's "Desktop & Documents Folders" sync) tags synced files/directories with `com.apple.FinderInfo` and `com.apple.fileprovider.fpfs#P`, and that combination is what `codesign` rejects — also explaining earlier flakiness, since the sync daemon kept re-applying the attributes after they were manually cleared. Fix: the git worktree was relocated (via `git worktree move`, not a plain file copy) to `~/dev/sirisos-worktrees/next-slice`, outside any iCloud-synced folder. Any future iOS-development clone of this repo needs to live outside a File-Provider-managed directory on macOS for the same reason. ADR 076.

### iOS Sign-In UI Test v1

Building on ADR 076, the sign-in flow itself is now verified interactively, not just visually. Claude Code's built-in iOS Simulator control tool turned out to be running in a disabled state on this machine, so a standard Apple `XCUITest` target (`RunnerUITests`) was added instead — it launches the app, fills in the sign-in form and submits it via `xcodebuild test`, independent of any third-party tooling. Getting it passing surfaced two real quirks worth recording: Flutter's `obscureText` fields don't expose as `XCUIElementTypeSecureTextField` on this iOS version (found only via a broad accessibility-descendant predicate), and the username field arrives pre-filled from a prior session, so the test clears it before typing. Verified against the real backend — the test's submission produced an actual `POST /api/v1/auth/login` → `200 OK` followed by the app's normal authenticated dashboard requests. ADR 077.

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
