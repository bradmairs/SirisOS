# ADR 109: Search everything

## Status

Accepted (2026-10-08).

## Context

Brad wanted one search box covering SirisOS and everything connected to it:
apps, widgets, Second Brain notes, SirisAI chats, and so on. The roadmap had
already listed "a command palette that searches across apps" for after the
rebuild. Several of the apps already have a search of their own, but each
one only works inside that app.

## Decision

### One palette, opened from anywhere

The palette is a Spotlight-style glass sheet over the whole shell. It
opens with **⌘K / Ctrl+K**, with **/** when you're not typing in a field,
with the search button in the sidebar (desktop), or with the search button
in the top bar (phone).

- **Keys.** ↑ and ↓ move between results, ↵ opens one, and Esc closes the
  palette.
- **Recent searches.** These are kept in the browser only, as a per-device
  convenience.
- **Ask Siris.** The last row always offers to ask Siris the query instead.

Screens and calculators are matched in the browser, so they show up after
the first keystroke. From two characters on, the palette also calls
`GET /api/v1/search?q=`, debounced, and cancels the previous request when
you keep typing.

### The backend fans out to every source at once

Every source runs in parallel with its own 4-second timeout. A slow or
broken source is listed in `failed` and leaves only its own group empty.

| Group | Source | Opens |
| --- | --- | --- |
| Apps | Every connector's name and description | That app's status sheet |
| On your home screen | The hub's cached widget items and metrics | The item's link, or the app |
| Links | The Links board | The link (new tab) |
| Second Brain | SirisAI `/siris/brain/search` | `/brain?q=<note>` |
| Siris chats | SirisAI's read-only `search_conversations` tool, run directly (no LLM), one result per conversation | `/assistant?c=<id>`, which reopens that chat |
| Project Management | APD PM's own `/api/search` (every register plus projects) | The project tab in APD PM |
| Engineering Archive | `/api/external/search` (assets, media including EXIF, tags and AI captions, and files including OCR text) | The asset, media item or Files page |
| Engineering Reviewer | Review names | The review |
| Engineering | Standards Library (titles and page text), SirisOS projects, SirisHydro questions | The matching screen |

### Connector contract

The connector contract gains an optional
`search(client, query) -> list[SearchHit]`. An app joins search by
implementing it, the same way an app joins the home screen with `widget()`.

### Ranking

Within a group, an exact title match ranks first. Then come titles that
start with the query, titles where one of the words starts with it, titles
that contain it, and finally results that match only in their other text.
Groups are ordered by their best result. The browser scores its own results
the same way, so instant and server results interleave sensibly.

## Consequences

- No new index or database: each app answers from its own data, so results
  are always current. The cost is that a search waits on the slowest app, up
  to the 4-second timeout. Instant local results cover that wait.
- SirisDrone, GVW Timesheets and the launch-only apps (Helmarr, JEFIT, Neo
  Server) can only be found as apps. They have no search API that SirisOS
  can reach.
- Each app's search only sees what SirisOS's service account can see. For
  APD PM, that is the VIEWER account.
