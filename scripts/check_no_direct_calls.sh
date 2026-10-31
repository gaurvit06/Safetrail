#!/usr/bin/env bash
# SPEC rule 1: fails the build if any code calls an AI provider directly or a key is committed.
# The checks live in check_no_direct_calls.py (plain Python, so they also run on Windows without bash).
set -euo pipefail
cd "$(dirname "$0")/.."
for py in backend/.venv/bin/python backend/.venv/Scripts/python.exe; do
  if [ -x "$py" ]; then exec "$py" scripts/check_no_direct_calls.py "$@"; fi
done
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1; then exec "$py" scripts/check_no_direct_calls.py "$@"; fi
done
echo "Python not found: install Python 3 or create backend/.venv first." >&2
exit 2
