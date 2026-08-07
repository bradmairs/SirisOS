# ADR 022 — Network UPS Tools integration

## Status

Accepted.

## Context

SirisOS needs vendor-neutral UPS monitoring without coupling the platform to one UPS brand or requiring the browser to connect directly to power hardware. The Integration Framework already provides lifecycle, scheduling, events and Notification Policies for external systems.

## Decision

Use Network UPS Tools (NUT) as the UPS integration boundary.

The SirisOS backend connects to the NUT server over its standard text protocol and exposes an authenticated `/api/v1/homelab/ups` snapshot. `NUT_HOST` is the enable/disable switch; `NUT_PORT` defaults to 3493 and `NUT_UPS_NAME` is optional. If no UPS name is supplied, SirisOS selects the first UPS returned by `LIST UPS`.

The backend reads `LIST VAR` and normalises common NUT variables including `ups.status`, `battery.charge`, `battery.runtime`, `ups.load`, `input.voltage` and `output.voltage`. Missing driver-specific variables are treated as unavailable rather than errors.

Flutter uses `UpsConnector` through `SirisIntegrationManager`. It refreshes every 15 seconds, publishes Homelab events on meaningful power/battery changes and evaluates deterministic policies for NUT unavailability, on-battery state and low-battery state.

The Mission Control widget is read-only. Automated shutdown is deliberately excluded from this slice because shutdown orchestration is a high-impact action that requires explicit host/NAS targeting, audit logging, ordering and safety controls.

## Consequences

- SirisOS can support APC, CyberPower, Eaton and other UPS devices supported by NUT without vendor-specific Flutter code.
- NUT remains optional; existing installs are unchanged when `NUT_HOST` is blank.
- Power events feed the same Event Bus, Mission Control wake, Briefing and Siris Score paths as other Homelab incidents.
- Future graceful-shutdown automation can build on the same snapshot/policy layer without changing monitoring semantics.
