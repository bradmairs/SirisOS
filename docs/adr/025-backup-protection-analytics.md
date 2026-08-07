# ADR 025 — Backup protection analytics from completion events

## Status

Accepted

## Context

SirisOS already monitors the current state of Synology Hyper Backup tasks and persists low-frequency task-state observations through the generic History Engine. Polling state such as `failed` or `running` is useful operationally, but repeated samples cannot be treated as completed backup jobs and therefore cannot produce a trustworthy success rate.

Operations Center needs an explainable 30-day protection view without inventing statistics from polling frequency.

## Decision

Persist a discrete `synology_backup/completion` observation only when the task's latest completion changes.

Each completion observation:

- uses the task ID/name as series dimensions;
- stores `1` for a successful completion and `0` for a failed completion;
- stores the reported finish timestamp, result and destination in the short text payload;
- is deduplicated by `record_if_changed`, so repeated connector refreshes do not create duplicate runs.

The backend exposes an authenticated `/api/v1/history/backup-protection` endpoint that calculates rolling summaries from completion observations. The default window is 30 days and the API supports 1–90 days.

Operations Center consumes this deterministic summary through `HistoryService` and presents overall and per-task completion counts, failures and success rates. The panel owns a cached future and is repaint-isolated so operational event rebuilds do not create repeated analytics requests.

## Consequences

- Backup success rate represents observed completed jobs rather than poll samples.
- Existing installations begin accumulating trustworthy completion history after deployment; SirisOS does not fabricate historical runs that it has never observed.
- The first observation for each task may represent the most recent completion already reported by DSM at deployment time.
- Analytics quality depends on DSM exposing a stable last-finish/result pair.
- Schedule-aware overdue detection remains separate because it requires reliable schedule semantics, not just completion history.
- The generic History Engine remains the single persistence mechanism for this low-frequency operational history.
