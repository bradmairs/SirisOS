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
new ones are refused (notes live in Second Brain).

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
| `GET /api/v1/brain/search?q=` · `GET /api/v1/brain/today` · `GET /api/v1/brain/insights?days=30` · `POST /api/v1/brain/capture` | Second Brain via SirisAI (insights: growth, topics, deadlines, overdue tasks, idle projects, links to make) |
| `POST /api/v1/brain/link` · `POST /api/v1/brain/not-related` · `POST /api/v1/brain/unlink` (`{a, b}`) | Link two notes, dismiss a suggestion, or disconnect two notes (never auto-linked again) |
| `POST /api/v1/brain/autolink` | Link the pairs the brain is confident about now, rather than at the nightly tidy |
| `GET /api/v1/brain/note?title=` | A note's links and backlinks |
| `GET /api/v1/brief?fresh=` | The daily brief (ADR 108): `greeting`, `headline[]`, `weather {now, today}`, `schedule[]`, `tasks[]`, `todo[]`, `email {unread, important[]}`, `health[]`, `home[]`, `apps_attention[]`, `brain`, `news {topics[{topic, stories[{title, url, source, published, matches}]}], interests_from}`, `unavailable[]`, `status`. Cached 10 minutes |
| `GET /api/v1/brief/status` · `POST /api/v1/brief/dismiss` | `{date, show, dismissed_today, from, until}`: whether the brief should open itself now; dismiss it for today (all devices) |
| `GET /api/v1/search?q=` | Search everything (ADR 109): `{query, groups[{id, label, icon, best, hits[{title, subtitle, url, external, kind, app_id, score}]}], failed[], took_ms}`. Two characters minimum; each source has a 4 s timeout |

`state` is `ok`, `degraded` (reachable, but wrong credentials or a missing
dependency such as an LLM), `down` (unreachable or timed out) or
`unconfigured`. Statuses and widgets are cached for 20 seconds; pass
`fresh=true` to bypass the cache.
