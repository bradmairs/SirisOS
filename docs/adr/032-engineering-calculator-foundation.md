# ADR 032 — Engineering calculator foundation

## Status

Accepted.

## Context

Sprint 0.4.5 introduces first-class civil engineering tools into SirisOS. These calculations must remain deterministic, testable and explainable, and must not silently imply compliance with a particular authority or standard when project-specific assumptions have not been supplied.

## Decision

1. Pure engineering equations live in `engineering_calculators.dart`, independent from Flutter UI state.
2. The Engineering module is registered through the existing Module Registry and App Module Registry.
3. Initial tools are full circular pipe Manning capacity, Rational Method peak flow, buried-pipe buoyancy screening and constant-flow detention screening.
4. Every calculator uses explicit SI/Australian civil input units and validates invalid geometry/input ranges.
5. Screening tools clearly disclose simplified assumptions. In particular, the buoyancy helper does not claim side shear, anchors, slabs or project-specific load factors, and detention sizing does not replace hydrograph routing.
6. Numerical regression tests protect the calculation core from future UI, AI or refactoring changes.
7. Standards search and SirisHydro/SirisPM integration remain separate follow-on work; standards-specific defaults must be traceable to authoritative sources when introduced.

## Consequences

The Engineering module is useful immediately without coupling basic maths to external APIs or AI. Future standards-aware tools can build on the deterministic calculator core while preserving an auditable distinction between equations, assumptions and authority-specific requirements.
