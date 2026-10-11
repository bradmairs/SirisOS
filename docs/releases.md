# Releases and versions

SirisOS has one version, in [`/VERSION`](../VERSION) (e.g. `1.0`, `1.01`, `1.1`).
The API (`app/main.py`), the web app (`apps/web/src/version.ts`, shown in the
side menu) and a test (`tests/test_version.py`) all follow it.

## Every change bumps it

Each change merged to main moves the version up by:

- **+0.01** (`scripts/bump-version.sh patch`): fixes, tweaks and small changes, e.g. 1.0 → 1.01.
- **+0.1** (`scripts/bump-version.sh minor`): a new feature, screen, integration or other notable change, e.g. 1.07 → 1.1.

The script writes all three version spots and starts `docs/releases/<version>.md`;
fill in what changed. Bump in the same pull request as the change.

## Shipping

Changes go to main by pull request and are merged as soon as CI is green, with
no separate sign-off. When a merge changes `VERSION`, the
[Release workflow](../.github/workflows/release.yml) tags it `v<version>` and
publishes a GitHub release from its notes.

Older notes from before the hub (0.4.x) are kept in `docs/releases/`.
