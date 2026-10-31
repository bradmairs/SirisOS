# SirisOS Roadmap

SirisOS is the hub for the Siris family of apps (ADR 106). The pre-hub
roadmap, Sprints 0.4 to 1.0, is archived in
[`history/roadmap-v0.md`](history/roadmap-v0.md).

## Product philosophy: complement, not replace

- If another Siris app or Brad's preferred app owns a domain, SirisOS links
  to it, monitors it and surfaces its data. SirisOS does not rebuild it.
- SirisAI is the only assistant and Siris is the only notes store.
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
- [x] SirisAI + Siris: status, HUD widget, chat SSE passthrough, conversations, brain search/capture/today
- [x] APD PM: service login, project and due-task widget
- [x] Engineering Reviewer: health (LLM availability) and recent-reviews widget
- [x] Engineering Archive: `/api/external/status` widget (review queue, totals)
- [x] ~~GVW Timesheets: health and version~~ (removed in 1.31)
- [x] ~~CMP Capabilities: service login and `stats/me` widget~~ (removed 2026-10-04: work-only)
- [x] SirisDrone: library and export-queue widget
- [x] ~~Helmarr, JEFIT and Neo Server launch tiles~~ (removed in 1.31)
- [x] Tests against mocked HTTP for every connector

### Phase 2: Liquid Glass PWA shell ✅
- [x] `apps/web` (Vite + React + TS); Docker build stage and CI job
- [x] Glass design system: materials, specular edges, dock, sheets, light/dark, reduced-transparency fallback
- [x] Login, home screen (tiles and widgets), app detail sheet
- [x] Assistant sheet streaming from SirisAI, with tool-confirmation flow
- [x] Siris search and quick capture
- [x] PWA manifest and icons (installable on iPhone)

### Phase 3: Engineering module in React ✅
- [x] SirisHydro (evidence, synthesis status, history)
- [x] Calculator library
- [x] Standards Library (upload and search)
- [x] Projects (with calculations and citations)

### Phase 4: Removal ✅
- [x] Delete the Flutter app (`apps/mobile`)
- [x] Delete the backend modules superseded by SirisAI, Siris, JEFIT and Neo Server (ADR 106 §4), their tests, and the docker-proxy and node-exporter containers
- [x] Leave their Postgres tables in place: the container stays defined, and SirisOS no longer depends on it
- [x] Export the pre-hub Postgres and remove the container (3 October 2026; the dump is kept on the server)
- [x] Existing project links to knowledge notes stay listed; new ones are refused

### Phase 5: Deploy (on the LAN)
- [x] `SIRISOS_PORT` (default 8094) wired through compose, Makefile and scripts
- [x] `make hub-check` checks every connector against the live apps; checklist in [`deploy-hub.md`](deploy-hub.md)
- [ ] Pick up the new port on the server
- [ ] Create service accounts: APD PM VIEWER, Archive read key
- [ ] Verify every connector against the live apps on `192.168.0.100` (`make verify` does it in one go, 2.61)

## Performance ✅ (ADR 107)
- [x] Static wallpaper (no animated blur under the glass); compositor-only orb glow; no permanent GPU layers
- [x] Shared stale-while-revalidate data cache: one request per key across screens, instant revisits, background-paused polling
- [x] Lazy screens with idle prefetch, separate React chunk, gzip
- [x] Chat streaming batched per frame; memoised bubbles
- [x] API: OCR/search/SirisHydro off the event loop, parsed-index cache, pooled hub client, request coalescing, stale-while-revalidate, parallel status + widget

