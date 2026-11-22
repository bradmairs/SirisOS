# Releases and versions

SirisOS has one version, in [`/VERSION`](../VERSION): **Section.Feature.Fix**, e.g. `11.2.1`.
The API (`app/main.py`), the web app (`apps/web/src/version.ts`, shown in the
side menu) and a test (`tests/test_version.py`) all follow it.

## Every change bumps it

Each change merged to main moves the version up by one of:

- **Fix** (`scripts/bump-version.sh fix`): a fix or a minor change, e.g. 11.2.1 → 11.2.2.
- **Feature** (`scripts/bump-version.sh feature`): a new feature or a bigger upgrade, e.g. 11.2.1 → 11.3.0.
- **Section** (`scripts/bump-version.sh section`): a significant new section, like Health or SirisGym, e.g. 11.2.1 → 12.0.0.

Each part counts on its own and never rolls over into the next (11.9.0 plus a feature is 11.10.0), so a change in
the whole number always means a new section. The script writes all three version spots and starts
`docs/releases/<version>.md`; fill in what changed. Bump in the same pull request as the change.

### The renumbering (2026-11-22)

Until 2026-11-22 versions were decimals (+0.01 and +0.1, which rolled over: 1.9 + 0.1 became 2.0). Brad asked for
whole numbers to mean a new section only, so the whole history was renumbered: each release was judged a section,
a feature or a fix, and counted again from 1.0.0. 10.61 became 11.2.1. Each release's notes say its old number, the
GitHub releases and tags were recreated under the new numbers on the same commits, and
[`renumbering.md`](renumbering.md) lists every old number against its new one.

## Shipping

Changes go to main by pull request and are merged as soon as CI is green, with
no separate sign-off. When a merge changes `VERSION`, the
[Release workflow](../.github/workflows/release.yml) tags it `v<version>` and
publishes a GitHub release from its notes.

Older notes from before the hub (0.4.x) are kept in `docs/releases/`.
