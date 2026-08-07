# ADR 028 — Configurable Digital Twin topology

## Status
Accepted

## Context

ADR 027 introduced a deterministic dependency graph, but the first graph could only contain relationships compiled into SirisOS. Real homelab topology varies by installation, especially physical UPS coverage, network dependencies, and service placement. SirisOS must allow explicit local declarations without converting correlation into assumed causation.

## Decision

The Flutter Digital Twin graph keeps immutable built-in edges for relationships SirisOS can justify from its own architecture and adds a separate persisted set of user-defined edges.

Custom topology is edited from Operations Center and stored through `SharedPreferences` using a versioned key. An edge means `dependent -> dependency`; for example `Docker -> UPS` means Docker requires that UPS. Custom edges are validated against known nodes, reject self-dependencies, ignore duplicates, and reject graph cycles before persistence.

Incident downstream-impact analysis reads the combined built-in + custom graph. A topology edit therefore changes deterministic incident impact immediately without requiring backend restart or new environment variables.

## Boundaries

This first configurable slice only connects existing Digital Twin nodes. It does not yet create arbitrary custom components, discover Docker/network topology automatically, or persist topology server-side across browsers/devices.

Physical power/network relationships remain explicit user declarations. SirisOS must never infer them merely because failures occurred at the same time.

## Consequences

- Installations can model their real UPS and infrastructure dependencies safely.
- Built-in software relationships cannot be accidentally deleted.
- Invalid or cyclic custom topology cannot poison incident traversal.
- The current persistence scope is browser/profile local; server-side topology becomes appropriate when the Digital Twin expands to multiple clients or discovered nodes.
