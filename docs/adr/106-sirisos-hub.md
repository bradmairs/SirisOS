# ADR 106 — SirisOS becomes the hub ("the OS")

## Status

Accepted (2026-10-02). Supersedes the scope, though not the individual
decisions, of ADRs 001–105. The superseded features are listed below.

Amended 2026-10-04: the CMP Capabilities Database connector was removed at
Brad's request. It is a work tool, and SirisOS is for his own life. It is
still listed in the tables below as part of the original decision. Leftover
`CMP_*` settings in `.env` are ignored.

## Context

When SirisOS was revived in October 2026, Brad already ran a family of
self-hosted apps on `192.168.0.100`, and several of them now cover ground
SirisOS had been growing into:

| App | Repo | Port | What it owns |
| --- | --- | --- | --- |
| SirisAI | `bradmairs/SirisAI` | (own) | The Jarvis-style assistant: chat with tools, memory, briefing, goals, voice, home/HUD |
| Siris Second Brain | `bradmairs/Siris-Second-Brain` | — (vault, served by SirisAI `/siris/brain/*`) | Notes, knowledge, long-term memory (PARA Markdown vault) |
| APD Project Management | `bradmairs/APD-Project-Management-Dashboard` | 8080 | Projects, tasks, registers |
| Siris Engineering Reviewer | `bradmairs/siris-engineering-reviewer` | 8082 | Drawing pre-review |
| Engineering Archive | `bradmairs/Engineering-Archive` | 8091 | Site photos, files, assets |
| GVW Timesheet Tool | `bradmairs/gvw-timesheet-tool` | 8092 | Timesheets |
| CMP Capabilities Database | `bradmairs/CMP-Capabilities-Database` | 8093 | Staff capabilities, CVs, planner |

The phone apps Helmarr (media), JEFIT (gym) and Neo Server (homelab)
remain the preferred tools in their domains ("complement, not replace",
2026-08-22).

SirisOS had duplicated much of this work: its own agent chat (SirisAgent),
its own memory (Siris Memory), its own Obsidian knowledge module, homelab
monitoring and incidents (overlapping SirisAI's integrations and Neo
Server), and gym, running and health tracking (overlapping JEFIT and
SirisAI's health ingest). The Flutter UI had reached about 29k lines and 34
screens.

Brad's brief: integrate with these apps instead of rebuilding them, give
the whole thing an Apple **Liquid Glass** look, and change as much of
SirisOS as needed to get there.

## Decision

### 1. SirisOS is the shell, not the app

SirisOS becomes the visual home screen and hub for the whole Siris family:

- **App tiles.** Every app gets a tile with live status and a launch link.
- **Widgets.** Glanceable data comes from each app's own API (SirisAI HUD,
  APD PM due tasks, Archive review queue, and so on).
- **SirisAI is the system assistant.** The chat sheet streams from SirisAI's
  `/siris/chat/stream`. SirisOS has no LLM, agent or memory of its own.
- **Second Brain is the notes layer.** Search, quick capture and "learned
  today" all go through SirisAI's `/siris/brain/*`.
- **Engineering tools stay native**, because nothing else owns them: the
  SirisHydro evidence search, the civil/water calculator library, the
  private Standards Library and SirisOS Projects (which carry calculations
  and citations).

### 2. Backend: a connector gateway

The browser only ever talks to SirisOS. The FastAPI backend holds every
other app's credentials and calls those apps server-side. This keeps API
keys and service passwords off devices and avoids CORS. It also lets a tile
show *why* an app is unhappy (unconfigured, unauthorised, timeout,
unreachable).

Each app is a **connector** (`apps/backend/app/hub/connectors/`), and every
connector implements the same contract:

- `id`, `name`, `category` (`assistant`, `work`, `engineering`, `life`),
  `icon` and `launch_url`.
- `configured`: whether the env vars it needs are set.
- `status()`: an `ok | degraded | down | unconfigured` state, plus detail
  and latency.
- `widget()`: optional small, normalised JSON for the home screen.

