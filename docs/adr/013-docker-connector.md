# ADR 013 — Docker Connector through the Integration Framework

## Status

Accepted.

## Context

SirisOS already had Docker monitoring, lifecycle actions, logs, host metrics, alerts, and audit history before the Integration Framework existed. Sprint 0.4.3b needed to bring Docker under the common connector lifecycle without duplicating the working backend or coupling SirisCore directly to the Docker daemon.

The same slice also needed image update awareness. SirisOS runs behind a restricted Docker socket proxy, so the first connector implementation should not depend on exposing a raw daemon event stream to the Flutter client.

## Decision

Docker is represented by a Flutter-side `DockerConnector` implementing `SirisConnector`.

The connector:

- starts only after authentication is restored or completed;
- is registered with `SirisIntegrationManager`;
- refreshes on the shared scheduler;
- consumes the existing authenticated Homelab API through `HomelabService`;
- compares deterministic snapshots and publishes `ModuleDataChanged` only for meaningful container state, health, membership, or update-availability changes;
- is disposed when the user logs out.

Image update availability is calculated on the backend. For each distinct image in a Docker collection, SirisOS compares the local repository digest with the registry digest. Registry failures do not make Docker monitoring unavailable; they are retained as per-container update-check diagnostics.

Available image updates also enter the existing Homelab alert stream as warnings, so Notification Centre, Mission Control wake behaviour, briefings, and later notification policies can consume the same source rather than inventing a separate update-alert path.

## Consequences

- Docker now follows the same lifecycle as future Home Assistant, Obsidian, UniFi, and other connectors.
- Existing container action and monitoring behaviour remains intact.
- SirisCore does not depend on Docker SDK or daemon transport details.
- Snapshot comparison works with the existing restricted Docker proxy and authenticated API.
- A native Docker daemon event stream may be added later as an optimisation without changing the connector contract.
- Registry digest checks may fail for private registries, locally built images, digest-pinned images, or registries unsupported by the current Docker credentials; these failures are non-fatal by design.

## Alternatives considered

### Connect Flutter directly to the Docker daemon

Rejected because it would expose infrastructure transport and credentials to the client and bypass the backend security boundary.

### Build a Docker-specific polling system outside the Integration Manager

Rejected because it would duplicate scheduler, health, and event-bus behaviour and make later integrations inconsistent.

### Require a daemon event stream immediately

Deferred. Snapshot comparison provides the required state-change semantics now while preserving compatibility with the restricted proxy. A stream can be added later behind the same connector interface.
