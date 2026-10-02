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
- [x] CMP Capabilities: service login and `stats/me` widget
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
- [x] Existing project links to knowledge notes stay listed; new ones are refused

### Phase 5: Deploy (on the LAN)
- [x] `SIRISOS_PORT` (default 8094) wired through compose, Makefile and scripts
- [ ] Pick up the new port on the server
- [ ] Create service accounts: APD PM VIEWER, CMP user, Archive read key
- [ ] Verify every connector against the live apps on `192.168.0.100`

## After the rebuild

- Widgets you can configure and rearrange on the home screen.
- Notifications aggregated from every app (SirisAI events, Archive review
  queue, APD PM overdue tasks).
- A command palette that searches across apps (Second Brain, APD PM search,
  Archive search).
- More widgets for Neo Server and media apps, if they expose an API that's
  reachable from the server.
- SirisHydro answer synthesis routed through SirisAI's model router instead
  of SirisOS's own Ollama call.
