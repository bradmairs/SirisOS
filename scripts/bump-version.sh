#!/usr/bin/env bash
# Bump the SirisOS version (docs/releases.md). Versions are Section.Feature.Fix, e.g. 11.2.1:
#   scripts/bump-version.sh fix       # a fix or minor change          11.2.1 -> 11.2.2
#   scripts/bump-version.sh feature   # a new feature or bigger upgrade  11.2.1 -> 11.3.0
#   scripts/bump-version.sh section   # a significant new section (like Health or SirisGym)  11.2.1 -> 12.0.0
# (patch, minor and major still work, as fix, feature and section.) Each part counts on its own and never rolls over
# into the next, so a whole-number change always means a new section.
# Writes VERSION, the API's and the web app's version, the README's version line, and starts
# docs/releases/<version>.md. Merging the bump to main tags and releases it.
set -euo pipefail
cd "$(dirname "$0")/.."

kind="${1:-}"
current="$(tr -d '[:space:]' < VERSION)"
next="$(python3 - "$current" "$kind" <<'PY'
import sys
current, kind = sys.argv[1], {"patch": "fix", "minor": "feature", "major": "section"}.get(sys.argv[2], sys.argv[2])
parts = current.split(".")
if len(parts) != 3 or not all(p.isdigit() for p in parts):
    sys.exit(f"VERSION should be Section.Feature.Fix, like 11.2.1, not {current}")
s, f, x = (int(p) for p in parts)
if kind == "fix":
    x += 1
elif kind == "feature":
    f, x = f + 1, 0
elif kind == "section":
    s, f, x = s + 1, 0, 0
else:
    sys.exit("usage: scripts/bump-version.sh fix|feature|section")
print(f"{s}.{f}.{x}")
PY
)"

echo "$next" > VERSION
sed -i -E "s/^API_VERSION = \".*\"/API_VERSION = \"$next\"/" apps/backend/app/main.py
sed -i -E "s/^export const APP_VERSION = \".*\";/export const APP_VERSION = \"$next\";/" apps/web/src/version.ts
# The README's version line (8.9: it said 1.0 for seven major versions).
sed -i -E "s#^\*\*Version [0-9.]+\*\* \(\[release notes\]\(docs/releases/[0-9.]+\.md\)#**Version $next** ([release notes](docs/releases/$next.md)#" README.md
notes="docs/releases/$next.md"
[ -f "$notes" ] || printf '# SirisOS %s\n\n- \n' "$next" > "$notes"
echo "SirisOS $current -> $next (fill in $notes)"
