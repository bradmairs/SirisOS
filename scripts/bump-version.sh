#!/usr/bin/env bash
# Bump the SirisOS version (docs/releases.md):
#   scripts/bump-version.sh patch   # +0.01: fixes and small changes (1.0 -> 1.01)
#   scripts/bump-version.sh minor   # +0.1: a new feature or a notable change (1.07 -> 1.1)
# Writes VERSION, the API's and the web app's version, and starts
# docs/releases/<version>.md. Merging the bump to main tags and releases it.
set -euo pipefail
cd "$(dirname "$0")/.."

kind="${1:-}"
current="$(tr -d '[:space:]' < VERSION)"
next="$(python3 - "$current" "$kind" <<'PY'
import sys
from decimal import Decimal
current, kind = Decimal(sys.argv[1]), sys.argv[2]
step = {"patch": Decimal("0.01"), "minor": Decimal("0.1")}.get(kind)
if step is None:
    sys.exit("usage: scripts/bump-version.sh patch|minor")
# A minor bump lands on the next tenth: 1.07 -> 1.1, not 1.17.
nxt = (current + step).quantize(Decimal("0.01")) if kind == "patch" else ((current * 10).to_integral_value(rounding="ROUND_FLOOR") + 1) / 10
s = format(nxt.normalize(), "f")
print(s if "." in s else s + ".0")
PY
)"

echo "$next" > VERSION
sed -i -E "s/^API_VERSION = \".*\"/API_VERSION = \"$next\"/" apps/backend/app/main.py
sed -i -E "s/^export const APP_VERSION = \".*\";/export const APP_VERSION = \"$next\";/" apps/web/src/version.ts
notes="docs/releases/$next.md"
[ -f "$notes" ] || printf '# SirisOS %s\n\n- \n' "$next" > "$notes"
echo "SirisOS $current -> $next (fill in $notes)"
