# ADR 110: SirisAI integration, v1

## Status

Accepted (2026-10-09). Pairs with SirisAI milestones 125–127.

Landed in SirisOS on 2026-10-10. Until then it shipped as a patch in
SirisAI (`deploy/patches/sirisos-adr110.patch`), which SirisAI's
`deploy/setup.sh` applied. It was merged onto the daily brief, search,
calendar labels and Career work that had landed in the meantime. The
service-key allowlist now also covers the Career reads (ADR 111).

## Context

SirisOS reached SirisAI through one bearer key, and some of what it used
was fragile:

- **The daily brief ran SirisAI tools by name** (`weather_forecast`,
  `email_list_unread`, `health_summary`…) through
  `/siris/tools/{name}/run` and read their raw results. If a tool was
  renamed or its result changed shape, part of the brief went empty, and
  neither repo's tests noticed.
- **SirisAI's newer features never reached SirisOS:** protocols, cameras,
  the car, power prices, the autonomy timeline, and its alerts and
  approvals.
- **SirisAI couldn't use what SirisOS owns.** SirisAI is meant to be the
  only assistant, but the standards library, calculators, projects and
  SirisHydro were out of its reach.
- **SirisOS kept its own model connection** for SirisHydro, against "SirisOS
  has no LLM of its own".
- **Every request reached SirisAI as its default user**, and guest mode
  meant nothing on the home screen.

## Decision

### A versioned contract, tested on both sides

SirisAI serves `/siris/hub/v1`. Every response there is a pydantic model
that forbids unknown fields. SirisAI generates `contracts/hub-v1/schema.json`
from those models, plus one real example payload per endpoint, and its
tests fail if either drifts. `scripts/sync-sirisai-contract.sh` copies them
here, to `apps/backend/tests/contracts/sirisai-hub-v1/`. SirisOS's tests
(`test_sirisai_v1.py`, `SirisControls.test.tsx`) drive the brief, search,
inbox and controls from those same files.

Adding an optional field stays v1. Removing or retyping a field is a v2.
SirisOS falls back to the previous calls whenever SirisAI answers 404, so an
older SirisAI keeps working.

| SirisOS uses | SirisAI endpoint | Instead of |
| --- | --- | --- |
| Daily brief | `GET /siris/hub/v1/brief` | the HUD, five tools by name and brain insights |
| Search (Second Brain, chats, memories) | `GET /siris/hub/v1/search` | brain search and the `search_conversations` tool |
| Inbox | `GET /siris/hub/v1/attention` (+ `/stream`, `/act`, `/dismiss`) | nothing |
| Home: protocols, cameras, car, power, parcels | `GET /siris/hub/v1/widgets`, `/protocols/*`, `/cameras/*/look` | nothing (the HUD's parcels, read with the wrong keys) |
| Guest mode | `GET /siris/hub/v1` | nothing |
| SirisHydro answers | `POST /siris/hub/v1/llm/complete` | SirisOS's own Ollama call (kept as the fallback) |

One real bug turned up straight away: the brief printed a contract float as
"70.0% chance of rain". It's fixed, and the contract test now covers it.

### The inbox

`/inbox` (and a "Needs you" panel on Home, plus a count in the menu) merges:

- **SirisAI's attention feed.** It covers intruder alerts (with "Lock
  down"), failed self-heals, unattended actions waiting for approval
  (Approve/Decline), habit suggestions, jobs waiting for cheap power, and
  Second Brain reviews. Their actions run in SirisAI; SirisOS relays them.
- **SirisOS's own items.** These are apps that are down or degraded, Project
  Management's overdue tasks, and the Engineering Archive's review queue.
  Each can only be dismissed, and tapping one opens the app. A dismissal is
  stored server-side and lasts until the situation changes: the item's key
  includes its state or count.

The PWA keeps one live stream (`/api/v1/attention/stream`) for every screen.
SirisOS relays SirisAI's stream and re-checks its own items every minute.
If the stream drops, the PWA reconnects and backs off. Actions aren't
optimistic: if an approval fails, the item stays on screen with the error.

### SirisAI can read the engineering library

SirisAI calls SirisOS with `Authorization: Bearer <SIRISOS_SERVICE_KEY>`.
One middleware (`app/service_key.py`) accepts the key only on these routes:

- `GET /api/v1/hub/apps`
- `GET /api/v1/engineering/standards`
- `GET /api/v1/engineering/calculators` and `POST .../{id}/run`
- `GET /api/v1/projects`
- `GET /api/v1/engineering/sirishydro/evidence`

Any other route answers 403 to the key, including everything that uploads,
edits or deletes. On an allowed route, the middleware swaps the key for a
five-minute session token, so each route's existing auth check applies
unchanged. A key shorter than 24 characters is ignored.

The calculators now also run server-side (`app/engineering/calculators.py`),
ported line for line from `calculators.ts`, including JavaScript's `toFixed`
rounding. `calculator-cases.json` holds 50 cases that both test suites run:
the web suite writes them and the backend suite checks them. A spoken
answer from SirisAI therefore matches the Calculators screen exactly.

### Who is asking

Every SirisAI request carries `X-Siris-Client: SirisOS`, so SirisAI's audit
log says "... in SirisOS". `SIRISAI_USER` is opt-in and adds
`X-Siris-User`. It isn't the default because records made before it was set
belong to SirisAI's default user.

While SirisAI's guest mode is on:

- The home screen drops SirisAI's "Today" widget and the Second Brain widget.
- The calendar widget is hidden and a banner says why.
- The brief arrives without its personal sections and says so.

## Consequences

- When SirisAI's contract changes, run `scripts/sync-sirisai-contract.sh`
  and the backend tests. A breaking change fails here before it ships.
- `SIRISOS_SERVICE_KEY` (here) and `SIRISAI_SIRISOS_SERVICE_KEY` (SirisAI)
  must match for SirisAI's engineering tools to work.
- SirisHydro needs no model settings of its own once SirisAI is configured.
  The `OLLAMA_URL` settings remain as the fallback.
