#!/usr/bin/env bash
# Copy SirisAI's hub contract (schema + example payloads) into the backend
# tests (ADR 110). Run after SirisAI changes contracts/hub-v1, then run the
# backend tests: they parse every example the way SirisOS uses it.
#
#   scripts/sync-sirisai-contract.sh ../SirisAI
set -euo pipefail
src="${1:?usage: $0 <path to a SirisAI checkout>}/contracts/hub-v1"
dest="$(cd "$(dirname "$0")/.." && pwd)/apps/backend/tests/contracts/sirisai-hub-v1"
[ -f "$src/schema.json" ] || { echo "no $src/schema.json" >&2; exit 1; }
mkdir -p "$dest"
cp "$src/schema.json" "$src"/examples/*.json "$dest/"
echo "Copied $(ls "$src"/examples/*.json | wc -l) examples and the schema to $dest"
