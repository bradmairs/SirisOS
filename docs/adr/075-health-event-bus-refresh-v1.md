# ADR 075 — Health Event Bus Refresh v1

## Status

Accepted.

## Context

"Event Bus refresh and Health summary API" was originally one roadmap checkbox under Health Data Export REST ingestion. ADR 072 shipped the summary API and split the line in two, leaving live refresh as the last cleanly-scoped item before Sprint 0.9's remaining work turns into either new capture infrastructure (elevation/GPS, a real planner) or explicitly-speculative "Experimental" material.

The obvious framing — "publish a `ModuleDataChanged` event when new health data arrives" — turned out to have a real architectural gap once actually investigated. `SirisEventBus` is a pure in-memory, single-isolate pub/sub: every existing publisher fires as a side effect of an HTTP call *that same client just made* (e.g. `gym_service.dart` publishes after its own `POST /gym/workouts` succeeds). Health Auto Export data doesn't work that way — the iPhone automation POSTs directly to the backend's `POST /api/v1/health/ingest`, authenticated by its own dedicated token, with no currently-open Flutter session involved in that request at all. There is nothing to hook a client-side bus-publish onto, and confirmed via a full grep of the backend: there's no WebSocket/SSE/any backend-initiated push mechanism anywhere in this app to notify an open tab of a change it didn't cause itself.

## Decision

`HealthSyncWatcher` (new singleton, `apps/mobile/lib/src/core/health_sync_watcher.dart`) polls the already-existing `GET /api/v1/health/status` every 5 minutes via a `SirisScheduler` job — the same poll-then-publish shape `SirisIntegrationManager` already uses for its own connectors (UPS, Docker, Storage, etc.), the closest existing precedent for "periodically check an external source, then rebroadcast onto the event bus for other screens to react to." It compares `last_sync`/`records_received` against the previously-seen values and publishes `ModuleDataChanged(moduleId: 'health', reason: 'ingest_sync')` only when they've actually changed. The first poll after app start establishes a silent baseline rather than firing a spurious refresh just because the app happened to just launch.

`HealthScreen` and `SirisCoachScreen` (the two screens that read health-derived data — recovery baselines and the "Today" conflict card, respectively) subscribe to `SirisEventBus.instance.on<ModuleDataChanged>()`, filter to `event.moduleId == 'health'`, and call their existing `_refresh()` method — reusing the same fetch-and-`setState` logic pull-to-refresh already uses rather than building a separate "silent" refresh path. `HealthSyncWatcher.start()`/`.stop()` are registered from `AppShell`'s `initState`/`dispose` (the persistent root widget for the whole logged-in session, mounted once regardless of which module screen is currently visible) rather than from either individual screen, since the watch needs to keep running even while neither Health nor Coach happens to be the active tab.

## Consequences

- No backend changes were needed — `GET /api/v1/health/status` already existed and already returns exactly the two fields (`last_sync`, `records_received`) needed to detect a new sync.
- A background refresh currently causes the same brief loading-spinner flash a manual pull-to-refresh does, rather than a fully content-preserving silent update (`dashboard_screen.dart`'s `_lastDashboardData` pattern shows how that would be built). Deferred as polish, not core to what "live refresh" means here — the roadmap item was about the refresh happening automatically at all.
- **Flagged mid-slice**: another concurrent session is replacing Health Auto Export with Apple HealthKit. This slice was completed and merged anyway (confirmed with Brad) because it's small and additive — it only reads `GET /health/status`, never touches the ingestion endpoints or payload shape — so it carries a low conflict/rework risk even if the underlying capture mechanism changes. If HealthKit changes what `last_sync`/`records_received` mean or removes that endpoint's current shape, `HealthSyncWatcher` is the one place that would need updating.
- Verified live end-to-end with a temporarily shortened poll interval (5 seconds instead of 5 minutes, reverted before merge): POSTing new Health Auto Export data through the real ingest endpoint caused the Health screen's "Recovery vs your baseline" section to appear on its own, with no manual refresh, within one poll cycle.
