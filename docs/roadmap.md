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
- [ ] Verify every connector against the live apps on `192.168.0.100` (`make verify` does it in one go, 1.15.1)

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
- [ ] Check the importer against a real Engineers Australia export (`make verify EA=export.csv`, 1.15.1)
- [x] SirisAI tools `career_cpd_status` and `career_chartership_status`, through the read-only service key
- [x] Phone dock: five items, with Career in place of Engineering
- [x] Draft competency claims from tagged evidence into Siris (1.6.0)

## SirisLearn ✅ (ADR 112)
- [x] SirisLearn connector: status and the Learning widget (streak, XP today, level, courses, next lesson, new awards)
- [x] SirisLearn courses and lessons in search
- [x] Inbox: "your learning streak ends at midnight" while today's quiz isn't done
- [ ] Set `SIRISLEARN_URL` / `SIRISLEARN_HUB_KEY` on the server and check the tile live

## After the rebuild

- [x] Widgets you can configure and rearrange on the home screen (1.3.0)

## Daily staples (2.9 onwards)

- [x] Tasks: one list from SirisOS, Siris notes and SirisAI reminders; plain-words entry, repeats, snooze, push at a time (2.0.0)
- [x] Evening wrap-up: today, CPD from meetings, tomorrow's top 3 into the brief, a journal line (2.1.0)
- [x] Home that changes through the day: morning, work, weekend, evening (2.2.0)
- [x] Meeting prep: people, Siris notes, latest emails, related tasks; notes into Siris with actions as tasks; 10-minute heads-up (2.3.0)
- [x] Email triage: SirisAI's drafted replies, edit and send, snooze, leave (2.4.0)
- [x] Terminal shortcuts: one-tap commands behind a fresh code, output inline (2.5.0)
- [x] Weekly review: the week in numbers, quiet projects, next week's crunch points, what matters (2.6.0)
- [x] iPhone home-screen widget (Scriptable), fitness card, backups/updates/certificates on System status (2.7.0)
- [x] Nightly backups of SirisOS's own data, with download and undoable restore on System status (2.8.0)
- [x] Notifications with buttons: Done, In an hour, Approve, Snooze; a one-tap page on iPhone (2.9.0)
- [x] Access from here: test SirisOS from wherever the phone is, with fixes in plain words (2.10.0)
- [x] Projects: one page per Siris project with its tasks, meetings, emails and links (2.11.0)
- [x] Your year: CPD, running, tasks done, journal days and Inbox load, month by month (2.12.0)
- [x] Home controls: lights, garage, locks and scenes on Home, with a yes first for the garage and unlocking (2.13.0)
- [x] Talk to SirisOS: tasks, what's on, CPD reminders and notes by voice; anything else to SirisAI (2.14.0)
- [x] Yearly goals on Your year; tasks only your own; personal projects only; wrap-up as memories; Meetings, Email, iPhone shortcuts and This week archived (2.15.0)
- [x] Smart home: the house in 3D, floor by floor, with every network device in its room and live UniFi traffic flowing along neuron-style links (3.0.0)
- [x] Smart home: devices as small models of themselves, grouped when close, dragged to where they really are; the floor plan corrected (3.2.0)
- [x] Home: times of day you set (work 8:30–4:30 on weekdays), section order per part of the day, protocols only when you're home (3.3.0)
- [x] Home through the day: what each part of the day shows, wind down from 8 pm, work and personal tasks, welcome home (3.4.0)
- [x] Chartered application in Career: the self-reflection, the CPD questionnaire and the Building Industry Assessment, with a readiness checklist feeding next steps and a yearly goal (3.1.0)
- [x] From your notes: one older Siris note a day on Home, related to your projects, tasks and calendar (3.7.0)
- [x] Home maintenance: repeating jobs and appliances (manuals, warranties) in the house's rooms, due rooms glowing, on Home and as notifications with Done (3.8.0)
- [x] Network alerts: a notification when an unknown device joins (It's mine or Block it) or a watched one drops off, through SirisAI and UniFi (3.9.0)
- [x] Power use: rooms in the house lit by what they draw, a Power card with today's kWh, and kWh by month on Your year (3.10.0)
- [x] Training: a race plan from your recent running, today's run adjusted for sleep and recovery, a subscribed calendar; Apple Health arriving on its own through Health Auto Export (4.0.0)
- [x] Setup checklist on System status: every integration tested live, on, off or needing a look, with the fix and the setting names (4.1.0)
- [x] Health: readiness from HRV, resting heart rate, sleep and vitals against your own normal; sleep, training load and vitals; readiness leads the morning brief (5.0.0)
5.1.1: phone fixes: server rings sized again, dock kept at the bottom, iPhone push accepted (VAPID subject)
5.2.0: readiness kept from the morning (overnight HRV), and an energy score (Body Battery) through the day
5.3.0: visual checks in CI (phone and desktop), and notification health (last delivered, failing devices, weekly check)
5.3.1: slow Inbox actions say 'still working' (SirisAI 3.2.0), dropped connections explained, Setup flags an out-of-date SirisAI
5.4.0: training uses overnight HRV and energy, today's session in the brief, weekly trends, early run-down heads-up, body in the wrap-up
5.5.0: device inventory (name, owner, type, room) in alerts and the house, energy by device and always-on, maintenance by use
5.6.0: chartership readiness by element (weekly next steps), nudges with a daily cap and quiet hours, offline capture, house jobs and appliances in search
5.7.0: strain, week of sleep, Health Auto Export check, Update now on System status, standby killer, ask the manuals, pre-push check
6.0.0: Gym: exercise library, routines and starters, live logging with last time, what to lift, rest timer and plates, offline, records, history
6.1.0: SirisGYM: import years of JEFIT (or any CSV) workouts with a preview and exercise matching; safe to re-run
6.1.1: Health Auto Export setup says Date Range Default (Previous 7 Days left today out)
6.1.2: SI units everywhere: SirisGYM kg only (lb gyms converted), energy in kJ
6.2.0: SirisGYM: settings, gyms (bar, plates, dumbbells, stack), warm-ups, supersets, RPE and notes, progression rules, yearly heatmap
6.3.0: SirisGYM: muscle targets, deloads, readiness-aware plans, strain and training plan, Watch heart rate, strength standards, year in review; local-day fix
6.4.0: SirisGYM: programme builder, body measurements and progress photos, rest-over push, voice logging, SirisAI coaching, gym in the weekly review
6.4.1: Health says why today is empty (export stopped at yesterday, or nothing for hours)
6.5.0: SirisGYM runs an iPhone Shortcut when a workout starts or finishes (e.g. start the Watch workout)
6.6.0: Test the sync, where the numbers come from, exercise swap, protein target, gym time in the calendar, the gym in the brief, live checks
6.6.1: SirisGym: routine days on set weekdays (the week on Today, rest days), renamed from SirisGYM
6.6.2: SirisGym: no duplicate workouts from JEFIT (live days skipped, repeated sets once); exercises made from workout names taken out, workouts kept
6.7.0: SirisGym: set times lined up with the Watch's heart rate (effort per exercise, from SirisAI 3.7.0); JEFIT times in local time, old imports moved to their day
6.7.1: SirisGym on the tab bar from 6 to 8 am
6.8.0: Live-test batch: imports keep every set, impossible days held for checking, real workout names, merge duplicates, Last column, Finish warning, morning card, weekly coach, effort advice; lighter tab dot and saved data first; SirisAI-quiet alert, daily self-test, test mode
6.9.0: SirisGym: the Watch steers what to lift and the rest timer, fitter at the same weight, niggles, cardio, form videos, backups and export
7.0.0: Work dashboard (8:00 to 4:30, on the tab bar and Home), edit Siris notes and memories, Passkey only, Dom's iPhone counts as home
7.0.1: SirisGym: JEFIT exports read exactly (exercise logs only, Melbourne dates, no doubled sets, right exercises); re-import fixes an older import
7.0.2: live updates no longer held back by a proxy in front, HTTPS seen through it, self-renewing certificates not flagged, updater note
7.0.3: Apple Health sync moved to Health → Data sync; the terminal fits what's visible so the typing line isn't hidden
8.0.1: Work without the calendar or projects
8.1.0: Work made visual: day ring, task tiles, week bars, focus timer, work app tiles, CPD rings and logging, recent work notes as cards, desktop grid
8.2.0: work wrap-up at home time (carry-over, first thing, CPD, to Siris), chartership progress trend, ask about this page, tasks and SirisGym in search with filters, the week in the review notification
8.3.1: discarding a SirisGym workout runs the finish Shortcut too (stops the Watch); the Shortcut gets finished or discarded as input
9.1.0: SirisGym first-use fixes: weights carry down to the next sets, decimal weights type properly, edit a saved workout, a workout-in-progress bar on every page
9.1.1: Data sync setup says Time Grouping Minutes (metrics) and Seconds (workouts), with SirisAI 4.3.1
9.2.0: protocol on/off and notification switches (SirisAI 4.3.2), one device per install for notifications with a device list, one wind-down a night, evenly spaced tab bar
9.2.1: SirisGym reads weight from the daily health records (400 days, not the slow 70-day overview); Data sync shows the last weight received
9.3.0: Receipts in email fill in Things (SirisAI 4.4.0), read-only, with a script to connect Gmail
9.4.0: Receipts kept with the email and attachments, linked from Things; the Gmail Receipts folder read in full (SirisAI 4.5.0)
9.4.1: The receipt itself first (SirisAI 4.6.0), new and deleted projects, SirisAI's version checked properly, section names capitalised, Home controls above the 3D model
9.4.2: New tasks default to today (date on the Add bar and each task), focus and break lengths, pick the Work apps
9.4.3: Things and receipts show the latest 5, then everything by category; Budget sections fold away
9.5.0: SirisAI asks on Home to set goals all January and review them all December (unfinished carry over); delete notes from the mind map (engine 2.39); full-screen map clears the menu
9.6.0: What SirisAI watches on System status: switch off a container removed on purpose so its 'down' alerts stop (SirisAI 4.6.1)
9.8.0: Home Lab diagram, Training becomes Fitness (with Health's activity), drag sheets down to close, away-mode choice, no leave-by times, no OneNote handwriting check, wind-down desktop fixes
9.9.0: SirisGym list: start stays in the Home Screen app, weights don't drop a digit, rest timer kept and chimes in-app, 2 min between exercises, Clock-timer rest Shortcut, Finish at the bottom, reorder, unmerge and not-the-same, workouts kept offline and resent to SirisAI
9.10.0: SirisGym review: link your history, tidy imported exercises, typo check and Fix a set, iPhone workout (⋯, swipe, plates, against last time, new best, how it felt), repeat last, recovery, weekly push, deload Not now, lift goals, bad-date and warm-up fixes
9.11.0: SirisGym: screen stays on, log sets with Siri, tired / short-on-time days, AMRAP and rest-pause sets, form cues, gym swaps, planned lighter weeks, the next block, muscles over time, bodyweight in volume, monthly measure-up, backups pruned
9.12.0: Add to SirisOS (Share Sheet), offline tasks and uploads, WireGuard as VPN, return windows, review goals and overdue, server disk and GPU watch, backups copied to the NAS and restore-checked, Gym screen split, generated API docs
9.13.0: SirisGym: sheets close only from the top tab, the picker's search can't close it by mistake, last time's sets in every workout (GET /gym/last)
9.14.0: Health's Mental health tab: mood (Apple Health's State of Mind or a quick log), mindful minutes, what goes with a better mood, breathing, grounding, reframing, three good things, a journal and where to get help
9.15.0: Face ID for the Mental health journal, mood against drinks, caffeine and the gym, mood from Apple Health only, and a Habits tab with streaks
9.17.0: Habits on Home and in what helps, mind and habits in the weekly review, documents and renewals with reminders, an iPhone widget (Scriptable) with its own read-only key, a smaller first download, and setup checks for mood and the journal lock
9.18.0: public-repo hardening: never sign with a published key or accept a published password, read-only CI, SECURITY.md
9.18.1: lights show what they really are: a tap's answer only stands until the next read, and SirisAI 4.14.3 waits for the light to switch
9.18.3: SirisGym: every exercise names its helper muscles (built-ins fixed, yours filled once from the name), Helped by in New and Edit exercise, and recovery counts helpers
9.19.0: Pay day for each income line in Budget, with a SirisAI reminder at 8am on the day (SirisAI 4.15.1) and a Pay day card on Home
9.19.1: no work tasks or work reminders at the weekend (Show them on Tasks; the Sunday review still plans the week)
9.19.2: feed cards keep line breaks, for SirisAI's plain-words weekly reports
9.19.3: SirisAI's briefing card with Read it to me (SirisAI's voice, phone voice fallback)
9.20.0: SirisGym: assisted and one-side exercises counted right, what makes a good session (sleep, resting HR, time of day, caffeine), a workout card to share
9.20.1: exercise search mid-workout keeps the keyboard (sheets no longer steal focus on every tick)
9.20.2: bars stay at the bottom on iPhone after the keyboard closes or coming back to the app
9.20.3: SirisGym energy in kcal
9.20.4: an empty workout comes back to SirisGym after the Watch Shortcut, like a routine
9.20.5: SirisGym percentage chart of your best estimated 1RM on every exercise
9.21.0: SirisGym: a picture for each exercise (start and end of the movement), your own photo, or none
9.21.1: workout exercise pictures beside the name, not over it; Air Bike shows a bike
9.21.2: the tab bar floats lower on iPhone
9.21.3: the tab bar back where it was
9.22.0: readiness/strain/battery rings on Home, timesheet notes in Work, habits on chosen days, tap the tab to go to the top, honest 'Show N more', more health insights
9.24.0: actual spending from bank CSVs against the budget, balances with goal forecasts and net worth, focus blocks onto the timesheet with a Friday reminder, Home Assistant lists in Tasks, and a sun and heat heads-up
9.25.0: until pay day (the balance forward to after pay, lowest point, a Home card and notification when it's tight), recurring charges and subscriptions flagged from bank imports, suggestions for the plan
10.0.0: Meals with Mealie (its meal plan, the week's shopping onto Home Assistant's list), notification roundups, Trips (weather, packing, bills while away, out-of-office, away mode), a better doctor's summary (SirisAI 4.21.0), last month in short on Home and in Siris
10.0.1: SirisGym moved up the side menu, just below Tasks
10.0.2: Work's Timesheet notes card as wide as the Focus card on a computer
10.1.0: slide the bubble along the phone tab bar (Liquid Glass), fold the spending lines, bank files listed with Take out and Add another, no duplicate transactions
10.1.1: the tab bar's bubble lines up with the tab, swells while you drag, and follows smoothly
10.1.2: tapping a tab slides the tab bar bubble across (with a small swell) instead of jumping
10.1.3: the Friday debrief on Fridays only, with Add another after saving and Nothing this week (SirisAI 4.21.1)
10.1.4: Mealie's address works without http://, and its errors say what's wrong
11.0.0: Around the week: fuel on the Shepparton drive, weekend planner, watch tonight, bin night, bedroom before bed, garden and rain, catch-ups; Home Lab container updates and internet speed
11.1.0: Shorter side menu: 13 sections under headings, with tabs across grouped screens
11.2.0: Smarter notifications: seen in the app, still true, banner while using it, one device, asleep/busy/home aware, learns what's ignored, daily cap, replacing
11.2.1: Every screen opens at its top (back and forward keep your place)
11.2.2: Versions are Section.Feature.Fix, and the whole history renumbered that way (10.61 became 11.2.1)
11.3.0: Smart capture, a plan for the day, Home that learns, bills on the timeline and price rises, patterns across sections, SirisAI reads SirisOS's data, goals that steer themselves, while you were away
11.4.0: SirisOS works offline: Get ready for offline (by itself before a flight), every screen keeps its last data, everyday changes queue and sync, IndexedDB storage, a sync bar, safe merging, SirisAI questions asked offline

## Terminal (ADR 113)

- [x] A shell on a home machine over SSH, behind a fresh 2FA code each session (1.17.0)
- [ ] Set `SIRISOS_TERMINAL_HOSTS` on the server, add the `make terminal-key` key to `authorized_keys`, set up 2FA
