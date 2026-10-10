#!/usr/bin/env bash
# Switch the SirisOS logo between the lightning-bolt S and the original curved S
# (docs/brand.md). Updates the in-app mark (apps/web/src/components/Logo.tsx)
# and the favicon / home-screen icon (apps/web/public/siris-mark.svg,
# siris-icon.png). Rebuild afterwards: make up.
#
#   scripts/use-logo.sh bolt      # the faceted lightning S (default)
#   scripts/use-logo.sh classic   # the original curved S
set -euo pipefail
style="${1:-}"
case "$style" in bolt|classic) ;; *) echo "usage: $0 bolt|classic" >&2; exit 2 ;; esac
root="$(cd "$(dirname "$0")/.." && pwd)"
pub="$root/apps/web/public"
cp "$pub/siris-mark-$style.svg" "$pub/siris-mark.svg"
cp "$pub/siris-icon-$style.png" "$pub/siris-icon.png"
sed -i.bak -E "s/^export const LOGO_STYLE: LogoStyle = \"(bolt|classic)\";/export const LOGO_STYLE: LogoStyle = \"$style\";/" \
  "$root/apps/web/src/components/Logo.tsx" && rm -f "$root/apps/web/src/components/Logo.tsx.bak"
echo "Logo set to '$style'. Rebuild (make up); phones may keep the old home-screen icon until you re-add it."
