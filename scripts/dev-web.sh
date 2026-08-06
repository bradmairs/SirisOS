#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="$ROOT_DIR/apps/mobile"

if ! command -v flutter >/dev/null 2>&1; then
  echo "Flutter is required but was not found in PATH." >&2
  echo "Install Flutter and run 'flutter doctor' before starting SirisOS." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but was not found in PATH." >&2
  exit 1
fi

bash "$ROOT_DIR/scripts/backend-up.sh"

cd "$MOBILE_DIR"

if [[ ! -d web ]]; then
  echo "Generating Flutter Web platform files..."
  flutter create --platforms=web .
fi

echo "Installing Flutter packages..."
flutter pub get

echo "Launching SirisOS Web..."
echo "Backend: http://localhost:8000"
echo "Press q in this terminal to stop Flutter Web."

flutter run \
  -d chrome \
  --dart-define=SIRISOS_API_URL=http://localhost:8000
