# ADR 107 — Performance: smoother, faster, lighter

## Status

Accepted (2026-10-03).

## Context

After the hub rebuild (ADR 106), SirisOS felt slower than it needed to.
Five causes:

- **GPU churn.** Four 70vmax wallpaper layers with `filter: blur(120px)`
  drifted forever. Every glass panel uses `backdrop-filter`, so each frame
  every panel re-blurred a changing backdrop. That caused jank on scroll and
  drained battery on iPhone, even when nothing on screen changed.
  `will-change: transform` on every interactive glass element also kept a
  GPU layer allocated per tile and button. The orb's idle breathing animated
  `box-shadow`, which forces a repaint on every frame.
- **Duplicate requests.** The sidebar, Home and Engineering each fetched and
  polled the app list, and Home and Siris each fetched the HUD. Revisiting a
  screen always started from a blank skeleton.
- **One large bundle.** Every screen shipped up front: 89 KB gzipped, with
  React in the same file, so each deploy re-downloaded everything.
- **Chat rendering.** Every streamed token re-rendered the whole
  conversation, and so did every keystroke in the composer.
- **A blocked event loop.** Standards upload ran text extraction and OCR
  (up to 300 s) inside an `async` route, freezing every other request:
  tiles, chat streams, everything. Searches and SirisHydro re-read and
  re-parsed every standard's full page index on every query. The hub opened
  a new HTTP client for each request, fetched an app's status and widget one
  after the other, and made callers wait whenever the 20 s cache expired.

## Decision

**Rendering**
- The wallpaper is a static radial-gradient image with `contain: strict`:
  no filter and no animation. The glass now blurs a static backdrop.
- Remove the permanent `will-change`.
- The orb glow moves to a `::after` layer whose `opacity` animates, which
  the GPU composites without repainting.

**Data** (`apps/web/src/api/resource.ts`)
- A small stale-while-revalidate store. One request and one poll timer per
  key, shared by every screen that reads it.
- Cached results render instantly on revisit, then refresh.
- Polling pauses while the app is in the background and catches up when it
  returns.
- The cache is cleared on sign-out.
- Used for the app list, the HUD, Brain "learned today", insights, and the
  Links launchpad and its status.

**Bundle**
- Siris, Brain, Links and Engineering are lazy routes, prefetched once the
  shell is idle.
- React and the router get their own long-cached chunk.
- nginx gzips JS, CSS and JSON. `text/event-stream` is excluded, so chat
  still streams.

**Chat**
- Stream events are folded into the message at most once per animation
  frame.
- Bubbles are memoised, with stable callbacks.

**API**
- Standards upload and revision, search, and SirisHydro evidence assembly
  run in worker threads (`asyncio.to_thread`).
- Parsed standards JSON is cached by file identity (path, mtime, size) in
  `app/services/json_cache.py`.
- Query terms and concept expansion are computed once per query rather than
  once per page.
- The hub uses one pooled keep-alive client per event loop.
- Concurrent requests for the same status or widget share one upstream call.
- Values up to 5 minutes old are served instantly while a background refresh
  runs.
- Status and widget are fetched in parallel.
- SirisAI proxy calls reuse the pool. The SSE relay keeps its own client,
  because it owns that client's lifetime.

## Consequences

- First-load JavaScript drops from 88.9 KB to 16.5 KB of app code plus a
  53.6 KB React chunk that stays cached across deploys (gzipped). Other
  screens arrive in the background.
- One app-list request on load instead of two, and none when switching
  between screens within the cache window.
- The home screen's widgets are at most one background refresh behind (up
  to 5 minutes if apps were slow), never blocked on a slow app. Pull to
  refresh (`fresh=true`) still waits for live data.
- An OCR upload no longer freezes the rest of SirisOS.
- The wallpaper no longer drifts. That was a deliberate trade of a subtle
  motion for smooth scrolling and battery life.
- Tests: backend `test_hub_performance.py` (request coalescing,
  stale-while-revalidate, parallel fetch, client reuse) and
  `test_json_cache.py`; web `resource.test.tsx` (shared request, instant
  revisit, sign-out clears).
