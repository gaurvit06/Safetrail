#!/usr/bin/env bash
# Run SafeTrail on this computer (macOS or Linux) with one command: checks what's needed, builds the app,
# installs the server, starts it on http://localhost:8000 and opens the browser. Ctrl+C stops it.
#
#   bash scripts/run_local.sh              # set up (first time) and run
#   bash scripts/run_local.sh --no-run     # set up only
#   bash scripts/run_local.sh --port 8001  # another port
#
# Windows: follow "Run it" in README.md.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=8000
RUN=1
while [ $# -gt 0 ]; do
  case "$1" in
    --no-run) RUN=0 ;;
    --port) PORT="$2"; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

# Python 3.10 or newer (the python3 that comes with macOS is often 3.9, which is too old for this code)
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    PY="$(command -v "$c")"
    break
  fi
done
[ -n "$PY" ] || fail "Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/ (or: brew install python@3.12), then run this again."
command -v node >/dev/null 2>&1 || fail "Node.js is needed. Install the LTS version from https://nodejs.org (or: brew install node), then run this again."
[ "$(node -p 'process.versions.node.split(".")[0]')" -ge 18 ] || fail "Node.js 18 or newer is needed (you have $(node -v)). Install the LTS version from https://nodejs.org."

say "Building the app (frontend)"
(cd frontend && npm install --no-audit --no-fund --loglevel=error && npm run build --silent)

say "Installing the server (backend) with $("$PY" --version)"
(cd backend && { [ -x .venv/bin/python ] || "$PY" -m venv .venv; } \
  && .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt)

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add the Prune keys there later; everything works without them."
fi

if [ "$RUN" = 0 ]; then
  say "Ready. Start it with: bash scripts/run_local.sh"
  exit 0
fi
if command -v lsof >/dev/null 2>&1 && lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  fail "Port $PORT is already in use (is SafeTrail already running in another window?). Stop it, or run: bash scripts/run_local.sh --port 8001"
fi

URL="http://localhost:$PORT"
say "SafeTrail is starting on $URL"
cat <<EOF
  Phone view (Chrome): open $URL, press Option+Cmd+I, then Shift+Cmd+M, pick an iPhone at the top, reload.
  Tourist ..... $URL           (Start a trip; set your location with "Demo: tap the map")
  Responder ... $URL/r         (PIN 2468)
  Projector ... $URL/stage     (Presenter, PIN 1357)
  Presenter ... $URL/stage/control
  Stop with Ctrl+C. Next time just run: bash scripts/run_local.sh
EOF
(sleep 4
 if command -v open >/dev/null 2>&1; then open "$URL"
 elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL" >/dev/null 2>&1 || true
 fi) &
cd backend
exec .venv/bin/python -m uvicorn app.main:app --port "$PORT"
