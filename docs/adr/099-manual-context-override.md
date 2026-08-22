# ADR 099 — Manual Context Override

## Status

Accepted.

## Context

ADR 031's SirisCore Context Service has been entirely provider-derived since it shipped: `_OperationalContextProvider` reasons from integration health/notification policy state, and `ProjectContextProvider` (ADR 051) reflects the manually-selected current project. Nothing lets the user directly assert a context fact of their own -- "I'm focused, don't surface non-urgent items" or "away from home this weekend" has no way into the snapshot. The roadmap named this gap directly: "Manual context override with expiry/provenance."

This is distinct from Mission Control's existing `MissionControlFocus` (work/home/fitness/travel, ADR from Sprint 0.4.2) -- that's a display-layer widget filter with no expiry and no representation in `SirisContextSnapshot` at all. The two remain separate; unifying them wasn't asked for and would mean redesigning a shipped, working feature to solve a problem it doesn't have.

## Decision

`ManualContextOverrideService` (`apps/mobile/lib/src/core/manual_context_override.dart`) persists a single active override client-side via `SharedPreferences` -- the same storage boundary every other Context Service provider already lives behind; there is no server-side context store to persist through. `set()` takes a label, `SirisContextDomain`, optional detail and optional `Duration` expiry; `current()` returns the active override or `null`, lazily deleting it from storage the moment it's read past its expiry rather than leaving it to linger until something else happens to overwrite it.

`ManualContextOverrideProvider implements SirisContextProvider` wraps the service and emits a single fact at priority 200 when an override is active -- above every existing provider-derived priority (the highest, UPS power events, is 100), so a manual assertion always wins as `snapshot.primary`. Registered in `app.dart` alongside `ProjectContextProvider`.

`ContextPanel` (Operations Center / Mission Control's `siris.context` widget) gained a header action: an edit icon opens a dialog to set label/detail/domain/expiry (1h / 4h / 8h / no expiry); once an override is active the icon becomes a clear button, and a line beneath the fact chips states either "clears automatically at HH:MM" or "no expiry, tap the icon above to clear it" -- provenance the user can actually see, not just a `source: 'manual'` string in the model.

## Consequences

- Setting or clearing an override calls `SirisCoreContextService.refresh()` immediately, so the panel reflects the change without waiting for the next `IntegrationHealthChanged`/`NotificationPolicyStateChanged` event.
- Expiry itself is enforced lazily on read, matching every other Context Service provider's freshness model -- nothing in this service polls on a timer. A stored override past its expiry is silently excluded from `collect()` the next time anything triggers a refresh, but if the panel is left open with no other event firing, the displayed chip could in principle linger past the stated expiry time until the next refresh. Adding a dedicated polling job to guarantee sub-minute expiry accuracy was considered and deliberately deferred -- no other Context Service provider has this property either, and inventing one only for this feature would be solving a problem nothing has actually reported.
- v1 holds exactly one active override, matching the roadmap's own singular framing. Setting a new one silently replaces the old, rather than the two composing or queuing.
- Flutter: 6 new tests (`manual_context_override_test.dart`) covering set/current round-trip, expiry (including that an expired read actually deletes the stored value, not just filters it), clear, the never-set case, and the provider's empty/active-fact shapes. `flutter analyze` clean, full suite (64 tests) passes.
