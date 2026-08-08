# ADR 030 — Capability Framework foundation

## Status

Accepted.

## Context

SirisOS needs a stable way for planners, playbooks, SirisAI/Hermes, modules and future automation to ask what the platform can currently do without depending on connector-specific implementation details. The Action Framework has been discussed but is not yet implemented in the repository, so capability discovery must remain separate from execution.

## Decision

Introduce a declarative `SirisCapabilityRegistry` in SirisCore.

Each capability has a stable ID, title, description, provider ID, kind, risk and confirmation metadata. Availability is resolved from `SirisIntegrationManager` health rather than by calling providers directly.

Healthy providers expose their declared capabilities. Degraded providers may continue to expose read-only capabilities, but control/execution capabilities fail closed. Connecting, failed, disabled and disconnected providers expose no capability availability.

Operations Center displays current capability availability and provider/risk metadata. The registry is discovery only: it does not execute commands.

## Consequences

- Operations Planner, Action Framework, Playbooks and Hermes can target stable capability IDs later.
- Capability discovery stays independent from executor implementation.
- Existing integrations require no new backend or credential surface.
- Control capabilities fail closed when provider health is degraded.
- Capability metadata can later move to provider registration/dynamic discovery without changing consumers.

## Follow-on work

- Implement the Action Framework and bind executable actions to capability IDs.
- Add provider-owned capability registration for plugin/module extensibility.
- Add argument schemas and authorization/role requirements.
- Add server-side capability exposure for Hermes and external automation.
- Add audit records for capability execution once execution exists.