## Siris linking ✅ (October 2026)
- [x] Confident pairs are linked automatically: the threshold starts at 80% and calibrates itself from your link and not-related decisions (Siris-Second-Brain `autolink`, run in SirisAI's nightly upkeep or with "Link now")
- [x] "Could be linked" lists only the unsure pairs, with a confidence
- [x] "Linked automatically" panel to review and undo recent auto links
- [x] Done button on "Coming up" (tick a task or finish a project), and long lists collapse to 3
- [x] Unlink any connection from a note's Connections in Brain search; the pair is never auto-linked again

## Daily brief ✅ (ADR 108)
- [x] `GET /api/v1/brief`: weather, schedule, tasks, to-dos, email, home, health, apps needing a look and Siris, from SirisAI's read-only tools, insights and the hub
- [x] News for Brad: topics from the "Daily Briefing Preferences" note, ranked by the interests linked from his notes (Google News + ABC RSS)
- [x] Opens by itself 4–9 am until closed; dismissal is shared across devices; `/brief` any time
- [ ] Check the news feeds and tool sections against the live server

## Search everything ✅ (ADR 109)
- [x] ⌘K / Ctrl+K palette: screens and calculators instantly; apps, home-screen widgets, links, Siris, SirisAI chats, APD PM, Engineering Archive, Reviewer, Standards, projects and SirisHydro from `/api/v1/search`
- [x] Connector `search()` contract; per-source timeout, failures listed
- [x] Deep links: `/assistant?c=`, `/brain?q=`, `/engineering/standards?q=`, `/engineering/hydro?q=`
- [ ] Check APD PM and Archive search against the live apps

## SirisAI integration v1 ✅ (ADR 110)
- [x] SirisAI's hub contract (`/siris/hub/v1`): schema and examples copied in, tested here; 404 falls back to the old calls
- [x] Daily brief from one contract call (fixed "70.0% chance of rain" on the way)
- [x] Search: Siris, chats and memories from one SirisAI call
- [x] Inbox: SirisAI's attention feed (alerts, approvals, suggestions, reviews) + apps down, APD PM overdue, Archive queue; live stream; server-side dismissals
- [x] Home: protocols with preview, confirm and undo; cameras with "What's there?"; car; power; parcels
- [x] Guest mode hides personal widgets and brief sections
- [x] `X-Siris-Client` on every SirisAI call; opt-in `SIRISAI_USER`
- [x] SirisAI's service key opens only the read/compute routes
- [x] Calculators server-side, with 50 parity cases shared by both suites
- [x] SirisHydro synthesis through SirisAI's model router (own Ollama as fallback)
- [ ] Set `SIRISOS_SERVICE_KEY` / `SIRISAI_SIRISOS_SERVICE_KEY` on the server and check SirisAI's engineering tools live

## Career ✅ (ADR 111)
- [x] Career tab: overview, CPD, pathways (EA membership, CPEng, NER, Victorian registration), Stage 2 competency evidence, goals
- [x] CPD imported from Engineers Australia's export (CSV or Excel), re-importable without duplicates; rolling 3-year totals against the 150-hour requirement and its minimums
- [x] Home widget, daily brief card, search results
- [ ] Check the importer against a real Engineers Australia export (`make verify EA=export.csv`, 2.61)
- [x] SirisAI tools `career_cpd_status` and `career_chartership_status`, through the read-only service key
- [x] Phone dock: five items, with Career in place of Engineering
- [x] Draft competency claims from tagged evidence into Siris (1.7)

## SirisLearn ✅ (ADR 112)
- [x] SirisLearn connector: status and the Learning widget (streak, XP today, level, courses, next lesson, new awards)
- [x] SirisLearn courses and lessons in search
- [x] Inbox: "your learning streak ends at midnight" while today's quiz isn't done
- [ ] Set `SIRISLEARN_URL` / `SIRISLEARN_HUB_KEY` on the server and check the tile live

## After the rebuild

- [x] Widgets you can configure and rearrange on the home screen (1.4)

## Daily staples (2.9 onwards)

- [x] Tasks: one list from SirisOS, Siris notes and SirisAI reminders; plain-words entry, repeats, snooze, push at a time (2.9)
- [x] Evening wrap-up: today, CPD from meetings, tomorrow's top 3 into the brief, a journal line (3.0)
- [x] Home that changes through the day: morning, work, weekend, evening (3.1)
- [x] Meeting prep: people, Siris notes, latest emails, related tasks; notes into Siris with actions as tasks; 10-minute heads-up (3.2)
- [x] Email triage: SirisAI's drafted replies, edit and send, snooze, leave (3.3)
- [x] Terminal shortcuts: one-tap commands behind a fresh code, output inline (3.4)
- [x] Weekly review: the week in numbers, quiet projects, next week's crunch points, what matters (3.5)
- [x] iPhone home-screen widget (Scriptable), fitness card, backups/updates/certificates on System status (3.6)
- [x] Nightly backups of SirisOS's own data, with download and undoable restore on System status (3.7)
- [x] Notifications with buttons: Done, In an hour, Approve, Snooze; a one-tap page on iPhone (3.8)
- [x] Access from here: test SirisOS from wherever the phone is, with fixes in plain words (3.9)
- [x] Projects: one page per Siris project with its tasks, meetings, emails and links (4.0)
- [x] Your year: CPD, running, tasks done, journal days and Inbox load, month by month (4.1)
- [x] Home controls: lights, garage, locks and scenes on Home, with a yes first for the garage and unlocking (4.2)
- [x] Talk to SirisOS: tasks, what's on, CPD reminders and notes by voice; anything else to SirisAI (4.3)
- [x] Yearly goals on Your year; tasks only your own; personal projects only; wrap-up as memories; Meetings, Email, iPhone shortcuts and This week archived (4.4)
- [x] Smart home: the house in 3D, floor by floor, with every network device in its room and live UniFi traffic flowing along neuron-style links (4.5)
- [x] Smart home: devices as small models of themselves, grouped when close, dragged to where they really are; the floor plan corrected (4.7)
- [x] Home: times of day you set (work 8:30–4:30 on weekdays), section order per part of the day, protocols only when you're home (4.8)
- [x] Home through the day: what each part of the day shows, wind down from 8 pm, work and personal tasks, welcome home (4.9)
- [x] Chartered application in Career: the self-reflection, the CPD questionnaire and the Building Industry Assessment, with a readiness checklist feeding next steps and a yearly goal (4.6)
- [x] From your notes: one older Siris note a day on Home, related to your projects, tasks and calendar (5.1)
- [x] Home maintenance: repeating jobs and appliances (manuals, warranties) in the house's rooms, due rooms glowing, on Home and as notifications with Done (5.2)
- [x] Network alerts: a notification when an unknown device joins (It's mine or Block it) or a watched one drops off, through SirisAI and UniFi (5.3)
- [x] Power use: rooms in the house lit by what they draw, a Power card with today's kWh, and kWh by month on Your year (5.4)
- [x] Training: a race plan from your recent running, today's run adjusted for sleep and recovery, a subscribed calendar; Apple Health arriving on its own through Health Auto Export (5.5)
- [x] Setup checklist on System status: every integration tested live, on, off or needing a look, with the fix and the setting names (5.6)
- [x] Health: readiness from HRV, resting heart rate, sleep and vitals against your own normal; sleep, training load and vitals; readiness leads the morning brief (5.7)
5.81: phone fixes: server rings sized again, dock kept at the bottom, iPhone push accepted (VAPID subject)

## Terminal (ADR 113)

- [x] A shell on a home machine over SSH, behind a fresh 2FA code each session (2.8)
- [ ] Set `SIRISOS_TERMINAL_HOSTS` on the server, add the `make terminal-key` key to `authorized_keys`, set up 2FA
