# Working on SirisOS

Read [README.md](README.md) (the handover) and [docs/roadmap.md](docs/roadmap.md) first.

## Versions and shipping (Brad's standing instructions)

- **Bump the version in every pull request**: `scripts/bump-version.sh patch` (+0.01) for fixes, tweaks and small changes; `scripts/bump-version.sh minor` (+0.1) for a new feature, screen, integration or other notable change. Fill in the `docs/releases/<version>.md` it starts. See [docs/releases.md](docs/releases.md).
- **Merge to main automatically**: open the pull request, wait for CI to go green, then mark it ready and merge it (squash) without asking. Fix red CI first; never merge red.
- Merging a `VERSION` change tags `v<version>` and publishes the GitHub release by itself (`.github/workflows/release.yml`).

## Checks before pushing

- Backend: `cd apps/backend && pytest -q`
- Web: `cd apps/web && npx tsc -b --noEmit && npm test`
