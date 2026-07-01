#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

wait_for_tailscale() {
  for i in $(seq 1 30); do
    if tailscale status >/dev/null 2>&1; then
      log "Tailscale is up"
      return 0
    fi
    log "Waiting for Tailscale ($i/30)..."
    open -a Tailscale 2>/dev/null || true
    sleep 10
  done
  log "WARN: Tailscale not ready; continuing anyway"
  return 0
}

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

wait_for_tailscale

if [[ -x "$ROOT/configure-tailscale.sh" ]]; then
  "$ROOT/configure-tailscale.sh" >>"$ROOT/logs/tailscale.log" 2>&1 || log "WARN: tailscale configure failed"
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
fi

exec "$ROOT/.venv/bin/python" -m uvicorn bridge.server:app --host 127.0.0.1 --port "${BRIDGE_PORT:-8010}"
