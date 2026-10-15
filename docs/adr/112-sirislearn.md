# ADR 112: SirisLearn in the hub

## Status

Accepted (2026-10-15).

## Context

Brad wants a private learning app, something like LinkedIn Learning for one
person: give it a topic and it writes a course of lessons, each followed by
a 10-question quiz (multiple choice and written answers, some about a
picture), with learning history, streaks and achievements.

Unlike Career (ADR 111), this is a separate app, **SirisLearn**
(`bradmairs/SirisLearn`, port 8100):

- It's its own domain with its own data (courses, lessons, quiz attempts,
  history) and its own model costs, and nothing else in SirisOS needs it.
- Writing a course is long-running background work against Claude; keeping
  it out of the SirisOS container keeps the hub fast and simple.
- It's used on its own for long stretches (reading and quizzes), like the
  other apps SirisOS links to.

It uses the SirisOS Liquid Glass design system (`glass.css` copied across)
so it looks like part of the suite.

## Decision

SirisOS gets a `SirisLearnConnector` (`app/hub/connectors/sirislearn.py`),
category *life*, icon a graduation cap. SirisLearn exposes a small hub API
for it, read with a shared key:

| SirisLearn route | Used for |
| --- | --- |
| `GET /api/hub/v1/status` | Tile status and version |
| `GET /api/hub/v1/summary` | The widget, and the inbox item below |
| `GET /api/hub/v1/search?q=` | ⌘K search (courses and lessons) |

All take `X-API-Key: <SIRISLEARN_HUB_KEY>`, the same value in both `.env`
files. Links come back as paths in SirisLearn (`/lesson/<id>`), and the
connector puts `SIRISLEARN_PUBLIC_URL` (or `SIRISLEARN_URL`) in front.

- **Widget "Learning"**: Streak (days; good once today's quiz is done,
  warning while it's at risk), Today (XP against the daily goal), Level,
  active Courses; items: the streak warning, *Next: <lesson>* with course
  progress, and recently unlocked awards.
- **Search**: SirisLearn's own search, through the generic connector search
  (ADR 109), as its own group.
- **Inbox**: SirisOS's own item "Your N-day learning streak ends at
  midnight" (severity info) when the widget's Streak metric is flagged. Its
  key includes the date, so dismissing it lasts for the day. It opens the
  next lesson.

## Consequences

- Without `SIRISLEARN_URL` and `SIRISLEARN_HUB_KEY` the tile shows as not
  configured; a wrong key shows it degraded ("Unauthorised").
- The hub contract lives in SirisLearn's `app/hub.py` and README; change it
  together with this connector and its tests (`test_hub.py`,
  `test_search.py`).
