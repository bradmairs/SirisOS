# ADR 021 — Synology Hyper Backup monitoring

## Status

Accepted.

## Context

SirisOS already monitors Synology DSM, disks and volumes through the Integration Framework. Hyper Backup is the next data-protection signal, but its task API varies by DSM/Hyper Backup package version and is not documented as consistently as DSM authentication/API discovery.

## Decision

SirisOS will monitor Hyper Backup through the existing backend-side Synology DSM session. The backend discovers DSM APIs at runtime and only enables task monitoring when `SYNO.Backup.Task` is exposed to the configured DSM account.

For each task, SirisOS calls the task list endpoint and then performs a best-effort status query. It normalises task name, state, last result, last-finish timestamp, next-run timestamp and destination when those fields are supplied by DSM. Missing optional fields do not make the Synology connector unhealthy.

The Flutter client receives only the authenticated SirisOS snapshot. DSM credentials and session IDs never leave the backend.

A failed last result activates a critical Notification Policy and therefore automatically participates in Mission Control wake behaviour, deterministic briefings and Siris Score penalties. Backup-state changes publish the normal Homelab module event rather than creating a parallel event system.

A dedicated `homelab.backups` widget presents current task/running/failure counts separately from NAS storage health.

## History boundary

This release does not claim persistent long-term backup analytics. DSM's current task status/last-result data is treated as the authoritative live snapshot. Thirty-day success rate, duration trends, failure history and schedule-aware staleness require SirisOS-side persisted observations and remain follow-on work.

## Consequences

- Hyper Backup monitoring survives DSM/package field differences through defensive parsing.
- Unsupported optional task data degrades gracefully.
- Existing Synology configuration is reused; no additional secret is required.
- Backup failures immediately use the established Notification Policy, Briefing and Mission Control infrastructure.
- Rich historical analytics can later be added without changing the connector contract.
