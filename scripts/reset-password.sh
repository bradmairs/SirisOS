#!/usr/bin/env bash
# Set a new SirisOS sign-in password. Run on the server, from the repo folder:
#
#   make reset-password                       # change the password
#   make reset-password ARGS=--sign-out-all   # also end every signed-in session
#
# It asks for the new password twice (nothing is echoed or printed), writes it
# to .env (the old .env is kept as .env.bak.<timestamp>), and recreates the
# container so it takes effect. Nobody else ever sees the password: it goes
# from your keyboard to .env.
#
# The username stays as SIRISOS_ADMIN_USERNAME in .env. Sessions already
# signed in keep working until they expire (SIRISOS_JWT_EXPIRY_HOURS), unless
# you pass --sign-out-all, which also replaces SIRISOS_JWT_SECRET.
set -euo pipefail
cd "$(dirname "$0")/.."

sign_out_all=0
[ "${1:-}" = "--sign-out-all" ] && sign_out_all=1

[ -f .env ] || { echo "No .env here. Run this from the SirisOS folder on the server." >&2; exit 1; }

read -r -s -p "New password: " pw1; echo >&2
read -r -s -p "Again: " pw2; echo >&2

[ "$pw1" = "$pw2" ] || { echo "The two passwords don't match. Nothing was changed." >&2; exit 1; }
[ "${#pw1}" -ge 8 ] || { echo "Use at least 8 characters. Nothing was changed." >&2; exit 1; }
# These would be altered by Docker Compose when it reads .env, so you'd be locked out again.
case "$pw1" in
  *[\$\"\'\\\`\#\ ]*) echo "Avoid spaces and these characters: \$ \" ' \\ \` #  Nothing was changed." >&2; exit 1 ;;
esac

backup=".env.bak.$(date +%Y%m%d-%H%M%S)"
cp -p .env "$backup"
chmod 600 "$backup" .env

# Replace the line if it's there, add it if not. The value never appears on a command line.
set_env() {
  local key="$1" value="$2" tmp
  tmp="$(mktemp .env.XXXXXX)"
  chmod 600 "$tmp"
  KEY="$key" VALUE="$value" awk '
    BEGIN { k = ENVIRON["KEY"]; v = ENVIRON["VALUE"]; done = 0 }
    index($0, k "=") == 1 { if (!done) { print k "=" v; done = 1 } ; next }
    { print }
    END { if (!done) print k "=" v }
  ' .env > "$tmp"
  mv "$tmp" .env
}

set_env SIRISOS_ADMIN_PASSWORD "$pw1"
if [ "$sign_out_all" = 1 ]; then
  set_env SIRISOS_JWT_SECRET "$(head -c 48 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi

docker compose up -d sirisos >/dev/null
echo "Password changed. Sign in as $(grep -E '^SIRISOS_ADMIN_USERNAME=' .env | tail -1 | cut -d= -f2-)."
[ "$sign_out_all" = 1 ] && echo "Everyone signed in was signed out."
echo "The previous settings are kept in $backup; delete that file once you're happy."
