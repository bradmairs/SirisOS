# ADR 012 — Siris Integration Framework

## Status
Accepted

## Context
SirisOS is expanding from a Docker-focused homelab dashboard into a platform that will integrate Docker, Home Assistant, Obsidian/Selkies, UniFi, Proxmox, NAS, health data, calendars, automation systems, and other external services.

Implementing connection lifecycle, refresh scheduling, health tracking, retries, and event publication independently for each integration would duplicate logic and make system behaviour inconsistent.

## Decision
Introduce a reusable Integration Framework in SirisCore.

Each external integration implements the `SirisConnector` contract and supplies:

- stable connector ID and label
- enabled state
- refresh interval
- connect lifecycle
- refresh lifecycle
- disconnect lifecycle

`SirisIntegrationManager` owns:

- connector registration and unregistration
- lifecycle execution
- current connector health
- scheduled refresh registration through `SirisScheduler`
- deterministic degraded/failed transitions
- publishing typed integration health and refresh events through `SirisEventBus`

Connector health uses explicit states: disconnected, connecting, healthy, degraded, failed, and disabled.

Configuration is separated from credentials. Flutter-side configuration may contain non-secret endpoints and options plus an opaque `credentialRef`, but credential values themselves must remain in the backend or another appropriate secret store.

## Consequences

- Future integrations share one lifecycle and health model.
- Mission Control, notifications, briefings, Siris Score, and AI Context can consume consistent integration events.
- Polling intervals remain connector-specific while scheduling behaviour remains centralised.
- Three consecutive failures currently escalate a connector from degraded to failed; future policy work may make this configurable.
- Existing integrations do not need to be rewritten in one large migration. Docker is the first planned migration behind the contract.
- The later Obsidian/Selkies Knowledge connector will use the same framework rather than creating a separate integration stack.

## Alternatives considered

### Keep bespoke integration services
Rejected because lifecycle, retry, scheduling, and health logic would be duplicated across every external system.

### Put all integration logic directly in the Event Bus
Rejected because the Event Bus should transport events, not own connection lifecycle or external-system state.

### Store integration credentials in Flutter preferences
Rejected because browser/client-side preference storage is not an appropriate secret store.
