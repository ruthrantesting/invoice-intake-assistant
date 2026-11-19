#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:5173}"
STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-60}"
CHROME_BIN="${CHROME_BIN:-google-chrome}"
BACKEND_LOG="${BACKEND_LOG:-/tmp/invoice-agent-backend.log}"
WORKER_LOG="${WORKER_LOG:-/tmp/invoice-agent-worker.log}"
FRONTEND_LOG="${FRONTEND_LOG:-/tmp/invoice-agent-frontend.log}"
PROTOTYPE_MODE="${PROTOTYPE_MODE:-true}"

backend_pid=""
worker_pid=""
frontend_pid=""

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  for pid in "$frontend_pid" "$worker_pid" "$backend_pid"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  for pid in "$frontend_pid" "$worker_pid" "$backend_pid"; do
    if [[ -n "$pid" ]]; then
      wait "$pid" 2>/dev/null || true
    fi
  done
  exit "$exit_code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for path in "$BACKEND_DIR/pyproject.toml" "$FRONTEND_DIR/package.json"; do
  if [[ ! -f "$path" ]]; then
    printf 'Required project file not found: %s\n' "$path" >&2
    exit 1
  fi
done

if ! command -v uv >/dev/null 2>&1; then
  printf 'uv is required to start the backend. Install uv and try again.\n' >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  printf 'npm is required to start the frontend. Install Node.js/npm and try again.\n' >&2
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  printf 'curl is required to wait for the frontend server.\n' >&2
  exit 1
fi

if ! command -v "$CHROME_BIN" >/dev/null 2>&1; then
  if command -v google-chrome-stable >/dev/null 2>&1; then
    CHROME_BIN="google-chrome-stable"
  else
    printf 'Google Chrome was not found. Set CHROME_BIN to its executable path.\n' >&2
    exit 1
  fi
fi

printf 'Starting backend at %s ...\n' "$BACKEND_URL"
if [[ "$PROTOTYPE_MODE" == "true" ]]; then
  printf '%s\n' 'Local prototype mode enabled: local auto-login, SQLite, and private local blobs. Not for production or sensitive invoices.'
fi
(
  cd "$BACKEND_DIR"
  PROTOTYPE_MODE="$PROTOTYPE_MODE" exec uv run fastapi dev src/invoice_agent/main.py --host 127.0.0.1 --port "${BACKEND_PORT:-8000}"
) >"$BACKEND_LOG" 2>&1 &
backend_pid=$!

backend_deadline=$((SECONDS + STARTUP_TIMEOUT))
until curl --fail --silent --output /dev/null "${BACKEND_URL}/api/v1/health"; do
  if ! kill -0 "$backend_pid" 2>/dev/null; then
    printf 'Backend exited during startup. Log: %s\n' "$BACKEND_LOG" >&2
    cat "$BACKEND_LOG" >&2
    exit 1
  fi
  if (( SECONDS >= backend_deadline )); then
    printf 'Backend did not become ready within %s seconds. Log: %s\n' "$STARTUP_TIMEOUT" "$BACKEND_LOG" >&2
    cat "$BACKEND_LOG" >&2
    exit 1
  fi
  sleep 1
done

printf 'Starting processing worker ...\n'
(
  cd "$BACKEND_DIR"
  PROTOTYPE_MODE="$PROTOTYPE_MODE" exec uv run python -m invoice_agent.worker.runner
) >"$WORKER_LOG" 2>&1 &
worker_pid=$!

printf 'Starting frontend at %s ...\n' "$FRONTEND_URL"
(
  cd "$FRONTEND_DIR"
  VITE_PROTOTYPE_MODE="$PROTOTYPE_MODE" exec npm run dev -- --host 127.0.0.1 --port "${FRONTEND_PORT:-5173}" --strictPort
) >"$FRONTEND_LOG" 2>&1 &
frontend_pid=$!

wait_for_frontend() {
  local deadline=$((SECONDS + STARTUP_TIMEOUT))
  until curl --fail --silent --output /dev/null "$FRONTEND_URL"; do
    if ! kill -0 "$frontend_pid" 2>/dev/null; then
      printf 'Frontend server exited before becoming ready. Log: %s\n' "$FRONTEND_LOG" >&2
      cat "$FRONTEND_LOG" >&2
      return 1
    fi
    if ! kill -0 "$backend_pid" 2>/dev/null; then
      printf 'Backend server exited during startup. Log: %s\n' "$BACKEND_LOG" >&2
      cat "$BACKEND_LOG" >&2
      return 1
    fi
    if ! kill -0 "$worker_pid" 2>/dev/null; then
      printf 'Processing worker exited during startup. Log: %s\n' "$WORKER_LOG" >&2
      cat "$WORKER_LOG" >&2
      return 1
    fi
    if (( SECONDS >= deadline )); then
      printf 'Frontend did not become ready within %s seconds. Log: %s\n' "$STARTUP_TIMEOUT" "$FRONTEND_LOG" >&2
      cat "$FRONTEND_LOG" >&2
      return 1
    fi
    sleep 1
  done
}

wait_for_frontend
printf 'Frontend is ready at %s. VS Code will forward port %s and open it in your local browser.\n' \
  "$FRONTEND_URL" "${FRONTEND_PORT:-5173}"
printf '%s\n' 'If VS Code does not open it automatically, use the Ports panel and select Open in Browser for Invoice Intake UI.'
printf 'Opening %s in Google Chrome on this machine ...\n' "$FRONTEND_URL"
if "$CHROME_BIN" --new-window "$FRONTEND_URL" >/dev/null 2>&1 & then
  chrome_pid=$!
  disown "$chrome_pid" 2>/dev/null || true
else
  printf 'Chrome could not be launched here; use the VS Code forwarded port for local Chrome.\n' >&2
fi

printf 'API, processing worker, and frontend are running. Press Ctrl+C to stop them.\n'
printf 'Backend log:  %s\nWorker log:   %s\nFrontend log: %s\n' "$BACKEND_LOG" "$WORKER_LOG" "$FRONTEND_LOG"
wait "$backend_pid" "$worker_pid" "$frontend_pid"
