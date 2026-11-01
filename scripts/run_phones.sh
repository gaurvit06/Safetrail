#!/usr/bin/env bash
# Open SafeTrail to real phones with one command: starts a tunnel and the app together, with the QR codes pointing
# at the tunnel. Phones need https for GPS, which the tunnel gives them. Ctrl+C stops both.
#
#   bash scripts/run_phones.sh               # app on port 8000
#   bash scripts/run_phones.sh --port 8001   # another port
#
# Needs cloudflared (macOS: brew install cloudflared) and a set-up app (bash scripts/run_local.sh --no-run).
# Anyone with the link can reach the app while this runs, and the link changes every time.
# Windows: follow "Before judging" in docs/DEMO_SCRIPT.md.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=8000
[ "${1:-}" = "--port" ] && PORT="$2"

command -v cloudflared >/dev/null 2>&1 || { echo "cloudflared is needed. On macOS: brew install cloudflared" >&2; exit 1; }
[ -x backend/.venv/bin/python ] && [ -f frontend/dist/index.html ] || { echo "Run this first: bash scripts/run_local.sh --no-run" >&2; exit 1; }
# New code pulled from GitHub only shows up after a build.
if [ -n "$(find frontend/src frontend/index.html -newer frontend/dist/index.html -print -quit)" ]; then
  echo "Building the latest screens..."
  npm --prefix frontend run build >/dev/null
fi
URL_FILE="$HOME/.safetrail-url"
links() { printf '\n  Judges join:  %s/j\n  Projector:    %s/stage\n  Presenter:    %s/stage/control\n  Responder:    %s/r\n\n' "$1" "$1" "$1" "$1"; }
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  if [ -s "$URL_FILE" ] && curl -fsS -m 8 -o /dev/null "$(cat "$URL_FILE")/api/config"; then
    echo "SafeTrail is already running. Use these links:"
    links "$(cat "$URL_FILE")"
    exit 0
  fi
  echo "Port $PORT is already in use, probably by another copy of the app. Stop that first, or add --port 8001." >&2
  exit 1
fi

LOG="$(mktemp)"
cloudflared tunnel --url "http://localhost:$PORT" --no-autoupdate >"$LOG" 2>&1 &
TUNNEL=$!
trap 'kill "$TUNNEL" 2>/dev/null; rm -f "$LOG"' EXIT

URL=""
for _ in $(seq 1 40); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done
[ -n "$URL" ] || { echo "The tunnel didn't start:" >&2; tail -5 "$LOG" >&2; exit 1; }

links "$URL"
echo "$URL" > "$URL_FILE"
if command -v caffeinate >/dev/null 2>&1; then caffeinate -dims -w $$ & fi  # keep the Mac awake during the demo
if [ "${NO_OPEN:-}" != "1" ] && command -v open >/dev/null 2>&1; then
  (sleep 4; open "http://localhost:$PORT/r"; open "http://localhost:$PORT/stage") &
fi
PUBLIC_URL="$URL" backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port "$PORT"
