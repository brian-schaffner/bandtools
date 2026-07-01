#!/usr/bin/env bash
# SetLoader login service: wait for Tailscale, configure Serve, run backend + frontend.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_DIR/service.log"
}

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

BACKEND_PORT="${BACKEND_PORT:-8002}"
FRONTEND_PORT="${FRONTEND_PORT:-3002}"
PYTHON="${PYTHON:-/usr/bin/python3}"
NODE_PATH="${NODE_PATH:-/opt/homebrew/bin}"

export PATH="${NODE_PATH}:/usr/local/bin:/usr/bin:/bin:${HOME}/Library/Python/3.9/lib/python/site-packages"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  log "Stopping SetLoader services..."
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait_for_tailscale() {
  local max=90 i=0
  while (( i < max )); do
    if tailscale status >/dev/null 2>&1; then
      log "Tailscale is up"
      return 0
    fi
    if (( i % 5 == 0 )); then
      log "Waiting for Tailscale ($((i + 1))/${max})..."
      open -a Tailscale 2>/dev/null || true
    fi
    sleep 2
    ((i++))
  done
  log "ERROR: Tailscale did not become ready in time"
  return 1
}

setup_tailscale_serve() {
  if [[ -x "$ROOT/configure-tailscale.sh" ]]; then
    log "Configuring Tailscale Serve..."
    if ! "$ROOT/configure-tailscale.sh" >>"$LOG_DIR/tailscale.log" 2>&1; then
      log "WARN: configure-tailscale.sh failed (see logs/tailscale.log)"
    fi
  fi
}

setup_frontend_env() {
  local host api_url
  host="$("$PYTHON" -c "
import json, subprocess, sys
try:
    out = subprocess.check_output(['tailscale', 'status', '--json'], text=True)
    data = json.loads(out)
    print(data['Self']['DNSName'].rstrip('.'))
except Exception:
    sys.exit(1)
" 2>/dev/null || echo "")"

  TAILNET_HOST="$host"
  export TAILNET_HOST

  if [[ -n "$host" ]]; then
    api_url="https://${host}/api"
  else
    api_url="http://127.0.0.1:${BACKEND_PORT}"
  fi

  cat > "$ROOT/setlist-helper/.env.local" <<EOF
NEXT_PUBLIC_API_URL=${api_url}
NEXT_PUBLIC_API_SECRET=${NEXT_PUBLIC_API_SECRET:-${SECRET:-change-me}}
NEXT_PUBLIC_FRONTEND_PORT=${FRONTEND_PORT}
EOF
  log "Wrote setlist-helper/.env.local (API: ${api_url})"
}

stop_existing() {
  pkill -f "uvicorn server_simple_db:app" 2>/dev/null || true
  pkill -f "next dev -p ${FRONTEND_PORT}" 2>/dev/null || true
  sleep 1
}

start_backend() {
  log "Starting backend on 127.0.0.1:${BACKEND_PORT}"
  # Ensure Google OAuth redirect matches how the UI is accessed (tailnet vs localhost)
  if [[ -z "${GOOGLE_REDIRECT_URI:-}" && -n "${TAILNET_HOST:-}" ]]; then
    export GOOGLE_REDIRECT_URI="https://${TAILNET_HOST}/auth/google/callback"
  fi
  SECRET="${SECRET:-change-me}" \
  GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}" \
  GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}" \
  GOOGLE_REDIRECT_URI="${GOOGLE_REDIRECT_URI:-}" \
  "$PYTHON" -m uvicorn server_simple_db:app \
    --host 127.0.0.1 \
    --port "$BACKEND_PORT" \
    >>"$LOG_DIR/backend.log" 2>&1 &
  BACKEND_PID=$!
}

start_frontend() {
  log "Starting frontend on port ${FRONTEND_PORT}"
  (
    cd "$ROOT/setlist-helper"
    export PORT="$FRONTEND_PORT"
    npm run dev
  ) >>"$LOG_DIR/frontend.log" 2>&1 &
  FRONTEND_PID=$!
}

main() {
  log "SetLoader service starting (root: $ROOT)"
  stop_existing
  wait_for_tailscale
  setup_tailscale_serve
  setup_frontend_env
  start_backend
  sleep 2
  start_frontend

  local host
  host="$(tailscale status --json 2>/dev/null | "$PYTHON" -c "import json,sys; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))" 2>/dev/null || echo 'localhost')"
  log "SetLoader running — https://${host}/ (backend PID ${BACKEND_PID}, frontend PID ${FRONTEND_PID})"

  while true; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
      log "Backend exited; launchd will restart the service"
      exit 1
    fi
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
      log "Frontend exited; launchd will restart the service"
      exit 1
    fi
    sleep 10
  done
}

main
