#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="$ROOT_DIR/apps/mobile"
SERVER_IP="${SIRISOS_SERVER_IP:-192.168.0.100}"
WEB_PORT="${SIRISOS_WEB_PORT:-6465}"
API_PORT="${SIRISOS_API_PORT:-6464}"
API_URL="http://${SERVER_IP}:${API_PORT}"

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

echo "Launching SirisOS Web development server..."
echo "Development UI: http://${SERVER_IP}:${WEB_PORT}"
echo "Unified SirisOS backend: ${API_URL}"
echo "Press q in this terminal to stop Flutter Web."

flutter run \
  -d web-server \
  --web-hostname=0.0.0.0 \
  --web-port="${WEB_PORT}" \
  --dart-define="SIRISOS_API_URL=${API_URL}"
