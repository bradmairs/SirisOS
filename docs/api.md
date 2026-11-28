# SirisOS API

Interactive docs are served at `/docs` (OpenAPI at `/openapi.json`). Every
`/api/v1` route except sign-in needs `Authorization: Bearer <token>` from
`POST /api/v1/auth/login`.

## System

| Route | Purpose |
| --- | --- |
| `GET /` | Name and version |
| `GET /health` | Liveness (used by the container healthcheck) |
| `POST /api/v1/auth/login` | `{username, password}` → `{access_token, expires_in, username}` |
| `GET /api/v1/auth/me` | The signed-in user |

## Engineering module

| Route | Purpose |
| --- | --- |
| `GET /api/v1/engineering/sirishydro/evidence?question=&limit=` | Cited evidence from the standards library, plus an optional Ollama-synthesized answer |
| `GET /api/v1/engineering/sirishydro/history` · `DELETE …/history/{id}` | Past SirisHydro questions |
| `GET /api/v1/engineering/standards?query=&authority=&include_archived=&limit=` | Search documents and page text |
| `POST /api/v1/engineering/standards` (multipart) · `POST …/{id}/replace` | Upload a PDF / a new revision |
| `DELETE /api/v1/engineering/standards/{id}` · `POST …/{id}/restore` | Archive / restore |
| `GET /api/v1/engineering/standards/{id}/pages/{page}` · `GET …/{id}/file` | Indexed page text / the PDF |
| `GET, POST /api/v1/engineering/calculations` · `GET, DELETE …/{id}` | Saved calculator results |
| `GET, POST /api/v1/projects` · `GET, PATCH …/{id}` · `GET, PUT …/current` | Engineering projects and the current project |
| `GET, POST /api/v1/projects/{id}/relationships` · `DELETE …/{rid}` · `GET …/{id}/graph` | Links to calculations and standards |

Project links to knowledge notes made before ADR 106 are still listed;
new ones are refused (notes live in Siris).

## Hub (ADR 106)

All routes require the SirisOS bearer token.

| Route | Purpose |
| --- | --- |
| `GET /api/v1/hub/apps?widgets=&fresh=` | Every app tile: `id`, `name`, `category`, `icon`, `launch_url`, `configured`, `status {state, detail, latency_ms, version, checked_at}`, optional `widget` |
| `GET /api/v1/hub/apps/{id}` | One app with its widget |
| `GET /api/v1/hub/widgets` | Widgets for every reachable app: `{title, metrics[{label,value,tone}], items[{title,subtitle,url,tone}], empty, updated_at}`, or `{error}` |
| `POST /api/v1/assistant/chat/stream` | SirisAI `/siris/chat/stream`, relayed as Server-Sent Events |
| `POST /api/v1/assistant/chat/confirm/stream` | SirisAI tool confirmation, streamed |
| `GET /api/v1/assistant/conversations[/{id}]` | SirisAI conversation history |
| `GET /api/v1/assistant/hud` | SirisAI HUD summary |
| `GET /api/v1/brain/search?q=` · `GET /api/v1/brain/today` · `GET /api/v1/brain/insights?days=30` · `POST /api/v1/brain/capture` | Siris via SirisAI (insights: growth, topics, deadlines, overdue tasks, idle projects, links to make) |
| `POST /api/v1/brain/link` · `POST /api/v1/brain/not-related` · `POST /api/v1/brain/unlink` (`{a, b}`) | Link two notes, dismiss a suggestion, or disconnect two notes (never auto-linked again) |
| `POST /api/v1/brain/autolink` | Link the pairs the brain is confident about now, rather than at the nightly tidy |
| `GET /api/v1/brain/note?title=` | A note's links and backlinks |
| `POST /api/v1/brain/delete` (`{title, permanent?}`) · `POST /api/v1/brain/restore` · `POST /api/v1/brain/purge` (`{title}`) · `GET /api/v1/brain/deleted` | Delete a note (it leaves search, links and the map; links to it are removed; restorable unless `permanent`), put one back with its connections, remove a deleted one for good, or list deleted notes with `restorable` |
| `GET /api/v1/memories?query=&limit=` · `DELETE /api/v1/memories/{id}` | SirisAI's own memories (`id`, `content`, `created_at`, `recall_count`), and deleting one (no undo) |
| `GET /api/v1/brief?fresh=` | The daily brief (ADR 108): `greeting`, `headline[]`, `weather {now, today}`, `schedule[]`, `tasks[]`, `todo[]`, `email {unread, important[]}`, `health[]`, `home[]`, `apps_attention[]`, `brain`, `news {topics[{topic, stories[{title, url, source, published, matches}]}], interests_from}`, `unavailable[]`, `status`. Cached 10 minutes |
| `GET /api/v1/brief/status` · `POST /api/v1/brief/dismiss` | `{date, show, dismissed_today, from, until}`: whether the brief should open itself now; dismiss it for today (all devices) |
| `GET /api/v1/search?q=` | Search everything (ADR 109): `{query, groups[{id, label, icon, best, hits[{title, subtitle, url, external, kind, app_id, score}]}], failed[], took_ms}`. Two characters minimum; each source has a 4 s timeout |
| `GET /api/v1/career` · `GET /api/v1/career/overview` | Career (ADR 111): `{document, overview}`. The document holds profile, pathways and steps, Stage 2 elements, evidence, goals and CPD records. The overview has CPD totals over the rolling 3 years, pathway progress, competency counts and gaps, goals and `next_steps` |
| `PUT /api/v1/career` | Save the profile, pathways, evidence and goals (never CPD) |
| `POST /api/v1/career/cpd/import` (multipart `file`) · `PUT /api/v1/career/cpd/{id}/category` | Import Engineers Australia's CPD export (CSV or .xlsx; re-importing never duplicates). Correct a guessed category (`null` restores the guess) |

`state` is `ok`, `degraded` (reachable, but wrong credentials or a missing
dependency such as an LLM), `down` (unreachable or timed out) or
`unconfigured`. Statuses and widgets are cached for 20 seconds; pass
`fresh=true` to bypass the cache.

## Every route

<!-- routes:start -->

