# ADR 094 — SirisAgent: Homelab Alerts Tool

## Status

Accepted.

## Context

ADR 093 added `get_docker_status` and `get_host_metrics` to SirisAgent but deliberately left `get_homelab_alerts` out, because its scoring logic (host-metric thresholds, container health/stopped/update-available checks) lived directly inside the `/api/v1/homelab/alerts` route handler in `app/api/homelab_alerts.py`, not a separate service object -- adding it as a tool would have meant either calling route-handler internals directly (inconsistent with every other tool) or extracting a service first. This slice does the extraction, then adds the tool.

## Decision

Extracted the alert-scoring logic verbatim into a new `HomelabAlertService` (`app/services/homelab_alert_service.py`): `HomelabAlert`/`HomelabAlertSummary` dataclasses, the `_metric_alert()` threshold helper, and the `get_summary()` method that combines `HostMetricsCollector` and `DockerMonitor` output into a status/counts/alerts summary -- byte-for-byte the same rules the route handler used (same alert IDs, messages, and CPU/memory/disk warning/critical env-var thresholds), just moved. The route handler's response shape (`AlertResponse`/`AlertSummaryResponse` Pydantic models) is unchanged; `/alerts` now just converts the service's dataclasses to those same models.

**One wiring detail mattered:** the route module keeps `collector`/`docker_monitor` as monkeypatchable module-level singletons (existing tests in `test_recommendations.py` reassign `homelab_alerts.collector`/`homelab_alerts.docker_monitor` to fakes and expect `/alerts` to see them). Pre-binding a single `HomelabAlertService` instance at import time captured the *original* objects by reference, so those tests' monkeypatches silently stopped taking effect -- 3 tests failed with the real (unavailable) Docker result instead of the fake one. Fixed by constructing `HomelabAlertService(...)` fresh inside the route handler on each call, reading the current `collector`/`docker_monitor` module globals at call time -- the same pattern `docker_updates()` already used one function below it in the same file.

`SirisAgentService` gained a `get_homelab_alerts` tool (12th tool overall): a `homelab_alert_service` DI param defaulting to `HomelabAlertService(host_metrics_collector=self._host_metrics_collector, docker_monitor=self._docker_monitor)`, reusing the agent's own collector instances rather than constructing new ones.

Live-verified against the real local Ollama instance: asked "Are there any active homelab alerts right now?", the agent called `get_homelab_alerts` and answered "a critical alert for docker-unavailable" -- matching the real `/api/v1/homelab/alerts` endpoint's own output exactly (`status: critical`, `critical_count: 1`, same alert id and message), confirmed by calling both endpoints side by side. Re-ran the out-of-scope refusal and the existing `get_docker_status` tool call as regression checks -- both still correct.

**One pre-existing, unrelated wording quirk observed while retesting `get_docker_status`:** across a few repeated calls, the model's phrasing for "Docker monitoring is unavailable" varied between an accurate "could not be retrieved" and a slightly loose "not healthy" -- the underlying real error message was correctly cited every time, and no container name, count, or health status was ever invented. This is the same class of small-model wording variance ADR 092 already documented, not a new grounding failure, and isn't chased further here.

## Consequences

- SirisAgent's tool count goes from 11 to 12. Alert-scoring logic now exists in exactly one place (`HomelabAlertService`), reused by the `/alerts` REST endpoint, the Recommendation Engine (`app/api/recommendations.py`, unchanged, still calls the route handler), and SirisAgent.
- 5 new tests in `test_homelab_alert_service.py` covering the healthy/warning/critical thresholds, host-unavailable, docker-unavailable, and all three container alert kinds directly against the service; 2 new tests in `test_siris_agent_service.py` for the new tool's dispatch and full loop. Full backend suite: 268 passed (was 261 after ADR 093).
- The module-global-vs-captured-reference bug this slice caught and fixed before shipping is exactly the kind of thing a "just wrap it in a service" refactor can silently break when the call site doesn't preserve late-binding -- worth remembering if any other route-level singleton gets wrapped in a service the same way.
- `get_homelab_alerts` deliberately doesn't expose the underlying `check_updates` parameter `DockerMonitor.collect()` supports -- image-update checks make outbound registry calls, out of scope for a read-only status tool.
