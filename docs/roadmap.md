# SirisOS Roadmap

SirisOS is the hub for the Siris family of apps (ADR 106). The pre-hub
roadmap, Sprints 0.4 to 1.0, is archived in
[`history/roadmap-v0.md`](history/roadmap-v0.md).

## Product philosophy: complement, not replace

- If another Siris app or Brad's preferred app owns a domain, SirisOS links
  to it, monitors it and surfaces its data. SirisOS does not rebuild it.
- SirisAI is the only assistant and Second Brain is the only notes store.
  SirisOS has no LLM, agent or memory of its own.
- Engineering tools (SirisHydro, calculators, Standards, Projects) stay
  native in SirisOS, because nothing else owns them.
- Provenance is part of the UX. Every widget names the app its data came
  from and links back to it.

## Hub rebuild (October 2026)

### Phase 0: Architecture ✅
- [x] ADR 106: SirisOS is the hub, plus the connector contract, removals and port
- [x] README and roadmap rewritten; pre-hub docs archived

### Phase 1: Connector gateway ✅
- [x] Connector contract, registry, concurrent status with per-connector timeout and cache
- [x] SirisAI + Second Brain: status, HUD widget, chat SSE passthrough, conversations, brain search/capture/today
- [x] APD PM: service login, project and due-task widget
- [x] Engineering Reviewer: health (LLM availability) and recent-reviews widget
- [x] Engineering Archive: `/api/external/status` widget (review queue, totals)
- [x] GVW Timesheets: health and version
- [x] ~~CMP Capabilities: service login and `stats/me` widget~~ (removed 2026-10-04: work-only)
- [x] SirisDrone: library and export-queue widget
- [x] Helmarr, JEFIT and Neo Server launch tiles
- [x] Tests against mocked HTTP for every connector

### Phase 2: Liquid Glass PWA shell ✅
- [x] `apps/web` (Vite + React + TS); Docker build stage and CI job
- [x] Glass design system: materials, specular edges, dock, sheets, light/dark, reduced-transparency fallback
- [x] Login, home screen (tiles and widgets), app detail sheet
- [x] Assistant sheet streaming from SirisAI, with tool-confirmation flow
- [x] Second Brain search and quick capture
- [x] PWA manifest and icons (installable on iPhone)

### Phase 3: Engineering module in React ✅
- [x] SirisHydro (evidence, synthesis status, history)
- [x] Calculator library
- [x] Standards Library (upload and search)
- [x] Projects (with calculations and citations)

### Phase 4: Removal ✅
- [x] Delete the Flutter app (`apps/mobile`)
- [x] Delete the backend modules superseded by SirisAI, Second Brain, JEFIT and Neo Server (ADR 106 §4), their tests, and the docker-proxy and node-exporter containers
- [x] Leave their Postgres tables in place: the container stays defined, and SirisOS no longer depends on it
- [x] Export the pre-hub Postgres and remove the container (3 October 2026; the dump is kept on the server)
- [x] Existing project links to knowledge notes stay listed; new ones are refused

### Phase 5: Deploy (on the LAN)
- [x] `SIRISOS_PORT` (default 8094) wired through compose, Makefile and scripts
- [x] `make hub-check` checks every connector against the live apps; checklist in [`deploy-hub.md`](deploy-hub.md)
- [ ] Pick up the new port on the server
- [ ] Create service accounts: APD PM VIEWER, Archive read key
- [ ] Verify every connector against the live apps on `192.168.0.100`

## Performance ✅ (ADR 107)
- [x] Static wallpaper (no animated blur under the glass); compositor-only orb glow; no permanent GPU layers
- [x] Shared stale-while-revalidate data cache: one request per key across screens, instant revisits, background-paused polling
- [x] Lazy screens with idle prefetch, separate React chunk, gzip
- [x] Chat streaming batched per frame; memoised bubbles
- [x] API: OCR/search/SirisHydro off the event loop, parsed-index cache, pooled hub client, request coalescing, stale-while-revalidate, parallel status + widget

## Second Brain linking ✅ (October 2026)
- [x] Confident pairs are linked automatically: the threshold starts at 80% and calibrates itself from your link and not-related decisions (Siris-Second-Brain `autolink`, run in SirisAI's nightly upkeep or with "Link now")
- [x] "Could be linked" lists only the unsure pairs, with a confidence
- [x] "Linked automatically" panel to review and undo recent auto links
- [x] Unlink any connection from a note's Connections in Brain search; the pair is never auto-linked again

## Daily brief ✅ (ADR 108)
- [x] `GET /api/v1/brief`: weather, schedule, tasks, to-dos, email, home, health, apps needing a look and the Second Brain, from SirisAI's read-only tools, insights and the hub
- [x] News for Brad: topics from the "Daily Briefing Preferences" note, ranked by the interests linked from his notes (Google News + ABC RSS)
- [x] Opens by itself 4–9 am until closed; dismissal is shared across devices; `/brief` any time
- [ ] Check the news feeds and tool sections against the live server

## Search everything ✅ (ADR 109)
- [x] ⌘K / Ctrl+K palette: screens and calculators instantly; apps, home-screen widgets, links, Second Brain, Siris chats, APD PM, Engineering Archive, Reviewer, Standards, projects and SirisHydro from `/api/v1/search`
- [x] Connector `search()` contract; per-source timeout, failures listed
- [x] Deep links: `/assistant?c=`, `/brain?q=`, `/engineering/standards?q=`, `/engineering/hydro?q=`
- [ ] Check APD PM and Archive search against the live apps

## Career ✅ (ADR 110)
- [x] Career tab: overview, CPD, pathways (EA membership, CPEng, NER, Victorian registration), Stage 2 competency evidence, goals
- [x] CPD imported from Engineers Australia's export (CSV or Excel), re-importable without duplicates; rolling 3-year totals against the 150-hour requirement and its minimums
- [x] Home widget, daily brief card, search results
- [ ] Check the importer against a real Engineers Australia export
- [ ] SirisAI tool: CPD status and next chartership step in chat
- [ ] Draft competency claims from tagged evidence into the Second Brain

## After the rebuild

- Widgets you can configure and rearrange on the home screen.
- Notifications aggregated from every app (SirisAI events, Archive review
  queue, APD PM overdue tasks).
- More widgets for Neo Server and media apps, if they expose an API that's
  reachable from the server.
- SirisHydro answer synthesis routed through SirisAI's model router instead
  of SirisOS's own Ollama call.
