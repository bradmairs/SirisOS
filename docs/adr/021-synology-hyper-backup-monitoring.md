# ADR 021 — Synology Hyper Backup monitoring

## Status

Accepted

## Context

Hyper Backup package APIs vary across DSM and package versions and are not guaranteed to be present or readable by the configured DSM account. Backup monitoring must not make the core NAS connector brittle or turn an optional integration into a deployment dependency.

## Decision

The existing `SynologyService` uses DSM's runtime API discovery and only calls advertised `SYNO.Backup.*` or `SYNO.HyperBackup.*` task/history APIs. It tries a small compatibility set of read-only list/get methods and normalizes successful responses into stable task and recent-history models.

Backup collection is best effort and isolated from DSM/storage collection. An absent package reports backup monitoring unavailable. An advertised but incompatible or unauthorized API returns a backup-specific diagnostic while DSM, disk and volume health remain available.

The normalized snapshot exposes task state, last result/run, next run, destination, up to 20 recent history entries, failure/staleness counts and the latest successful completion. Enabled tasks with no run in the last 48 hours are stale. Notification Policies raise deterministic alerts for failed and stale tasks; they remain quiet when backup monitoring is unavailable.

## Consequences

- Existing installations without Hyper Backup remain unchanged and deployable.
- DSM credentials and session identifiers remain backend-only.
- Package-version differences are contained in the backend compatibility adapter.
- A detected but unreadable package is visible as a diagnostic, not a false NAS outage or backup alert.
- Additional observed API response variants can be added to the normalizer without changing the Flutter connector contract.
