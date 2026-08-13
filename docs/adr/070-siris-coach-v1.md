# ADR 070 — Siris Coach v1

## Status

Accepted.

## Context

The Sprint 0.9 brainstorm names Siris Coach as its own explicit first-class section, and calls a deterministic weekly report "probably my #1 AI feature." The roadmap's stated sequencing puts it right after weekly training load (ADR 069). The brainstorm's own description bundles three things into "Coach": a "today" readiness/recommendation view, a "this week" deterministic delta report, and — following the same pattern already established for SirisHydro (ADR 057) — an optional Ollama narrative layer on top of the deterministic facts.

Two of those three aren't buildable yet without misrepresenting what SirisOS actually knows:

- **"Today"** (recovery %, gym/run recommendation, "watch" flags) needs recovery data (HRV, sleep) and a planned/scheduled workout to react to. Health Auto Export ingestion (merged just ahead of this slice) persists HRV/sleep samples now, but the roadmap's own "Event Bus refresh and Health summary API" item is still unchecked — there's no query surface yet to read those samples back out — and there's no concept of "today's planned session" until the Smart Weekly Planner exists. Building a "today" card now would mean inventing a readiness number from data the app can't actually read yet.
- **Ollama narrative synthesis** was deliberately deferred to a follow-up slice (confirmed with Brad before starting this one) — ship the deterministic core first, matching how Progressive Overload and Personal Records shipped, then layer narrative synthesis on top once the facts underneath are proven.

## Decision

`CoachService.weekly_report()` (new) computes a **deterministic weekly coach report** by composing the three existing training services — `RunningService`, `GymService`, `TrainingLoadService` (ADR 069) — with no new scoring logic of its own:

- **Week-over-week deltas**: running distance/run count and gym volume/session count for the current week vs. the immediately preceding week. If there's no data at all before the current week for that modality, the delta is `null` ("first week logged") rather than a delta against zero — comparing to a week before the athlete had any history would be misleading, the same reasoning ADR 069 applied to its baseline window.
- **Weekly training load**: reused as-is from `TrainingLoadService.weekly_load()` — no duplicated thresholds or scoring.
- **New bests this week**: a retroactive version of the exact independent-per-record-type check `GymService.create_workout()` already does at save time (ADR 067) — each exercise trained this week compared against every set logged strictly before this week, weight/estimated-1RM/set-volume checked independently. An exercise logged for the first time this week has nothing prior to beat, so (matching ADR 067) it isn't counted as an improvement.
- **Headline**: a single rule-based sentence — `"New best on {exercises}. {training_load.assessment}"` when there were improvements, otherwise just the training-load assessment verbatim. No new "is this week good or bad" judgement is invented; it reuses the one `TrainingLoadService` already computed. When nothing notable happened, the headline just says so — matching the brainstorm's explicit design principle that Coach "doesn't constantly manufacture advice."

`GET /api/v1/coach/weekly-report` exposes this, wired into the existing `/api/v1` aggregator alongside `training`. On the Flutter side, **Coach is a genuinely new first-class navigation destination** (not a card bolted onto Gym/Running) — a `SirisCoachScreen` registered in `SirisModuleRegistry`/`AppModuleRegistry`, reachable from the desktop sidebar and the mobile "More" menu. It was deliberately left out of the mobile bottom nav's fixed 6-icon primary row (`_mobilePrimaryModuleIds` in `app_shell.dart`) rather than added as a 7th icon, to avoid a layout decision the brainstorm never asked for.

## Consequences

- Every number in the weekly report traces to a service that already existed before this slice (`RunningService`, `GymService`, `TrainingLoadService`) — Coach v1 adds a composition layer and a screen, not a new source of truth.
- "Today" (readiness, gym/run go/no-go recommendation, "watch" flags) and Ollama narrative synthesis are both explicitly deferred, not built partially. Building "today" now would need to either fabricate a readiness signal SirisOS can't actually compute yet, or silently omit it in a way that looks like a bug rather than a scoping decision — this ADR records it as the latter.
- `_weekly_improvements()` duplicates ADR 067's per-record-type comparison logic in a retroactive (whole-week) form rather than reusing `create_workout()`'s event-time version, since there's no persisted, queryable record of "which PRs happened in week X" — `PersonalRecord` events are transient, returned once at save time and only durably visible via the (unfilterable-by-date) `ActivityService` feed. If a future slice needs the same week-scoped PR query elsewhere, this logic is a candidate to extract rather than re-duplicate a third time.
- A real bug was caught during live verification, not by `flutter analyze` or tests: `_MetricTile`'s `Column` used a `Spacer()` inside a `Wrap`-laid-out tile. `Wrap` gives its children unbounded height by design, and a flex child (`Spacer`) inside unbounded height constraints is an assertion failure in debug builds — invisible to `flutter analyze`/`flutter test`, and silently different in release builds (since Dart `assert()`s compile out), which is exactly the kind of bug this project's "run the real app" rule exists to catch. Fixed by replacing `Spacer()` with a fixed `SizedBox` gap; worth checking whether `health_screen.dart`'s `_MetricTile`, which uses the identical `Container(minHeight) + Column + Spacer()` pattern inside its own `Wrap`, has the same latent issue.
