# ADR 081 — "Can I Train Today?" v1

## Status

Accepted.

## Context

The roadmap's Unified Training section names this exact framing: "'Can I train today?' / 'Should I run tonight?' — a natural-language front end over the same deterministic training-load and readiness data everything above already computes." Unlike most remaining roadmap items, this genuinely needed nothing new — `TrainingConflictService` (ADR 073, the Coach screen's "Today" card) and `TrainingLoadService` (ADR 069, weekly load) already compute exactly the two signals this question needs.

## Decision

Added `AskSirisService._readiness_check()`, a new recognized question pattern in the existing Ask Siris framework (ADR 071) rather than a new screen or endpoint. It matches phrasings like "can I train/run/lift/work out" or "should I train/run/lift/work out" combined with "today"/"tonight", then composes `TrainingConflictService.check()`'s `guidance` and `TrainingLoadService.weekly_load()`'s `assessment` into one answer — both already-written, human-readable sentences from services that already reason over real recovery and training-load data, not new inference. No new UI: the question just works through the Coach screen's existing free-text Ask Siris box, and now appears in `EXAMPLE_QUESTIONS` as a clickable suggestion, matching how every other Ask Siris question type surfaces.

`coach.py` already held a module-level `TrainingConflictService` instance (`conflict_service`, used by the existing conflict-check endpoint); `AskSirisService` now accepts it via constructor injection rather than creating a second one.

## Consequences

- Zero Flutter changes — the existing `AskSirisAnswer` model already carries a generic `answer` string and `facts` map, and the Coach screen's Ask Siris card already renders whatever `EXAMPLE_QUESTIONS` contains.
- Found and fixed a real latent bug while wiring this up: `AskSirisService`'s new optional `training_conflict_service` parameter, when left to its own default, constructed a `TrainingConflictService` whose internal `HealthIngestService` was never `.initialise()`'d, which would have thrown "no such table: health_metric_samples" the first time this code path ran without an explicitly-injected conflict service (e.g. any test or caller not going through `coach.py`). Fixed by explicitly constructing and initialising a `HealthIngestService` in that default path. `coach.py`'s own pre-existing `conflict_service = TrainingConflictService()` has the same latent gap but currently avoids it only because `health.py`'s router import happens to run its own `HealthIngestService().initialise()` first at app startup — a pre-existing fragility, out of scope for this change, but worth knowing about.
- Verified live end-to-end via the actual Ask Siris UI on the Coach screen: asking "Can I train today?" returned the exact composed sentence from both real services, not a mock.
