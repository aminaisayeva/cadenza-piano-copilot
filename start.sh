#!/usr/bin/env bash
#
# Cadenza one-shot launcher.
#   ./start.sh
# Sets up anything missing (venv, deps, node_modules), starts the backend on
# :8200 and the Vite frontend, opens your browser, and shuts both down on Ctrl+C.

set -euo pipefail
cd "$(dirname "$0")"

BACKEND_PORT=8200
PY=python3.10

say() { printf "\n\033[1;35m▶ %s\033[0m\n" "$1"; }

# ---------------------------------------------------------------- backend setup
say "Backend setup"
cd backend
if [ ! -d .venv ]; then
  say "Creating Python venv + installing deps (first run, ~a few minutes)…"
  $PY -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip >/dev/null
  ./.venv/bin/python -m pip install -r requirements.txt
  # neural model package (no PyPI release; --no-deps protects modern transformers)
  ./.venv/bin/python -m pip install --no-deps git+https://github.com/jthickstun/anticipation.git
fi
cd ..

# --------------------------------------------------------------- frontend setup
say "Frontend setup"
cd frontend
if [ ! -d node_modules ]; then
  say "Installing frontend deps (first run)…"
  npm install
fi
cd ..

# ------------------------------------------------------------------------- ports
# Free the backend port if a previous run left it occupied.
if lsof -nP -iTCP:$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  say "Port $BACKEND_PORT busy — stopping the old process"
  lsof -nP -iTCP:$BACKEND_PORT -sTCP:LISTEN -t | xargs kill 2>/dev/null || true
  sleep 1
fi

# ------------------------------------------------------------------------ launch
PIDS=()
cleanup() {
  say "Shutting down…"
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  exit 0
}
trap cleanup INT TERM

say "Starting backend on http://localhost:$BACKEND_PORT"
( cd backend && ./.venv/bin/python -m uvicorn app.main:app --port $BACKEND_PORT ) &
PIDS+=($!)

# wait for backend health
for _ in $(seq 1 30); do
  if curl -sf http://localhost:$BACKEND_PORT/health >/dev/null 2>&1; then break; fi
  sleep 0.5
done

say "Starting frontend"
FE_LOG="$(mktemp)"
( cd frontend && npm run dev ) >"$FE_LOG" 2>&1 &
PIDS+=($!)

# grab the URL Vite prints (port may vary if 5173 is taken)
URL=""
for _ in $(seq 1 30); do
  URL="$(grep -Eo 'http://localhost:[0-9]+/?' "$FE_LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 0.5
done
URL="${URL:-http://localhost:5173/}"

say "Cadenza is up → $URL"
echo "   Open it in Chrome or Edge, then click '▶ Demo melody' (no keyboard needed)."
echo "   Press Ctrl+C here to stop both servers."
# Prefer Chrome (Safari lacks Web MIDI); fall back to the default browser.
if open -a "Google Chrome" "$URL" 2>/dev/null; then :; else open "$URL" 2>/dev/null || true; fi

# keep running until Ctrl+C
wait
