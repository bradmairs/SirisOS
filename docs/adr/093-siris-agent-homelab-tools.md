# ADR 093 — SirisAgent: Homelab Tool Scope

## Status

Accepted.

## Context

ADR 091 explicitly scoped SirisAgent v1 to Training + Health and deferred "broader scope" (Homelab: Docker status, host metrics) as a named but unchosen option. With ADR 092 having verified the tool-calling loop against a real local Ollama model, the natural next step was widening the tool set into that already-deferred domain, reusing the same deterministic services the Homelab dashboard cards already call rather than building anything new.

`DockerMonitor.collect()` and `HostMetricsCollector.collect()` were both already shipped, tested, fail-open services with no dependency on SirisAgent. `get_homelab_alerts` was considered and explicitly not added this slice -- its logic lives directly in `app/api/homelab_alerts.py`'s route handler, not a separate service object, so wrapping it cleanly would mean either extracting a service first (out of scope for a tool-scope-only slice) or calling route-handler internals directly (inconsistent with every other tool, which all wrap an existing service).

## Decision

Added two tools to `SirisAgentService`: `get_docker_status` (wraps `DockerMonitor.collect()`) and `get_host_metrics` (wraps `HostMetricsCollector.collect()`), following the exact established pattern -- a DI constructor param defaulting to the real service, a dispatch-dict entry, and a thin pass-through dispatch method with no logic of its own. The system prompt and `REFUSAL_MESSAGE` were updated from "training and health" to "training, health and homelab" scope; no other prompt rule changed.

Live-verified against the real local Ollama instance (`llama3.2:3b`), not just the scripted fake client:

- This dev Mac has neither a Docker daemon nor a node-exporter reachable, so both real collectors genuinely return `available=False` with a real connection error. Asked "Are all my Docker containers healthy right now?", the agent called `get_docker_status` and correctly reported the data as unavailable rather than inventing container names or a health count -- confirmed both via direct `curl` against `/api/v1/siris/agent/ask` and via the live browser chat UI, matching the tool's real (fake-but-honest) output.
- Asked about host CPU/memory, the agent called `get_host_metrics` and correctly reported the real lookup failure rather than fabricating a percentage.
- Re-ran both ADR 092 regression cases (an out-of-scope general-knowledge question, and a real Training tool call) against the widened prompt: the refusal sentence and the strength-score tool call both still behave exactly as before. Widening the scope description did not disturb the existing prompt-hardening work.

## Consequences

- SirisAgent's tool count goes from 9 to 11; `_TOOL_DEFINITIONS`, the dispatch dict, and the DI constructor all grew by exactly two entries each, no other logic touched.
- 3 new backend tests added (`test_get_docker_status_returns_real_container_data`, `test_get_host_metrics_returns_real_data`, `test_agent_dispatches_docker_status_through_the_full_loop`), using a fake collector object injected via the existing DI params -- same hermetic-by-construction pattern as every other test in the file, no real Docker daemon or node-exporter required to run the suite. Full backend suite: 261 passed (was 258 in ADR 092).
- Flutter chat screen's example prompts, header copy, and empty-state copy updated to mention Homelab/Docker; `flutter analyze` clean.
- `get_homelab_alerts` remains a deliberately deferred fourth Homelab tool -- revisit only alongside (or after) extracting its alert logic out of the route handler into a proper service, not by special-casing the agent to call route internals.
- Knowledge and Projects remain unscoped for the same structural reason as `get_homelab_alerts` -- neither has a clean service-layer object to wrap yet.