Connectors run concurrently, each with its own timeout and a short-lived
cache. A slow or dead app blanks its own tile and never the whole page.
That is the same rule SirisAI's HUD follows.

Hub API (all JWT-protected like the rest of `/api/v1`):

- `GET /api/v1/hub/apps`: every tile with its status.
- `GET /api/v1/hub/apps/{id}`: one app's status and widget.
- `GET /api/v1/hub/widgets`: widgets for every configured app.
- `/api/v1/assistant/*`: proxy for SirisAI chat (SSE passthrough), confirm,
  conversations, HUD and briefing.
- `/api/v1/brain/*`: proxy for Second Brain search, capture and today.

Credentials per connector:

| Connector | Auth used by SirisOS |
| --- | --- |
| SirisAI / Second Brain | `Authorization: Bearer $SIRISAI_API_KEY` |
| APD PM | Logs in with `APD_PM_EMAIL`/`APD_PM_PASSWORD` (cookie session). Use a dedicated read-only (VIEWER) account |
| Engineering Reviewer | Optional HTTP Basic (`REVIEWER_USERNAME`/`REVIEWER_PASSWORD`) |
| Engineering Archive | `X-API-Key: $ARCHIVE_API_KEY` (a `read`-scope key from the Archive's API keys page) |
| GVW Timesheets | Unauthenticated `/healthz` only. Its pages use per-user Basic auth, so the tile is status + launch |
| CMP Capabilities | Logs in with `CMP_EMAIL`/`CMP_PASSWORD` (bearer JWT) |
| Helmarr, JEFIT, Neo Server | Launch tiles only (`*_URL` may be an app URL scheme) |

### 3. Frontend: React + TypeScript PWA with a Liquid Glass design system

`apps/web` (Vite + React + TypeScript) replaces the Flutter app.

- CSS `backdrop-filter` gives real translucency and refraction-like layering
  on Safari/iOS, which Flutter web can only approximate.
- It matches the stack of Brad's other apps.
- It installs to the iPhone home screen as a PWA.

The design system covers glass materials (regular and clear), specular
edges, a floating tab bar/dock, sheets, light and dark themes, and
`prefers-reduced-transparency`/`prefers-reduced-motion` fallbacks.

### 4. Removed (Phase 4)

The following come out of the backend and are not ported to React:

- **SirisAgent** and **Ask Siris**: replaced by SirisAI.
- **Siris Memory**: replaced by SirisAI memory and Second Brain.
- **Knowledge / knowledge context / semantic search**: replaced by Second
  Brain.
- **Homelab, Docker, host metrics, infrastructure integrations, Synology,
  Grafana, alerts, incidents, digital twin, actions and recommendations**:
  replaced by Neo Server and SirisAI integrations.
- **Gym/JEFIT import, running, training, coach, achievements, readiness,
  Apple Health ingest**: replaced by JEFIT and SirisAI health.
- **The Flutter app** (`apps/mobile`).

Database tables those modules created are **left in place, not dropped**.
Nothing is deleted from Postgres. The `postgres` service stays in
`docker-compose.yml` so `./data/postgres` remains intact and reachable, but
SirisOS no longer connects to it or depends on it. A later decision can
export or drop it. The docker-proxy and node-exporter containers, which only
fed homelab monitoring, are removed.

Project relationships to knowledge notes made before this ADR stay listed
with their stored label. New ones are refused, because notes live in Second
Brain now.

### 5. Port

SirisOS moves off `6464`, which is now used by dad-joke-of-the-day. It now
publishes on `SIRISOS_PORT`, default **8094**, next to the other tools in
the 8080–8093 range.

## Consequences

- SirisOS shrinks from a do-everything app into a thin, fast shell plus the
  engineering module. Most of the codebase is deleted, but the history stays
  in git and in `docs/history/`.
- SirisOS depends on the other apps being up. Every connector failure is
  visible and isolated, never fatal.
- New apps join by adding a connector class and env vars. No frontend change
  is needed for a basic status/launch tile.
- Live behaviour against the real apps can only be verified on Brad's LAN.
  Connectors are built against the APIs read from each repo and tested with
  mocked HTTP.
