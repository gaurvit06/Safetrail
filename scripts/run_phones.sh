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
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
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

printf '\n  Judges join:  %s/j\n  Projector:    %s/stage\n  Presenter:    %s/stage/control\n  Responder:    %s/r\n\n' "$URL" "$URL" "$URL" "$URL"
PUBLIC_URL="$URL" backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port "$PORT"
