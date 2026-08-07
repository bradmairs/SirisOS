# ADR 014 — Deterministic Notification Policy Engine

## Status
Accepted

## Context
Integration refreshes occur frequently. Publishing a notification on every refresh would create duplicates, make Mission Control noisy, and make escalation timing dependent on UI behaviour rather than deterministic state.

SirisOS also needs policy outcomes to influence more than a notification list: they should be able to wake Mission Control, surface in the briefing, and affect the Siris Score without duplicating the underlying condition logic.

## Decision
Introduce a client-side `NotificationPolicyEngine` in SirisCore.

A `NotificationPolicyRule` defines:

- stable policy ID
- owning module
- title and message
- initial severity
- optional activation duration
- optional escalation duration/severity
- deterministic Siris Score penalty

The engine tracks the first time a condition becomes true. It only creates an active outcome after the configured activation duration. Repeated evaluations of the same active rule are deduplicated. If an escalation threshold is crossed, the existing outcome changes severity rather than creating a second outcome. When the condition clears, the outcome resolves and its state is removed.

Policy transitions publish typed `NotificationPolicyStateChanged` events plus the existing `NotificationStateChanged` and `ModuleDataChanged` events. This keeps existing Mission Control wake and refresh behaviour compatible without giving the policy engine UI responsibilities.

Active policy outcomes are also consumed by Mission Control briefing presentation and the deterministic Siris Score. Score effects remain explicit through each rule's `scorePenalty`.

## Initial policies
The Docker connector evaluates three rules:

- unhealthy containers: warning after 2 minutes, critical after 5 minutes
- stopped containers: warning after 2 minutes, critical after 10 minutes
- image updates available: warning immediately

These values are deterministic defaults and can later become configurable policy presets.

## Consequences

### Positive
- frequent connector refreshes do not spam notifications
- duration and escalation semantics are deterministic
- policy resolution is explicit
- Mission Control wakes through existing event infrastructure
- briefing and score reuse the same active policy state
- future connectors can add policies without duplicating timing/dedup logic

### Trade-offs
- active policy state is currently in-memory and resets with the Flutter application
- policy outcomes are not yet persisted as backend activity records
- configurable user policy editing is deferred

Persisted policy history and user-configurable policies can be added later without changing the rule/evaluation contract.
