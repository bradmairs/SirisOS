# Working on SirisOS

Read [README.md](README.md) (the handover) and [docs/roadmap.md](docs/roadmap.md) first.

## Versions and shipping (Brad's standing instructions)

- **Bump the version in every pull request**: `scripts/bump-version.sh patch` (+0.01) for fixes, tweaks and small changes; `scripts/bump-version.sh minor` (+0.1) for a new feature, screen, integration or other notable change. Fill in the `docs/releases/<version>.md` it starts. See [docs/releases.md](docs/releases.md).
- **Merge to main automatically**: open the pull request, wait for CI to go green, then mark it ready and merge it (squash) without asking. Fix red CI first; never merge red.
- Merging a `VERSION` change tags `v<version>` and publishes the GitHub release by itself (`.github/workflows/release.yml`).

## Checks before pushing

- Backend: `cd apps/backend && pytest -q`
- Web: `cd apps/web && npx tsc -b --noEmit && npm test`

## Siris: record what you build (Brad's standing instruction)

Siris is Brad's second brain, the private repo `bradmairs/Siris-Second-Brain`, and his manual for rebuilding everything. When a session in this repo builds, changes, deploys or retires a feature, record it in Siris before finishing, without being asked:

- Follow `plugins/siris-brain/skills/learn/SKILL.md` in that repo. In a cloud session, attach it first (owner `bradmairs`, repo `Siris-Second-Brain`, push access). Always write through its engine (`tools/brain.py learn`), never by editing notes directly, then commit and push.
- Add to this app's note, **"SirisOS"**, so it gets a dated update instead of a duplicate.
- Capture what changed and why, the version, how to deploy or update it, the settings that matter (names only), and lessons learned. Never write secrets.
- End your reply with one line, e.g. `🧠 Siris learned: [[SirisOS]] (updated)`.
