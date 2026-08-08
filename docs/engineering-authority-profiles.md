# Engineering Authority Profiles

Authority profiles will connect deterministic Engineering calculators to traceable project assumptions without hard-coding unsupported requirements into calculator logic.

## Proposed profile fields
- Stable profile ID and display name.
- Jurisdiction / asset owner.
- Applicable project or design context.
- Assumption name and value with explicit SI units where applicable.
- Source document ID, reference, edition and page.
- Optional user-entered project override with reason and timestamp.
- Provenance state: `source-backed`, `project-override`, or `unverified`.

## Rules
- Calculator mathematics remain deterministic and standards-neutral by default.
- A profile may prefill an input only when the source and provenance are visible to the user.
- SirisOS must not label a value as an authority requirement unless a local or authoritative source establishes it.
- Project overrides must remain distinguishable from authority defaults.
- Superseded editions should not silently replace values used by an existing project calculation.

## Initial target authorities
WSAA, Sydney Water, Austroads, Australian Standards and project/council specifications. Profiles should be created from documents actually available to the user rather than from model memory.
