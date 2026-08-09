# ADR 056 — Cite an engineering standard on a saved calculation

## Status

Accepted.

## Context

ADR 055 gave calculations a persistent record and let a Project relate to both a calculation and an Engineering Standard independently. Neither relationship says a calculation was performed *against* a specific standard — the two facts sit side by side in the Project Context Graph with no link between them. Sprint 0.6's calculators already carry an assumptions disclaimer ("not a substitute for... governing standards"); letting a user attach the exact standard document/edition they designed to turns that disclaimer into a traceable record instead of a caveat.

## Decision

`CalculationRecord` gains an optional `cited_standard_id`. On save, the backend validates the ID against the Engineering Standards library (404 if missing) and resolves a human-readable `cited_standard_label` (reference/title, edition, library revision) fresh on every read — the same "resolve live, tolerate staleness" pattern ADR 053 established for standard relationships, so a calculation still shows its citation even if the cited standard is later archived or removed. This is a citation on the calculation record itself, not a third relationship type on the Project graph — it travels with the calculation wherever it's viewed, including the existing "Attach calculation" picker (ADR 055), which now surfaces the cited standard under each entry.

The "Save calculation" dialog reuses the same standards search/filter dialog already built for the Project Context Graph's "Attach Engineering standard" flow, extracted into a shared `standard_picker_dialog.dart` widget rather than duplicated.

## Consequences

- A saved calculation can now answer "which standard was this designed to?" without cross-referencing the Project graph.
- The citation is frozen to a specific standard document ID (an exact revision), not just a title, consistent with ADR 053's "exact document revision" identity model.
- No new relationship type or persistence boundary — this is a field on the existing calculation record, resolved the same way `_canonical_target` resolves Project relationship labels.
- The standard picker dialog is now shared UI, reducing the chance the two attach flows (standards, calculations) drift in behavior.