Every route, generated from the app by `apps/backend/scripts/api_docs.py` (don't edit by hand).

### `/api/v1/access`

| Route | What it does |
| --- | --- |
| `GET /api/v1/access` |  |
| `GET /api/v1/access/stream` |  |

### `/api/v1/ask`

| Route | What it does |
| --- | --- |
| `POST /api/v1/ask` | Ask Siris from a Shortcut (11.16), with the Ask key in X-SirisOS-Key. Never approves anything. |
| `DELETE /api/v1/ask/key` |  |
| `GET /api/v1/ask/key` |  |
| `POST /api/v1/ask/key` | A new Ask key (11.16), shown once; the old one stops working. |

### `/api/v1/assistant`

| Route | What it does |
| --- | --- |
| `POST /api/v1/assistant/ask-later` | A question asked offline: SirisAI answers it in the background and the answer comes as a notification. |
| `GET /api/v1/assistant/asked` |  |
| `GET /api/v1/assistant/cameras/{camera}/latest.jpg` | The camera's latest frame, through SirisAI (which proxies Frigate), so neither Frigate nor the SirisAI key is exposed to the browser. |
| `POST /api/v1/assistant/cameras/{camera}/look` | SirisAI's vision model describes the camera's latest frame. |
| `POST /api/v1/assistant/chat/confirm/stream` |  |
| `POST /api/v1/assistant/chat/stream` | SirisAI's POST /siris/chat/stream, relayed as-is (Server-Sent Events). |
| `GET /api/v1/assistant/controls` |  |
| `POST /api/v1/assistant/controls/{entity_id}` | Garage doors and unlocking need {"confirmed": true}; SirisAI refuses otherwise. |
| `GET /api/v1/assistant/conversations` |  |
| `GET /api/v1/assistant/conversations/search` | Past conversations by words and dates, each with its title and summary (SirisAI 4.6). |
| `GET /api/v1/assistant/conversations/{conversation_id}` |  |
| `POST /api/v1/assistant/feedback` | "Not right" on SirisAI's last answer (10.01, SirisAI 7.17): SirisAI learns from it. |
| `GET /api/v1/assistant/hud` |  |
| `GET /api/v1/assistant/info` | Who SirisAI thinks is asking, whether guest mode is on, and which of its integrations are configured -- what the PWA shows and hides by. |
| `GET /api/v1/assistant/network` | UniFi's gateway, switches, access points and clients with live traffic (SirisAI 2.76), for the house view. |
| `GET /api/v1/assistant/protocols` | Every protocol with its steps, and what a step can do: the editor (SirisAI 2.91). |
| `POST /api/v1/assistant/protocols/undo` |  |
| `DELETE /api/v1/assistant/protocols/{name}` | Delete yours; a built-in you'd changed comes back. |
| `GET /api/v1/assistant/protocols/{name}` | What running the protocol would do right now, step by step. |
| `PUT /api/v1/assistant/protocols/{name}` | Make or change a protocol. SirisAI checks every step (only lights, switches, covers, locks, media, climate, scenes, notifications and guest mode can be set from here). |
| `POST /api/v1/assistant/protocols/{name}/run` | Runs only with {"confirmed": true}: protocols change locks, covers and modes. |
| `PUT /api/v1/assistant/protocols/{name}/switches` | 7.9: turn a protocol on or off (off: it never runs or gets offered), and its notifications (SirisAI 5.11). |
| `POST /api/v1/assistant/scenes/{scene_id}/run` |  |
| `GET /api/v1/assistant/tracking` | 8.4: what SirisAI watches (Docker's containers, tracked or not) and what it's been told to stop tracking (SirisAI 5.51). |
| `PUT /api/v1/assistant/tracking` | Stop tracking something removed on purpose (no more "it's down" alerts), or track it again. |
| `GET /api/v1/assistant/voice` | Whether SirisAI can hear (speech-to-text) and speak (text-to-speech). |
| `POST /api/v1/assistant/voice/converse` | SirisAI's POST /siris/voice/converse (one spoken turn), relayed as-is: newline-delimited JSON with the transcript, then each reply sentence with its audio, then a final event. It's the same conversation store as chat, so spoken turns feed Siris' nightly dream too. |
| `POST /api/v1/assistant/voice/speak` | Text read aloud in SirisAI's voice (9.53: the briefing card's "Read it to me"). 501 when SirisAI has no text-to-speech set up, so the phone can use its own voice. |
| `POST /api/v1/assistant/voice/transcribe` | Speech to text through SirisAI (for voice memos in quick capture). |
| `GET /api/v1/assistant/widgets` | Car, parcels, power, protocols (and the last run, for undo), cameras and what SirisAI did on its own today. |

### `/api/v1/attention`

| Route | What it does |
| --- | --- |
| `GET /api/v1/attention` |  |
| `GET /api/v1/attention/selftest` | This morning's self-test (7.0): what it found, for the Status page. |
| `GET /api/v1/attention/stream` | A snapshot of the whole inbox, then every change: SirisAI's feed is relayed live (its upserts and removals, ids prefixed), and SirisOS's own items are re-checked every minute (a new snapshot when they change). If SirisAI's stream drops, the relay reconnects after a pause. `max_events` (default 0 = forever) ends the stream after that many events. |
| `POST /api/v1/attention/{item_id}/act` |  |
| `POST /api/v1/attention/{item_id}/dismiss` |  |
| `POST /api/v1/attention/{item_id}/snooze` | Hide an inbox item until a time; it comes back by itself. |

### `/api/v1/auth`

| Route | What it does |
| --- | --- |
| `POST /api/v1/auth/login` |  |
| `GET /api/v1/auth/me` |  |
| `GET /api/v1/auth/passkeys` |  |
| `POST /api/v1/auth/passkeys/login` |  |
| `POST /api/v1/auth/passkeys/login/options` |  |
| `POST /api/v1/auth/passkeys/register` |  |
| `POST /api/v1/auth/passkeys/register/options` |  |
| `DELETE /api/v1/auth/passkeys/{cred_id}` |  |

### `/api/v1/away`

| Route | What it does |
| --- | --- |
| `GET /api/v1/away` |  |
| `POST /api/v1/away/done` |  |
| `POST /api/v1/away/touch` | The app is open (no summary showing): the clock starts again. |

### `/api/v1/backups`

| Route | What it does |
| --- | --- |
| `GET /api/v1/backups` |  |
| `POST /api/v1/backups` |  |
| `POST /api/v1/backups/check` | Check the newest backup would restore (8.9); weekly by itself. |
| `GET /api/v1/backups/{name}` |  |
| `POST /api/v1/backups/{name}/restore` |  |

### `/api/v1/bedroom`

| Route | What it does |
| --- | --- |
| `GET /api/v1/bedroom` |  |
| `PUT /api/v1/bedroom` |  |

### `/api/v1/bins`

| Route | What it does |
| --- | --- |
| `GET /api/v1/bins` |  |
| `PUT /api/v1/bins` |  |

### `/api/v1/brain`

| Route | What it does |
| --- | --- |
| `POST /api/v1/brain/autolink` | Link the pairs the brain is confident about now, instead of at the nightly tidy. |
| `POST /api/v1/brain/capture` |  |
| `GET /api/v1/brain/debrief` | This week's Friday debrief: whether it's open, the GVW projects to pick from, and the CPEng question. |
| `POST /api/v1/brain/debrief` | File the debrief: on the project, the decision in the Decision Log, the lesson in Lessons Learned. |
| `POST /api/v1/brain/debrief/dismiss` | 10.33: nothing to add this week; the card stays away until next Friday (SirisAI 7.29). |
| `POST /api/v1/brain/delete` | Delete a note: it leaves search, links and the map. Restorable unless `permanent`. |
| `GET /api/v1/brain/deleted` | Deleted notes, newest first, and whether each can be restored. |
| `POST /api/v1/brain/done` | Tick an overdue task in its note, or (no task) mark a project finished. |
| `POST /api/v1/brain/edit` | Edit a note's text (7.2, SirisAI 4.4, engine 1.98). Refused if it changed since `version` was read. |
| `GET /api/v1/brain/inbox/count` | How many notes wait in the brain's inbox: all the tab bar's dot needs, without working out the insights. |
| `GET /api/v1/brain/insights` | How Siris is growing and what needs attention, worked out by the vault's engine. |
| `POST /api/v1/brain/link` | Accept a "could be linked" suggestion: the two notes are linked both ways. |
| `POST /api/v1/brain/looks-right` | Keep a link Siris made itself; it leaves the review list for good (11.5). |
| `GET /api/v1/brain/map.html` | Siris' living mind map, drawn fresh from the vault by SirisAI. The PWA renders it in a sandboxed iframe, so it never sees the SirisAI key. |
| `POST /api/v1/brain/not-related` | Dismiss a "could be linked" suggestion so it isn't suggested again. |
| `GET /api/v1/brain/note` | One note with its links and backlinks, to review or unlink its connections. |
| `POST /api/v1/brain/purge` | Permanently remove a note that's already deleted. |
| `GET /api/v1/brain/recent` | The most recently updated Siris notes (titles), for Get ready for offline. |
| `POST /api/v1/brain/restore` | Undo a delete: the note returns where it was, with its connections. |
| `GET /api/v1/brain/review` | This week's notes to check (11.6.1): five picked each Sunday, the most connected unchecked notes Siris wrote, each with its card. Ones checked or put off leave it, and nothing new comes until next Sunday. |
| `POST /api/v1/brain/review/later` | "Not now" on the Is this right? card: off this week's card (it can come up another week). |
| `POST /api/v1/brain/reviewed` | Brad checked this note and it's right: it leaves the queue and Siris trusts it a little more. |
| `GET /api/v1/brain/search` |  |
| `POST /api/v1/brain/skip-link` | Skip a "could be linked" suggestion: off this week's list and not suggested again (11.5). |
| `GET /api/v1/brain/today` |  |
| `POST /api/v1/brain/unlink` | Disconnect two notes both ways; nothing automatic links them again. |

### `/api/v1/brief`

| Route | What it does |
| --- | --- |
| `GET /api/v1/brief` |  |
| `POST /api/v1/brief/dismiss` |  |
| `GET /api/v1/brief/history` | Every kept brief (60 days), newest first: date, weekday and headline. |
| `GET /api/v1/brief/history/{day}` |  |
| `GET /api/v1/brief/status` |  |

### `/api/v1/budget`

| Route | What it does |
| --- | --- |
| `GET /api/v1/budget` |  |
| `PUT /api/v1/budget` |  |
| `DELETE /api/v1/budget/accounts/{account_id}` |  |
| `PATCH /api/v1/budget/accounts/{account_id}` |  |
| `GET /api/v1/budget/actuals` |  |
| `POST /api/v1/budget/actuals/import` |  |
| `GET /api/v1/budget/actuals/imports` |  |
| `DELETE /api/v1/budget/actuals/imports/{import_id}` |  |
| `PUT /api/v1/budget/actuals/{tx_id}` |  |
| `GET /api/v1/budget/balances` |  |
| `POST /api/v1/budget/balances` |  |
| `GET /api/v1/budget/cashflow` |  |
| `GET /api/v1/budget/from-bills` | Each subscription or bill SirisAI found in email, as an expense line (renewals are taken as monthly unless the email says yearly). |
| `GET /api/v1/budget/pay-days` |  |
| `GET /api/v1/budget/recurring` |  |
| `PUT /api/v1/budget/recurring/{rec_id}` |  |
| `GET /api/v1/budget/split` | The saved split between incomes, checked against today's budget (11.12). |
| `PUT /api/v1/budget/split` | Keep a split: worked out now, and checked against the budget from then on (11.12). |
| `POST /api/v1/budget/split/preview` | What a split would be, without keeping it (11.12). |
| `GET /api/v1/budget/suggestions` |  |
| `DELETE /api/v1/budget/tap-key` |  |
| `GET /api/v1/budget/tap-key` | Whether the Apple Pay Shortcut has a key, and how it's going this month. |
| `POST /api/v1/budget/tap-key` | A new key for the Apple Pay Shortcut, shown once (the old one stops). |

### `/api/v1/budget-tap`

| Route | What it does |
| --- | --- |
| `POST /api/v1/budget-tap` | From the Apple Pay Shortcut (11.17): no sign-in, its own key, and it can only add a spend. |

### `/api/v1/calendar`

| Route | What it does |
| --- | --- |
| `GET /api/v1/calendar` |  |

### `/api/v1/capture`

| Route | What it does |
| --- | --- |
| `POST /api/v1/capture/route` |  |
| `POST /api/v1/capture/undo` |  |

### `/api/v1/career`

| Route | What it does |
| --- | --- |
| `GET /api/v1/career` |  |
| `PUT /api/v1/career` |  |
| `GET /api/v1/career/application` | The three forms, your answers so far and what's left. |
| `PUT /api/v1/career/application` |  |
| `GET /api/v1/career/application/draft/cpd/{question_id}` | A starting answer from your CPD records for one questionnaire question. |
| `GET /api/v1/career/application/draft/element/{element_id}` | A Part 3 comment started from your latest evidence for the element. |
| `DELETE /api/v1/career/application/{doc_id}/file` |  |
| `GET /api/v1/career/application/{doc_id}/file` |  |
| `POST /api/v1/career/application/{doc_id}/file` | Your filled-in copy of a form (PDF or Word), kept with the career file. |
| `GET /api/v1/career/claims` | Each Stage 2 element with the evidence tagged to it, for drafting claims. |
| `GET /api/v1/career/claims/{element_id}` | The structured draft, plus first-person prose from the local model when asked for and available. |
| `POST /api/v1/career/claims/{element_id}/save` | Into Siris (through SirisAI), titled per element so saving again adds to the same note instead of making another. |
| `POST /api/v1/career/cpd/import` |  |
| `GET /api/v1/career/cpd/plan` | CPD pacing for the next 12 months, with what to look for where you're behind, and matching SirisLearn courses when SirisLearn is connected. |
| `GET /api/v1/career/cpd/suggestions` | Calendar events from the last and next 30 days that look like CPD and aren't logged in Engineers Australia yet. |
| `POST /api/v1/career/cpd/suggestions/{key}` | Logged in Engineers Australia, or not CPD: either way, stop suggesting it. |
| `PUT /api/v1/career/cpd/{record_id}/category` | Correct a guessed category (null puts the guess back). Survives re-imports. |
| `GET /api/v1/career/overview` |  |

### `/api/v1/catchups`

| Route | What it does |
| --- | --- |
| `GET /api/v1/catchups` |  |
| `PUT /api/v1/catchups/{person_id}` |  |
| `POST /api/v1/catchups/{person_id}/done` |  |

### `/api/v1/command`

| Route | What it does |
| --- | --- |
| `POST /api/v1/command` |  |

### `/api/v1/engineering`

| Route | What it does |
| --- | --- |
| `GET /api/v1/engineering/calculations` |  |
| `POST /api/v1/engineering/calculations` |  |
| `DELETE /api/v1/engineering/calculations/{calculation_id}` |  |
| `GET /api/v1/engineering/calculations/{calculation_id}` |  |
| `POST /api/v1/engineering/calculations/{calculation_id}/check` | 11.19: mark a calculation as checked (by whom, today), or clear it with an empty name. |
| `GET /api/v1/engineering/calculations/{calculation_id}/pdf` |  |
| `GET /api/v1/engineering/calculators` |  |
| `POST /api/v1/engineering/calculators/{calculator_id}/run` |  |
| `GET /api/v1/engineering/sirishydro/evidence` |  |
| `GET /api/v1/engineering/sirishydro/history` |  |
| `DELETE /api/v1/engineering/sirishydro/history/{record_id}` |  |
| `GET /api/v1/engineering/standards` |  |
| `POST /api/v1/engineering/standards` |  |
| `GET /api/v1/engineering/standards/updates` | 11.21: when the library was last checked for new versions, what changed, and what couldn't be checked. |
| `POST /api/v1/engineering/standards/updates/check` |  |
| `DELETE /api/v1/engineering/standards/{document_id}` |  |
| `PATCH /api/v1/engineering/standards/{document_id}` |  |
| `GET /api/v1/engineering/standards/{document_id}/file` |  |
| `GET /api/v1/engineering/standards/{document_id}/pages/{page}` |  |
| `POST /api/v1/engineering/standards/{document_id}/replace` |  |
| `POST /api/v1/engineering/standards/{document_id}/restore` |  |

### `/api/v1/facts`

| Route | What it does |
| --- | --- |
| `GET /api/v1/facts` |  |

### `/api/v1/fitness`

| Route | What it does |
| --- | --- |
| `GET /api/v1/fitness` |  |
| `PUT /api/v1/fitness/goal` |  |

### `/api/v1/fuel`

| Route | What it does |
| --- | --- |
| `GET /api/v1/fuel` |  |
| `PUT /api/v1/fuel/settings` |  |

### `/api/v1/garden`

| Route | What it does |
| --- | --- |
| `GET /api/v1/garden` |  |
| `PUT /api/v1/garden` |  |
| `POST /api/v1/garden/watered` |  |

### `/api/v1/glance`

| Route | What it does |
| --- | --- |
| `GET /api/v1/glance` |  |
| `DELETE /api/v1/glance/key` |  |
| `GET /api/v1/glance/key` |  |
| `POST /api/v1/glance/key` |  |

### `/api/v1/goals`

| Route | What it does |
| --- | --- |
| `GET /api/v1/goals` |  |
| `POST /api/v1/goals` |  |
| `GET /api/v1/goals/prompt` |  |
| `POST /api/v1/goals/review` |  |
| `POST /api/v1/goals/set` |  |
| `GET /api/v1/goals/steer` |  |
| `DELETE /api/v1/goals/{goal_id}` |  |
| `PATCH /api/v1/goals/{goal_id}` |  |

### `/api/v1/gym`

| Route | What it does |
| --- | --- |
| `GET /api/v1/gym` |  |
| `GET /api/v1/gym/anatomy` | The main muscle and helpers an exercise's name says (9.44), to fill the new-exercise form. |
| `GET /api/v1/gym/backups` |  |
| `POST /api/v1/gym/backups/restore` |  |
| `GET /api/v1/gym/body` |  |
| `POST /api/v1/gym/builder` | A routine drafted from a goal, to edit and save (it isn't saved here). |
| `POST /api/v1/gym/cleanup` | Take out exercises with nothing logged (6.95): empty entries in workouts, and your own exercises with no data that no routine uses. Workouts themselves are kept; a copy of gym.json is saved first. |
| `GET /api/v1/gym/coach` | The week's one or two changes, from SirisAI (training, sleep, recovery, protein). Nothing when it isn't connected. |
| `POST /api/v1/gym/deload` | Start (or end) a deload week: half the sets, 10% lighter, no records. |
| `GET /api/v1/gym/duplicates` |  |
| `POST /api/v1/gym/duplicates/dismiss` | These two aren't the same (8.6): they won't be suggested as a pair again. |
| `POST /api/v1/gym/effort/refresh` |  |
| `GET /api/v1/gym/exercise-fixes` |  |
| `POST /api/v1/gym/exercise-fixes` | Apply the suggested tidy-up to these exercises (a copy of the file first), or say they're right as they are. |
| `POST /api/v1/gym/exercises` |  |
| `DELETE /api/v1/gym/exercises/{exercise_id}` |  |
| `GET /api/v1/gym/exercises/{exercise_id}` |  |
| `PUT /api/v1/gym/exercises/{exercise_id}` | Change one of your own exercises (8.7). Its sets stay as they are. |
| `PUT /api/v1/gym/exercises/{exercise_id}/cues` | Your form cues for an exercise (8.8); empty puts back the built-in ones, if it has any. |
| `GET /api/v1/gym/exercises/{exercise_id}/image` | 9.7: the exercise's picture: your photo, or the library's start (frame 0) or end (frame 1) of the movement. |
| `PUT /api/v1/gym/exercises/{exercise_id}/image` | 9.7: a different library picture, no picture, or (neither) back to the automatic one. |
| `PUT /api/v1/gym/exercises/{exercise_id}/loading` | 9.6: say an exercise is assisted (the weight is help: less is harder) or done one side at a time (volume counts both sides). Works for built-in exercises too; it's worked out from the name until you do. |
| `POST /api/v1/gym/exercises/{exercise_id}/photo` | 9.7: your own picture for an exercise (the machine at your gym, say). Kept on your server only. |
| `GET /api/v1/gym/export.csv` | Every set ever logged, one row each, in kg, km and seconds (7.1). |
| `GET /api/v1/gym/export.json` |  |
| `GET /api/v1/gym/good-sessions` | 9.6: what goes with your best and worst sessions: sleep, resting heart rate, time of day, caffeine. |
| `POST /api/v1/gym/gyms/{gym_id}/swaps` | Remember that this gym needs `into` instead of `source` (8.8), or forget it. |
| `GET /api/v1/gym/heatmap` |  |
| `GET /api/v1/gym/image-search` | 9.7: pictures in the library to choose from. |
| `POST /api/v1/gym/import` |  |
| `GET /api/v1/gym/last` | What you lifted last time for each exercise (9.0): its working sets and the day. For an empty workout, an exercise added mid-workout or a swap, which have no plan to bring last time with them. `exclude` leaves out the workout being edited. |
| `GET /api/v1/gym/links` |  |
| `POST /api/v1/gym/links` | Point the routine's exercise at the one your history is under (8.7), or say it's different. |
| `POST /api/v1/gym/measurements` |  |
| `DELETE /api/v1/gym/measurements/{measurement_id}` |  |
| `POST /api/v1/gym/merge` | Merge one of your exercises into another; a copy of the file is kept first. |
| `GET /api/v1/gym/merges` |  |
| `POST /api/v1/gym/merges/{merge_id}/undo` | Unmerge (8.6): the exercise and its sets come back. A copy of the file is kept first. |
| `GET /api/v1/gym/morning` | The morning card: today's workout and readiness, and what it takes to start it. |
| `GET /api/v1/gym/muscle-trends` |  |
| `GET /api/v1/gym/next-block` |  |
| `POST /api/v1/gym/next-block` | Make the accepted changes and start the next block today. A copy of the file is kept first. |
| `GET /api/v1/gym/niggles` |  |
| `POST /api/v1/gym/niggles` |  |
| `POST /api/v1/gym/niggles/{niggle_id}/healed` |  |
| `POST /api/v1/gym/note-actions/{action_id}` | Do what a session note suggested, or leave it (11.14). |
| `POST /api/v1/gym/photos` |  |
| `DELETE /api/v1/gym/photos/{photo_id}` |  |
| `GET /api/v1/gym/photos/{photo_id}` |  |
| `GET /api/v1/gym/plan` |  |
| `GET /api/v1/gym/plates` |  |
| `GET /api/v1/gym/protein` | Today's protein against a target from your bodyweight (Apple Health, via SirisAI) and whether you trained. |
| `DELETE /api/v1/gym/rest` |  |
| `POST /api/v1/gym/rest` | A push when the rest is over (6.9), so the phone can be locked between sets. A new rest replaces the last. |
| `POST /api/v1/gym/routines` |  |
| `DELETE /api/v1/gym/routines/{routine_id}` |  |
| `PUT /api/v1/gym/routines/{routine_id}` |  |
| `POST /api/v1/gym/schedule` | A gym slot in the calendar (6.93): the first free gap that day (early, lunch, after work, then any time), shown first (dry_run) and added on a second tap, through SirisAI's calendar. |
| `GET /api/v1/gym/sessions` |  |
| `POST /api/v1/gym/sessions` |  |
| `DELETE /api/v1/gym/sessions/{session_id}` |  |
| `GET /api/v1/gym/sessions/{session_id}` | One workout in full. `watch=false` skips finding its Watch workout (SirisAI asks that way: it has the heart rate itself, and the lookup would call back into it). |
| `GET /api/v1/gym/sessions/{session_id}/effort` | The Watch's heart rate lined up with each set, and the effort per exercise, from SirisAI (6.96, SirisAI 4.28). |
| `POST /api/v1/gym/sessions/{session_id}/feel` |  |
| `PUT /api/v1/gym/sessions/{session_id}/note` | A note on a finished workout (11.14), read at once for what it asks; the local model reads it too, after. |
| `POST /api/v1/gym/sessions/{session_id}/review` | Your call on an imported day too big to be one workout. It's never deleted: "real" counts it, "wrong" keeps it out. |
| `PUT /api/v1/gym/sessions/{session_id}/sets` | Correct one exercise's working sets in a saved workout (8.7), in order, e.g. a 210 kg squat that was 21 or 70. Warm-ups and the rest of the workout stay as they were. |
| `PUT /api/v1/gym/settings` |  |
| `GET /api/v1/gym/strength` |  |
| `GET /api/v1/gym/swap` |  |
| `GET /api/v1/gym/templates` |  |
| `GET /api/v1/gym/videos` |  |
| `POST /api/v1/gym/videos` |  |
| `DELETE /api/v1/gym/videos/{video_id}` |  |
| `GET /api/v1/gym/videos/{video_id}` |  |
| `DELETE /api/v1/gym/voice-key` |  |
| `POST /api/v1/gym/voice-key` | A new key for the Siri Shortcut (8.8), shown this once. Any old one stops working. |
| `GET /api/v1/gym/voice-log` |  |
| `POST /api/v1/gym/voice-log/ack` |  |
| `GET /api/v1/gym/warmups` |  |
| `GET /api/v1/gym/year` |  |

### `/api/v1/gym-voice`

| Route | What it does |
| --- | --- |
| `POST /api/v1/gym-voice/log` |  |

### `/api/v1/handbook`

| Route | What it does |
| --- | --- |
| `GET /api/v1/handbook` | Your own handbook commands. |
| `POST /api/v1/handbook` | Add a command of your own to the handbook. |
| `DELETE /api/v1/handbook/{entry_id}` | Take one of your commands out of the handbook. |
| `PATCH /api/v1/handbook/{entry_id}` | Change one of your handbook commands. |

### `/api/v1/health`

| Route | What it does |
| --- | --- |
| `GET /api/v1/health` |  |
| `POST /api/v1/health/apple-export` |  |
| `DELETE /api/v1/health/data` |  |
| `GET /api/v1/health/export.csv` |  |
| `GET /api/v1/health/goals` |  |
| `POST /api/v1/health/goals` |  |
| `POST /api/v1/health/import` | Health Auto Export's JSON goes to SirisAI as it is (5.8): SirisAI 3.51 reads it and keeps everything (every metric, sleep, workouts) for the Health section, chat and voice. Anything else (a Shortcut's simple {date, metrics}) is passed on too. Every attempt is logged, with the reason when it fails, for the Training page. |
| `POST /api/v1/health/import/key` |  |
| `GET /api/v1/health/import/status` |  |
| `POST /api/v1/health/import/test` | Test the sync (6.93): a small Health Auto Export-shaped sample for this hour goes the same way a phone's export would, to SirisAI as a dry run (nothing is kept), and comes back with what it read. |
| `POST /api/v1/health/log` |  |
| `POST /api/v1/health/meal` |  |
| `GET /api/v1/health/report` |  |
| `GET /api/v1/health/sources` | The data inspector (6.93): each metric that day, every source's value and which one counts (from SirisAI 4.17). |
| `GET /api/v1/health/today` |  |

### `/api/v1/home`

| Route | What it does |
| --- | --- |
| `GET /api/v1/home/context` | What part of the day it is (and whether anyone's home), so Home can put the right things first: morning, work, evening, night or weekend. |
| `GET /api/v1/home/layout` |  |
| `PUT /api/v1/home/layout` |  |
| `GET /api/v1/home/schedule` |  |
| `PUT /api/v1/home/schedule` |  |
| `GET /api/v1/home/usage` |  |
| `POST /api/v1/home/usage` |  |
| `PUT /api/v1/home/usage` |  |
| `PUT /api/v1/home/usage/menu` | 11.11: the sections the side menu leaves out (Home can't be). |

### `/api/v1/homelab`

| Route | What it does |
| --- | --- |
| `GET /api/v1/homelab` |  |
| `POST /api/v1/homelab` |  |
| `DELETE /api/v1/homelab/{node_id:path}` |  |
| `PATCH /api/v1/homelab/{node_id:path}` |  |

### `/api/v1/house`

| Route | What it does |
| --- | --- |
| `GET /api/v1/house/placements` |  |
| `PUT /api/v1/house/placements` |  |

### `/api/v1/hub`

| Route | What it does |
| --- | --- |
| `GET /api/v1/hub/apps` |  |
| `GET /api/v1/hub/apps/{app_id}` |  |
| `GET /api/v1/hub/status` | Every configured app's health now and over the last 24 hours and 7 days. |
| `GET /api/v1/hub/upkeep` | Backups, a waiting SirisAI update and certificate expiry, for System status (3.6). |
| `POST /api/v1/hub/upkeep/check` | Ask SirisAI to look for a new release now. |
| `POST /api/v1/hub/upkeep/update` | Update both apps now (6.4): asks SirisAI's updater (deploy/updater.sh) for the latest release; it rebuilds and restarts SirisAI and SirisOS, and rolls back on its own if they don't come back healthy. |
| `GET /api/v1/hub/widgets` |  |

### `/api/v1/lab`

| Route | What it does |
| --- | --- |
| `GET /api/v1/lab/containers` |  |
| `POST /api/v1/lab/containers/check` |  |
| `GET /api/v1/lab/containers/history` | 11.19 (SirisAI 4.32): every update, roll-back and failure, with what each was on before, and the ones held back. |
| `POST /api/v1/lab/containers/update` |  |
| `POST /api/v1/lab/containers/{name}/{action}` | `roll-back`: back to the version before its last update, held there; `update`: update it now (and release it). |
| `GET /api/v1/lab/internet` |  |
| `PUT /api/v1/lab/internet/plan` |  |

### `/api/v1/life`

| Route | What it does |
| --- | --- |
| `GET /api/v1/life/bills` |  |
| `POST /api/v1/life/bills/scan` |  |
| `POST /api/v1/life/bills/{bill_id}/status` |  |
| `GET /api/v1/life/documents` |  |
| `POST /api/v1/life/documents` |  |
| `DELETE /api/v1/life/documents/{doc_id}` |  |
| `GET /api/v1/life/documents/{doc_id}` |  |
| `GET /api/v1/life/documents/{doc_id}/download` | 11.8.0: one receipt to save, named by date and who it's from (an email as a page that can't run anything). |
| `GET /api/v1/life/documents/{doc_id}/files/{name}` | A kept receipt's original (SirisAI 5.31). It came from an email, so the browser is told nothing in it may run. |
| `GET /api/v1/life/email` |  |
| `GET /api/v1/life/news` |  |
| `GET /api/v1/life/people` |  |
| `POST /api/v1/life/people` |  |
| `DELETE /api/v1/life/people/{person_id}` |  |
| `PUT /api/v1/life/people/{person_id}` |  |
| `GET /api/v1/life/people/{person_id}/gifts` |  |
| `GET /api/v1/life/receipts/download` | 11.8.0: receipts as a zip (a search, a date range or chosen ids), each file named by date and who it's from, with receipts.csv listing them. |
| `GET /api/v1/life/reliability` |  |
| `GET /api/v1/life/speed` |  |
| `GET /api/v1/life/things` |  |
| `POST /api/v1/life/things` |  |
| `POST /api/v1/life/things/from-email` | Receipts in email are kept, and what was bought goes in Things (SirisAI 5.31). The local model reads up to 25 emails, so it can take a few minutes. |
| `DELETE /api/v1/life/things/{thing_id}` |  |
| `PUT /api/v1/life/things/{thing_id}` |  |
| `GET /api/v1/life/travel` |  |
| `POST /api/v1/life/travel/away` |  |
| `GET /api/v1/life/trial` |  |
| `POST /api/v1/life/trial` |  |

### `/api/v1/links`

| Route | What it does |
| --- | --- |
| `GET /api/v1/links` |  |
| `PUT /api/v1/links` |  |
| `GET /api/v1/links/status` | {link id: {up, status, ms}} for every link. LAN apps often use self-signed certificates, so certificates aren't verified here. |

### `/api/v1/machine`

| Route | What it does |
| --- | --- |
| `GET /api/v1/machine` |  |

### `/api/v1/maintenance`

| Route | What it does |
| --- | --- |
| `GET /api/v1/maintenance` |  |
| `POST /api/v1/maintenance/appliances` |  |
| `DELETE /api/v1/maintenance/appliances/{appliance_id}` |  |
| `PATCH /api/v1/maintenance/appliances/{appliance_id}` |  |
| `GET /api/v1/maintenance/appliances/{appliance_id}/manual` |  |
| `POST /api/v1/maintenance/appliances/{appliance_id}/manual` |  |
| `POST /api/v1/maintenance/jobs` |  |
| `DELETE /api/v1/maintenance/jobs/{job_id}` |  |
| `PATCH /api/v1/maintenance/jobs/{job_id}` |  |
| `POST /api/v1/maintenance/jobs/{job_id}/done` |  |
| `POST /api/v1/maintenance/jobs/{job_id}/snooze` |  |
| `POST /api/v1/maintenance/manuals/ask` | Ask the uploaded manuals (6.4): {answer, sources: [{appliance, page, snippet}], note?}. |

### `/api/v1/meals`

| Route | What it does |
| --- | --- |
| `GET /api/v1/meals` |  |
| `GET /api/v1/meals/recipes` |  |
| `GET /api/v1/meals/shopping` |  |
| `POST /api/v1/meals/shopping` |  |
| `PUT /api/v1/meals/staples` |  |
| `GET /api/v1/meals/tonight` | Tonight's dinner: Mealie's plan when it's set up (so one planned in Mealie shows too), else what was planned here. |
| `DELETE /api/v1/meals/{on}` |  |
| `PUT /api/v1/meals/{on}` |  |

### `/api/v1/memories`

| Route | What it does |
| --- | --- |
| `GET /api/v1/memories` | SirisAI's own memories (what `remember` saved), newest or best-matching first. |
| `DELETE /api/v1/memories/{memory_id}` | Delete one of SirisAI's memories. There's no undo. |
| `PUT /api/v1/memories/{memory_id}` | Correct one of SirisAI's memories (7.2, SirisAI 4.4). |

### `/api/v1/mind`

| Route | What it does |
| --- | --- |
| `GET /api/v1/mind` |  |
| `GET /api/v1/mind/clarity` |  |
| `POST /api/v1/mind/clarity/check` |  |
| `PUT /api/v1/mind/clarity/nudge` |  |
| `PUT /api/v1/mind/clarity/plan` |  |
| `POST /api/v1/mind/clarity/start` |  |
| `POST /api/v1/mind/clarity/urge` |  |
| `GET /api/v1/mind/habits` |  |
| `POST /api/v1/mind/habits` |  |
| `PATCH /api/v1/mind/habits/{habit_id}` |  |
| `POST /api/v1/mind/habits/{habit_id}/check` |  |
| `GET /api/v1/mind/journal` |  |
| `POST /api/v1/mind/journal` |  |
| `DELETE /api/v1/mind/journal/{entry_id}` |  |
| `POST /api/v1/mind/lock` |  |
| `POST /api/v1/mind/sessions` |  |
| `POST /api/v1/mind/unlock` |  |
| `POST /api/v1/mind/unlock/options` |  |

### `/api/v1/netwatch`

| Route | What it does |
| --- | --- |
| `GET /api/v1/netwatch` |  |
| `PATCH /api/v1/netwatch/{node_id}` | Name it, say whose it is and what it is (6.2); its room comes from the 3D house. |
| `POST /api/v1/netwatch/{node_id}/block` |  |
| `POST /api/v1/netwatch/{node_id}/important` |  |
| `POST /api/v1/netwatch/{node_id}/trust` |  |

### `/api/v1/patterns`

| Route | What it does |
| --- | --- |
| `GET /api/v1/patterns` |  |

### `/api/v1/plan`

| Route | What it does |
| --- | --- |
| `GET /api/v1/plan/today` |  |

### `/api/v1/power`

| Route | What it does |
| --- | --- |
| `GET /api/v1/power` |  |

### `/api/v1/presence`

| Route | What it does |
| --- | --- |
| `GET /api/v1/presence` | Home or away, and the phones that count as someone home (7.2, SirisAI 4.4). |
| `GET /api/v1/presence/away` | 8.5: what SirisAI does when everyone's out: off, ask or auto (SirisAI 5.63). |
| `PUT /api/v1/presence/away` |  |
| `PUT /api/v1/presence/phones` | The phones added here that count as home: away only once all of them have left. |

### `/api/v1/projects`

| Route | What it does |
| --- | --- |
| `GET /api/v1/projects` |  |
| `POST /api/v1/projects` |  |
| `GET /api/v1/projects/current` |  |
| `PUT /api/v1/projects/current` |  |
| `GET /api/v1/projects/{project_id}` |  |
| `PATCH /api/v1/projects/{project_id}` |  |
| `GET /api/v1/projects/{project_id}/graph` |  |
| `GET /api/v1/projects/{project_id}/relationships` |  |
| `POST /api/v1/projects/{project_id}/relationships` |  |
| `DELETE /api/v1/projects/{project_id}/relationships/{relationship_id}` |  |

### `/api/v1/push`

| Route | What it does |
| --- | --- |
| `GET /api/v1/push/act` |  |
| `POST /api/v1/push/act` |  |
| `POST /api/v1/push/act/opened` | A notification was tapped (from the service worker, no sign-in): only counts keys SirisOS actually pushed. |
| `POST /api/v1/push/active` | The app is open on this device (every minute while it's on screen); returns the in-app banners waiting. |
| `GET /api/v1/push/digest` |  |
| `PUT /api/v1/push/digest` |  |
| `GET /api/v1/push/key` |  |
| `POST /api/v1/push/seen` | Cards on screen: their notifications won't be sent (and any waiting are dropped). |
| `GET /api/v1/push/smart` |  |
| `PUT /api/v1/push/smart` |  |
| `PUT /api/v1/push/smart/kinds/{kind}` |  |
| `POST /api/v1/push/subscribe` |  |
| `GET /api/v1/push/subscriptions` |  |
| `POST /api/v1/push/test` |  |
| `POST /api/v1/push/unsubscribe` |  |

### `/api/v1/recap`

| Route | What it does |
| --- | --- |
| `GET /api/v1/recap` |  |
| `POST /api/v1/recap/{month}/seen` |  |

### `/api/v1/renewals`

| Route | What it does |
| --- | --- |
| `GET /api/v1/renewals` |  |
| `POST /api/v1/renewals` |  |
| `DELETE /api/v1/renewals/{item_id}` |  |
| `PATCH /api/v1/renewals/{item_id}` |  |

### `/api/v1/resurface`

| Route | What it does |
| --- | --- |
| `GET /api/v1/resurface` |  |
| `POST /api/v1/resurface/respond` |  |

### `/api/v1/review`

| Route | What it does |
| --- | --- |
| `GET /api/v1/review` |  |
| `POST /api/v1/review` |  |

### `/api/v1/search`

| Route | What it does |
| --- | --- |
| `GET /api/v1/search` |  |

### `/api/v1/security`

| Route | What it does |
| --- | --- |
| `GET /api/v1/security` |  |
| `PUT /api/v1/security/password-signin` | Passkey only (7.2): turn password sign-in off once there's a passkey, or back on. |

### `/api/v1/setup`

| Route | What it does |
| --- | --- |
| `GET /api/v1/setup` |  |

### `/api/v1/share`

| Route | What it does |
| --- | --- |
| `POST /api/v1/share` |  |
| `DELETE /api/v1/share/key` |  |
| `GET /api/v1/share/key` |  |
| `POST /api/v1/share/key` |  |

### `/api/v1/siris-projects`

| Route | What it does |
| --- | --- |
| `GET /api/v1/siris-projects` |  |
| `POST /api/v1/siris-projects` |  |
| `DELETE /api/v1/siris-projects/{title}` | The project's note goes to Siris' deleted notes, from where it can come back (never permanently from here). |
| `GET /api/v1/siris-projects/{title}` |  |
| `POST /api/v1/siris-projects/{title}/done` |  |
| `POST /api/v1/siris-projects/{title}/restore` |  |
| `POST /api/v1/siris-projects/{title}/tasks` | Plain words like the Tasks screen ("send levels friday"); the project's name goes in the notes, so it shows on this page. |

### `/api/v1/standby`

| Route | What it does |
| --- | --- |
| `GET /api/v1/standby` |  |
| `PUT /api/v1/standby` |  |

### `/api/v1/tasks`

| Route | What it does |
| --- | --- |
| `GET /api/v1/tasks` | At the weekend, work tasks are left out unless ?all=true (9.51). |
| `POST /api/v1/tasks` |  |
| `GET /api/v1/tasks/lists` | Home Assistant's to-do lists (a shopping list, chores), through SirisAI. |
| `POST /api/v1/tasks/lists/{entity_id}/done` |  |
| `POST /api/v1/tasks/lists/{entity_id}/items` |  |
| `DELETE /api/v1/tasks/{task_id}` |  |
| `PATCH /api/v1/tasks/{task_id}` |  |
| `POST /api/v1/tasks/{task_id}/done` |  |
| `POST /api/v1/tasks/{task_id}/snooze` |  |

### `/api/v1/tax`

| Route | What it does |
| --- | --- |
| `GET /api/v1/tax` |  |
| `POST /api/v1/tax/claims` |  |
| `DELETE /api/v1/tax/claims/{claim_id}` |  |
| `PUT /api/v1/tax/claims/{claim_id}` |  |
| `GET /api/v1/tax/export` |  |
| `POST /api/v1/tax/not-tax/{doc_id}` |  |
| `PUT /api/v1/tax/years/{fy}` |  |

### `/api/v1/terminal`

| Route | What it does |
| --- | --- |
| `GET /api/v1/terminal` |  |
| `POST /api/v1/terminal/2fa/confirm` |  |
| `POST /api/v1/terminal/2fa/off` |  |
| `POST /api/v1/terminal/2fa/setup` |  |
| `GET /api/v1/terminal/commands` |  |
| `POST /api/v1/terminal/commands` |  |
| `DELETE /api/v1/terminal/commands/{command_id}` |  |
| `POST /api/v1/terminal/run` | Run a shortcut on the host its ticket was unlocked for (the ticket works once). |
| `POST /api/v1/terminal/unlock` |  |

### `/api/v1/trails`

| Route | What it does |
| --- | --- |
| `GET /api/v1/trails` |  |
| `POST /api/v1/trails/apple-export` |  |
| `GET /api/v1/trails/import` |  |
| `DELETE /api/v1/trails/{walk_id}` |  |
| `GET /api/v1/trails/{walk_id}` |  |
| `PATCH /api/v1/trails/{walk_id}` |  |
| `GET /api/v1/trails/{walk_id}/gpx` |  |
| `DELETE /api/v1/trails/{walk_id}/join` |  |
| `POST /api/v1/trails/{walk_id}/join` |  |
| `POST /api/v1/trails/{walk_id}/photos` |  |
| `DELETE /api/v1/trails/{walk_id}/photos/{photo_id}` |  |
| `GET /api/v1/trails/{walk_id}/photos/{photo_id}` |  |
| `DELETE /api/v1/trails/{walk_id}/trim` |  |
| `POST /api/v1/trails/{walk_id}/trim` |  |

### `/api/v1/training`

| Route | What it does |
| --- | --- |
| `GET /api/v1/training` |  |
| `GET /api/v1/training/calendar.ics` |  |
| `GET /api/v1/training/feed` |  |
| `POST /api/v1/training/feed/new` |  |
| `DELETE /api/v1/training/race` |  |
| `PUT /api/v1/training/race` |  |

### `/api/v1/travel`

| Route | What it does |
| --- | --- |
| `GET /api/v1/travel` |  |
| `POST /api/v1/travel` |  |
| `GET /api/v1/travel/current` |  |
| `DELETE /api/v1/travel/{trip_id}` |  |
| `PATCH /api/v1/travel/{trip_id}` |  |

### `/api/v1/trends`

| Route | What it does |
| --- | --- |
| `GET /api/v1/trends` |  |

### `/api/v1/updates`

| Route | What it does |
| --- | --- |
| `GET /api/v1/updates` | The running version against main's on GitHub, and the last update's log. |

### `/api/v1/wall`

| Route | What it does |
| --- | --- |
| `GET /api/v1/wall` |  |
| `DELETE /api/v1/wall/key` |  |
| `GET /api/v1/wall/key` |  |
| `POST /api/v1/wall/key` |  |

### `/api/v1/watch`

| Route | What it does |
| --- | --- |
| `GET /api/v1/watch/tonight` |  |

### `/api/v1/week`

| Route | What it does |
| --- | --- |
| `GET /api/v1/week` |  |

### `/api/v1/weekend`

| Route | What it does |
| --- | --- |
| `GET /api/v1/weekend` |  |
| `PUT /api/v1/weekend/routes` |  |

### `/api/v1/work`

| Route | What it does |
| --- | --- |
| `GET /api/v1/work` |  |
| `POST /api/v1/work/cpd` |  |
| `POST /api/v1/work/focus` |  |
| `PUT /api/v1/work/settings` |  |
| `GET /api/v1/work/timesheet` |  |
| `POST /api/v1/work/timesheet` |  |
| `DELETE /api/v1/work/timesheet/{entry_id}` |  |
| `PATCH /api/v1/work/timesheet/{entry_id}` |  |
| `POST /api/v1/work/todo-done` |  |
| `POST /api/v1/work/wrapup` |  |

### `/api/v1/wrapup`

| Route | What it does |
| --- | --- |
| `GET /api/v1/wrapup` |  |
| `POST /api/v1/wrapup` |  |
| `POST /api/v1/wrapup/cpd/{key}` |  |

### `Other`

| Route | What it does |
| --- | --- |
| `GET /` |  |
| `GET /health` |  |

<!-- routes:end -->
