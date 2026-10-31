#!/usr/bin/env bash
# What CI checks, before you push (6.4). The pre-push hook runs it; turn the
# hook on once per clone with:  git config core.hooksPath .githooks
#   backend: pytest (bytecode caches cleared first)
#   web:     tsc and vitest
# Add VISUAL=1 to run the phone/desktop visual check too (needs a build and
# Playwright). SKIP_CHECKS=1 git push skips it all.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
find apps/backend -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
echo "Backend tests..."
(cd apps/backend && python -m pytest -q -x -p no:cacheprovider)
echo "Web: types and tests..."
(cd apps/web && npx tsc -b --noEmit && npx vitest run --reporter=dot)
if [ "${VISUAL:-}" = "1" ]; then
  (cd apps/web && npm run build && npm run visual)
fi
