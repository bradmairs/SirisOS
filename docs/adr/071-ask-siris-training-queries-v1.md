# ADR 071 — Ask Siris Training Queries v1

## Status

Accepted.

## Context

The Sprint 0.9 roadmap's "Siris Coach and Ask Siris" section calls for natural-language training queries ("What's my best 5K this year?", "Does poor sleep affect my bench?") as "a third instance of the grounded-evidence-plus-synthesis pattern" following ADR 057 (SirisHydro). That pattern's retrieval half — lexical scoring over pre-chunked standards-PDF text (`engineering_standards_search.py`) — is document-search-specific and doesn't generalize: training data (runs, workouts, weekly reports) is structured and directly queryable through `RunningService`/`GymService`/`TrainingLoadService`/`CoachService`, not free text to rank.

That leaves an open design question this pattern doesn't answer on its own: how does the system decide what a free-text training question is actually asking for? Two approaches were considered and discussed with Brad before starting:

1. **Deterministic pattern matching** — a small, fixed set of recognized question shapes routed by keyword/regex to the exact service call that answers it. Ollama, if used at all, only rephrases an already-computed answer.
2. **Ollama-assisted intent classification** — ask Ollama to map the question to a structured intent + parameters, then run the deterministic lookup against that.

Option 1 was chosen. It keeps Ollama out of the fact-finding path entirely — consistent with every other deterministic-first slice this sprint (Progressive Overload, Personal Records, Weekly Training Load, Siris Coach) — at the cost of narrower question coverage than the brainstorm's full example list.

## Decision

`AskSirisService.answer()` (new) tries a fixed, ordered list of question-pattern handlers against the lowercased question text; the first one that both matches the question's shape *and* can extract what it needs (an exercise name that's actually been logged, a weight, a distance, a period) wins. Handlers, in match order:

1. **Last time at weight** — "When did I last deadlift 140 kg?"
2. **Exercise progress / max** — "What's my bench press max?", "How much has my bench press improved since 2026-01-01?"
3. **Most improved exercise** — compares each exercise's estimated 1RM now vs. 90 days ago
4. **Best/fastest distance** — "What's my best 5K this year?" — filters `RunningService` runs within a tolerance band of the requested distance
5. **Training counts** — "How many leg workouts have I done this month?" — optionally filtered by a workout-name keyword (leg/push/pull/upper/lower/full body), since there's no exercise-to-muscle-group taxonomy to query against (same gap noted in the roadmap's Muscle Map item)
6. **Weekly summary** — reuses `CoachService.weekly_report().headline` verbatim, no new logic

If nothing matches, the response says so plainly and returns `EXAMPLE_QUESTIONS` as clickable suggestions, rather than guessing. Exercise names are matched by substring against exercises the athlete has *actually logged* (`GymService.list_exercises()`), not a hardcoded exercise vocabulary — asking about an exercise that's never been logged correctly falls through to "not understood" rather than fabricating an answer for it.

`GET /api/v1/coach/ask?question=` (new, under the existing `coach` router) calls `AskSirisService.answer()` for the deterministic result, then — only when `understood` is true, mirroring ADR 057's "sufficient evidence" gate — passes the question and the deterministic answer to the existing `chat_client.complete()` (ADR 057's `OllamaChatClient`, unmodified) with a system prompt instructing it to rephrase using only the facts already given, nothing new. `synthesized_answer` stays `null` and the deterministic `answer` is shown as-is whenever Ollama is unconfigured, unreachable, or fails — the same fail-open contract every other `chat_client` caller already relies on.

The Flutter side adds an "Ask Siris" card directly on the existing `SirisCoachScreen` (not a new screen) — a text field, a deterministic-answer display, a distinctly-styled card for the synthesized answer when present, and tappable suggestion chips when the question wasn't understood.

## Consequences

- Every answer traces to a real service call an athlete could make themselves — there's no path where Ollama invents a number, date, or exercise name. The only thing Ollama can do is make an already-correct answer read more naturally.
- Coverage is intentionally narrower than the brainstorm's full example list. Two categories are structurally impossible today and were left out rather than half-built: "what's my strongest muscle group" (needs an exercise-to-muscle-group taxonomy that doesn't exist, same gap as the roadmap's Muscle Map item) and "does poor sleep affect my bench" (needs the still-unbuilt Health summary API to read HRV/sleep back out). Anything else outside the six recognized patterns also declines rather than guessing.
- A genuine bug was caught by tests, not just live-verification this time: `_best_distance` and `_training_counts`'s period filters only checked a *lower* date bound (`>= since`) with no upper bound, so "this week" actually meant "since Monday, unboundedly into the future" — invisible in isolated single-scenario testing, but surfaced immediately once tests ran against the same shared dev database other tests populate (a workout dated in a *later* test's random year satisfied `>= since` for an *earlier* test's `today`). Fixed by bounding both filters with `<= today`, which is also the more correct production behavior.
- Test isolation for this suite needed disjoint random-year ranges across `test_training_load.py`, `test_coach.py`, and `test_ask_siris.py` (each narrowed to ~2000-value ranges), tightening the pattern ADR 069/070 already established — a shared, unbounded date range across files is exactly what let the bug above go undetected on a single test run in isolation.
