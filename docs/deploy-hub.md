# Deploying the SirisOS hub

This is a one-time checklist for moving `192.168.0.100` to the hub build
(ADR 106). It runs on the server, because the connectors need the LAN.

## 1. Pull and configure

```bash
cd ~/SirisOS          # wherever the repo lives on the server
git pull
cp .env .env.pre-hub  # keep the old settings for reference
```

Edit `.env`. Start from `.env.example`, which now lists only the settings
SirisOS reads:

- `SIRISOS_PORT=8094`. `6464` now belongs to dad-joke-of-the-day.
- Keep your existing `SIRISOS_ADMIN_*`, `SIRISOS_JWT_SECRET`, `POSTGRES_*`,
  `OLLAMA_URL` and `SIRISOS_OLLAMA_CHAT_MODEL`.
- Fill in the connector block (next section).

## 2. Credentials each app needs

| App | What to create | `.env` |
| --- | --- | --- |
| SirisAI | Copy its `SIRISAI_API_KEY` from SirisAI's `.env` | `SIRISAI_URL=http://192.168.0.100:8000`, `SIRISAI_API_KEY=…`, optionally `SIRISAI_PUBLIC_URL=https://192.168.0.100:8443` |
| Second Brain | Nothing: SirisAI serves it. SirisAI needs `SIRISAI_BRAIN_PATH` set | (uses the SirisAI values) |
| APD PM | Create a **Viewer** user, e.g. `siris-hub@…` | `APD_PM_URL=http://192.168.0.100:8080`, `APD_PM_EMAIL`, `APD_PM_PASSWORD` |
| Engineering Reviewer | Nothing, unless its Basic auth is on | `REVIEWER_URL=http://192.168.0.100:8082` (+ `REVIEWER_USERNAME/PASSWORD`) |
| Engineering Archive | Settings → API keys → new key with **read** scope | `ARCHIVE_URL=http://192.168.0.100:8091`, `ARCHIVE_API_KEY=ea_…` |
| GVW Timesheets | Nothing (health only) | `GVW_URL=http://192.168.0.100:8092` |
| CMP Capabilities | Your own login (the widget shows *your* capability stats) | `CMP_URL=http://192.168.0.100:8093`, `CMP_EMAIL`, `CMP_PASSWORD` |
| JEFIT, Helmarr, Neo Server | Nothing | `JEFIT_URL`, `HELMARR_URL`, `NEO_SERVER_URL`: a web URL or the app's URL scheme |

Inside the container, `192.168.0.100` reaches the other apps' published
ports. If an app uses a self-signed HTTPS certificate, set
`SIRISOS_HUB_VERIFY_SSL=false`.

## 3. Start and verify

```bash
make up            # builds the React app + API image; drops docker-proxy and node-exporter
make status        # container health
make hub-check     # every app: ✓ ok · ! degraded · ✗ down · not configured, with the reason
```

`make hub-check` exits non-zero while any configured app is degraded or
down, and each line says why: wrong credentials, timeout, no LLM and so on.
Fix `.env` and run `docker compose up -d sirisos` until it's all ✓ or ·.

Then open `http://192.168.0.100:8094`, sign in, and check:

- [ ] Home shows widgets for SirisAI, Second Brain, Projects, Reviews, Archive and CMP
- [ ] Siris chat streams a reply, and a tool that needs confirmation shows Allow/Cancel
- [ ] Brain search returns notes, and Quick capture lands in the vault inbox
- [ ] Engineering → Standards lists the existing library, and SirisHydro answers with citations
- [ ] Saved calculations and projects from before the rebuild are still there (they live in `data/app`)

## 4. Install on iPhone

In Safari, open `http://192.168.0.100:8094`, then Share → **Add to Home
Screen**. It opens full-screen like an app.

## What's left behind

- The `postgres` container still runs with the pre-hub data (gym, running,
  health, homelab history). Nothing reads it. Once you're sure nothing there
  is needed, export it (`docker compose exec postgres pg_dump -U sirisos
  sirisos > pre-hub.sql`), then remove the service.
- `data/knowledge` (the old read-only vault mount) is no longer used; the
  vault is Second Brain's.
