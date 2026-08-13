# ADR 073 — Training Conflict Detection v1

## Status

Accepted.

## Context

The Sprint 0.9 brainstorm names Training Conflict Detection the "signature feature" and the roadmap lists it right after weekly training load, gated on Apple Health recovery data as its stated hard dependency — which ADR 072's Health Summary API now provides. The brainstorm's own worked example, though, is about a *planned* schedule ("Tuesday: Heavy Squats, Wednesday: Running intervals" -> reschedule suggestion) — SirisOS has no concept of a planned/scheduled future session yet (that's the still-unbuilt Smart Weekly Planner), so that literal version isn't buildable today.

Two different readings of "conflict" were viable for a buildable v1, and this was confirmed with Brad before starting rather than assumed:

1. **Recovery-based** — flag when a recovery metric (HRV/resting HR) is notably worse than the athlete's own baseline on a day a session was also logged. Uses `HealthIngestService.summary()` (ADR 072) directly, with zero new inference.
2. **Sequencing-based** — flag the brainstorm's literal pattern (a leg-dominant gym day followed by a hard run within ~36 hours), inferred from workout names and run pace relative to the runner's own average.

Recovery-based was chosen: it's the dependency the roadmap itself names for this feature, it needed no new heuristics (workout-name guessing, run-intensity proxies), and it's the direct payoff of the Health Summary API just built.

## Decision

`TrainingConflictService.check(reference_date=today)` (new) reads the athlete's HRV and resting-heart-rate summaries from `HealthIngestService.summary()` and checks each against a fixed threshold — HRV below 85% of its trailing 14-day baseline, or resting heart rate above 110% of its baseline — then separately checks whether a gym workout or run was logged on `reference_date` (via `GymService`/`RunningService`, unchanged). A **critical correctness detail**: the health summary's "latest" reading is global, not scoped to any particular day, so the service explicitly checks that the reading's own date matches `reference_date` before using it — otherwise a stale sync (no data yet for today) would silently get treated as today's signal. Four possible outcomes:

- **`insufficient_data`** — no HRV/resting-HR reading synced *for this specific day* yet
- **`clear`** — recovery signals are within normal range
- **`reduced_recovery`** — recovery is down but nothing was trained that day (nothing to warn about — this is just a status, not a conflict)
- **`conflict`** — recovery is down *and* a session was logged that day, with the specific metric(s), their ratios, and a plain-English summary of what was logged

`GET /api/v1/coach/conflict-check` (new, under the existing `coach` router — this is a daily coaching signal, the same mental model as the weekly report and Ask Siris) exposes this. On the Flutter side, a "Today" card sits at the top of the existing `SirisCoachScreen`, above the weekly headline — matching the brainstorm's own Coach mockup ordering (today's status first, this week's report second).

No Ollama involvement in this slice: every output is a short, fully deterministic sentence built from the same facts already in the response, matching the "Siris doesn't manufacture advice" principle already established for Coach (ADR 070) — there's nothing here that benefits from paraphrasing that the fail-open pattern from ADR 057/071 would add value to.

## Consequences

- This is a real, load-bearing consumer of the Health Summary API — the reason that ADR (072) was built ahead of Gamification in the first place.
- Deliberately narrow: only two recovery metrics (HRV, resting heart rate) are checked, and only same-day session logging counts as "trained" — no lookback window for "trained recently" the way the brainstorm's sequencing example implies. A sequencing-based check (leg day -> hard run within 36h) remains explicit future work if the recovery-based signal proves insufficient on its own.
- The staleness check (reading must be dated `reference_date`, not just "the latest available") is the one subtle correctness issue this ADR had to get right — an earlier draft would have silently used however-old the last sync was and reported on "today" regardless. Caught during design, not left as a hidden gap.
- `reduced_recovery` (degraded signal, no training logged) is intentionally *not* the same status as `conflict` — nothing needs flagging if the athlete already isn't training that day. This distinction exists specifically so the guidance text never sounds alarmed about a day where nothing risky is actually happening.
- Test isolation needed a genuinely separate database per test (via `tmp_path`/`monkeypatch`, matching `test_health_ingest.py`'s existing pattern) rather than the random-year date-scoping used elsewhere in this sprint's tests — `HealthIngestService.summary()` has no per-test partition key at all (it's a real single-user datastore), so date-scoping alone can't isolate it.
