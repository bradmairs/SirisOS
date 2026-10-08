# ADR 108: Daily brief

## Status

Accepted (2026-10-08).

## Context

Brad wanted the start of each day on one screen. It should open by itself
every morning until 9 am, stay up until he closes it, and cover three
things: his day, news he'd care about, and anything else worth knowing
before he starts. Most of that data already lives in other Siris apps, and
SirisOS's rule is to surface it, not rebuild it (ADR 106).

SirisAI already has a `daily_briefing` skill, but SirisOS doesn't use it.
Running it clears SirisAI's queue of non-urgent notifications. It also
returns prose, and a dashboard needs structured data.

## Decision

### One endpoint gathers the brief

`GET /api/v1/brief` fetches every source at once. Each source has its own
timeout. When a source fails, only its section is blank, and the source is
listed in `unavailable`. That is the same rule the hub follows. The result
is cached for 10 minutes; pass `?fresh=true` to rebuild it.

| Section | Source |
| --- | --- |
| Weather now / today | SirisAI HUD; the `weather_forecast` tool |
| Schedule | `calendar_upcoming_events` (CalDAV), or `home_assistant_get_calendar_events` if CalDAV isn't set up |
| Tasks | Second Brain insights (overdue tasks, deadlines within 7 days) and APD PM's overdue or due-soon items |
| To-do | `home_assistant_get_todo_items` |
| Email | `email_list_unread` (last day; important ones listed) |
| Home & health | HUD parcels and car; `health_summary` |
| Needs a look | Hub apps that are `down` or `degraded` |
| Second Brain | Insights: inbox, auto-links, unsure links, highlights |
| News | See below |

SirisOS calls the SirisAI tools directly with `POST /siris/tools/{name}/run`.
That path never involves the LLM and adds nothing to a conversation. All of
the tools are read-only. If a tool isn't configured in SirisAI, the call
returns 404 and its section is left out.

The "At a glance" lines are written by plain rules, not an LLM: rain worth a
jacket, the first meeting, urgent tasks, important email, apps that are down,
and the inbox. They stay fast and predictable.

### News comes from the Second Brain

- **Topics.** The "Topics, in order" list in the vault note **Daily Briefing
  Preferences** becomes one news search per topic. Earlier topics rank
  higher. Edit the note and the brief follows it. If the note doesn't exist,
  a default list is used.
- **Ranking.** Interests are the `[[linked]]` notes in that note and in
  **Brad Mairs**, plus this week's hot tags from the brain insights. A story
  that mentions one of them ranks above a generic story in the same topic,
  and the matched interest is shown on the story.
- **Feeds.** Stories come from public RSS, so no keys are needed: Google News
  search (Australian edition, last day only) for each topic, plus ABC News
  top stories. Each feed is capped at 2 MB and 8 s and parsed defensively.
  Results are cached for 30 minutes, except after a total outage.

### When it opens itself

`GET /api/v1/brief/status` returns `show: true` from `SIRISOS_BRIEF_FROM_HOUR`
(default 4) until `SIRISOS_BRIEF_UNTIL_HOUR` (default 9), in
`SIRISOS_TIMEZONE` (default Australia/Melbourne), unless the brief has been
dismissed today. `POST /api/v1/brief/dismiss` records the day in
`data/app/brief-state.json`. Because the dismissal is stored on the server,
closing the brief on the phone closes it on the desktop too.

The PWA checks the status on load, whenever it comes back to the
foreground, and every 5 minutes. If `show` is true, the brief opens as a
full-screen glass overlay. Closing it (×, Escape or "Start my day")
dismisses it for the day. The same brief is available any time at `/brief`,
from Home ("Today's brief") or the sidebar, and viewing it there doesn't
dismiss anything.

## Consequences

- No LLM, keys or new services. Everything comes from apps that already
  exist, plus public RSS.
- News quality depends on the Google News and ABC feeds. They can only be
  verified from the server, because the development sandbox can't reach
  them. If a feed fails, the brief says so in "Couldn't reach".
- Changing what news Brad sees means editing a note in his vault, not
  changing code.
