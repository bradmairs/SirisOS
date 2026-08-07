# ADR 011 — Shared SirisOS design system

## Status

Accepted.

## Context

Mission Control has established the interaction model for SirisOS, but visual primitives were still being implemented independently inside individual widgets. That creates inconsistent spacing, status treatment and visual hierarchy as more modules are added.

## Decision

SirisOS will use a shared Flutter design-system layer under `widgets/siris_design_system.dart`.

The initial primitives are:

- `SirisCard` — shared glass/dark surface, border, accent and emphasis treatment.
- `SirisPanel` — titled content container built on `SirisCard`.
- `SirisMetric` — consistent label/value/detail hierarchy.
- `SirisStatusChip` — deterministic neutral/info/success/warning/critical status treatment.
- `SirisGauge` — consistent compact progress/score presentation.
- `SirisTimeline` — reusable event/activity presentation.

The global theme owns the premium black/red visual language, typography, navigation, form and action styling. Individual modules may use semantic accent colours for domain recognition, but warning and critical states must use shared semantic tokens rather than inventing local colours.

Mission Control summary cards are the first existing components migrated to these primitives. Future modules and refactors should prefer the shared components rather than creating new card/status/metric treatments.

## Consequences

- The visual language can evolve centrally without rewriting every module.
- Warning and critical states remain consistent across Personal, Infrastructure, Engineering and Knowledge domains.
- New modules have a smaller UI implementation surface.
- Existing specialised widgets can migrate incrementally; they do not need to be rewritten in one release.
- The design system remains presentation-only and must not contain module business logic.
