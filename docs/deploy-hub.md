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
- Keep your existing `SIRISOS_ADMIN_*`, `SIRISOS_JWT_SECRET`,
  `OLLAMA_URL` and `SIRISOS_OLLAMA_CHAT_MODEL`.
- Fill in the connector block (next section).

## 2. Credentials each app needs

| App | What to create | `.env` |
| --- | --- | --- |
| SirisAI | Copy its `SIRISAI_API_KEY` from SirisAI's `.env` | `SIRISAI_URL=http://192.168.0.100:8000`, `SIRISAI_API_KEY=…`, optionally `SIRISAI_PUBLIC_URL=https://192.168.0.100:8443` |
| Second Brain | Nothing: SirisAI serves it. SirisAI needs `SIRISAI_BRAIN_PATH` set | (uses the SirisAI values) |
| Engineering Reviewer | Nothing, unless its Basic auth is on | `REVIEWER_URL=http://192.168.0.100:8082` (+ `REVIEWER_USERNAME/PASSWORD`) |
| Engineering Archive | Settings → API keys → new key with **read** scope | `ARCHIVE_URL=http://192.168.0.100:8091`, `ARCHIVE_API_KEY=ea_…` |
| SirisDrone | Nothing, unless its `SIRIS_USER`/`SIRIS_PASSWORD` login is on | `SIRISDRONE_URL=http://192.168.0.100:8096` (+ `SIRISDRONE_USERNAME/PASSWORD`) |
| SirisLearn | Set `SIRISLEARN_HUB_KEY` in its `.env` (`openssl rand -hex 32`) | `SIRISLEARN_URL=http://192.168.0.100:8100` + the same `SIRISLEARN_HUB_KEY` |

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

- [ ] Home shows widgets for SirisAI, Second Brain, Projects, Reviews and Archive
- [ ] Siris chat streams a reply, and a tool that needs confirmation shows Allow/Cancel
- [ ] Brain search returns notes, and Quick capture lands in the vault inbox
- [ ] Engineering → Standards lists the existing library, and SirisHydro answers with citations
- [ ] Saved calculations and projects from before the rebuild are still there (they live in `data/app`)

## 3b. Check everything end to end

`make verify` goes further than `make hub-check`: every app, SirisAI's hub
contract, calendar range and forecast, Second Brain search and insights,
SirisAI's service key into SirisOS (it must open the calculators and be
refused creating a project), phone notifications, the security settings and
building today's brief. Each line is ✓ fine, ! worth a look, ✗ broken or ·
not set up, and it exits 1 if anything is broken.

- `make verify EA=ea-export.csv` also tries an Engineers Australia CPD export
  (copy it into `data/app/` first). It's parsed and summarised, never imported.
- `make verify PUSH=1` also sends every subscribed device a test notification.

Nothing is changed by it.

## 4. Install on iPhone

In Safari, open `https://192.168.0.100:8444` and accept the certificate
warning once. Then use Share → **Add to Home Screen**, and it opens
full-screen like an app. Use the https address so the Siris voice orb can
reach the microphone; `http://192.168.0.100:8094` still works for
everything except voice.

## 5. Phone notifications

Open SirisOS **from the Home Screen icon**, go to the Inbox and use
**Notifications on this device → Turn on notifications**. Pick what you want
to hear about (apps going down, SirisAI alerts and approvals, the daily
brief, career reminders) and tap **Send a test**. Each device is set up on
its own.

iPhones only allow notifications for a Home Screen app on an HTTPS address
whose certificate the phone *trusts*. Clicking through a certificate warning
isn't enough: the service worker that receives notifications won't run.
Either install the certificate's root on the iPhone (Settings → General →
VPN & Device Management, then Settings → General → About → Certificate
Trust Settings → turn it on), or reach SirisOS through an address with a
real certificate (for example Tailscale HTTPS or a domain behind a reverse
proxy). The server also needs to reach Apple's push service
(`web.push.apple.com`) on the internet.

The signing key for notifications is made on first use and kept in
`data/app/push-vapid.json`; deleting it means every device has to turn
notifications on again.

## Signed out and can't get back in?

Sign-in is one username and password, set by `SIRISOS_ADMIN_USERNAME` and
`SIRISOS_ADMIN_PASSWORD` in `.env`, or a passkey added on the Security screen.
A rejected sign-in means the username or password typed doesn't match
(they're case-sensitive; use the eye on the password box to check). After 8
wrong passwords in 15 minutes from one device, sign-in waits until the 15
minutes are up ("Too many wrong passwords"), or restart the container to
clear it.
Sessions last `SIRISOS_JWT_EXPIRY_HOURS` (24 by default), after which you're
asked to sign in again.

- **To see the current password**, read it on the server:
  `grep ^SIRISOS_ADMIN_PASSWORD= ~/Docker/SirisOS/SirisOS/.env`
- **To choose a new one**, on the server: `make reset-password`.
  Add `ARGS=--sign-out-all` to also end every signed-in session.

## What's left behind

- The pre-hub Postgres (gym, running, health and homelab history) was
  exported and removed on 3 October 2026. On the server, the dump and the raw
  data folder are in `~/Docker_ss/SirisOS-pre-hub`. To read it again, restore
  the dump into any Postgres 17 container.
- `data/knowledge` (the old read-only vault mount) is no longer used; the
  vault is Second Brain's.
