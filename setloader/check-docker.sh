#!/usr/bin/env bash
set -euo pipefail

log()   { printf "%s\n" "$*"; }
ok()    { printf "✅ %s\n" "$*"; }
warn()  { printf "⚠️  %s\n" "$*" >&2; }
err()   { printf "❌ %s\n" "$*" >&2; }

# --- Find colima even if PATH is minimal ---
COLIMA_BIN="$(command -v colima || true)"
if [[ -z "${COLIMA_BIN}" ]]; then
  # Common Homebrew locations
  for p in /opt/homebrew/bin/colima /usr/local/bin/colima ; do
    [[ -x "$p" ]] && COLIMA_BIN="$p" && break
  done
fi

# Ensure Homebrew bin dirs are on PATH for child processes
export PATH="${PATH}:/opt/homebrew/bin:/usr/local/bin"

# --- Helpers ---
docker_ok() { docker info >/dev/null 2>&1; }
have()      { command -v "$1" >/dev/null 2>&1; }

# --- Try to ensure Docker talks to Colima socket if present ---
ensure_socket_env() {
  local sock="$HOME/.colima/default/docker.sock"
  if [[ -S "$sock" ]]; then
    # Only set DOCKER_HOST if docker isn't currently reachable
    if ! docker_ok; then
      export DOCKER_HOST="unix://$sock"
      ok "Set DOCKER_HOST to Colima socket ($sock)."
    fi
  fi
}

# --- Main ---
log "🔍 Checking Docker/Colima readiness…"

if ! have docker; then
  err "Docker CLI not found in PATH. Install Docker CLI (e.g., via Homebrew)."
  exit 127
fi

# Fast path: already good
if docker_ok; then
  ok "Docker is already responding."
  exit 0
fi

# If colima is available, try to start/fix it
if [[ -n "${COLIMA_BIN}" ]]; then
  # Get status (avoid relying on shell rc PATH)
  STATUS="$("$COLIMA_BIN" status 2>/dev/null || true)"
  if grep -qi "not running" <<<"$STATUS"; then
    warn "Colima is not running. Starting Colima…"
    "$COLIMA_BIN" start
  else
    warn "Colima appears installed but may not be running or reachable. Attempting restart…"
    "$COLIMA_BIN" stop || true
    "$COLIMA_BIN" start
  fi

  # Point Docker at Colima socket if needed
  ensure_socket_env

  # Also try Docker context 'colima' if it exists
  if docker context ls --format '{{.Name}}' 2>/dev/null | grep -qx colima; then
    warn "Switching Docker context to 'colima'…"
    docker context use colima >/dev/null
  fi
else
  warn "Colima not found. If you intend to use Colima, install it (brew install colima)."
fi

# Re-check Docker
if docker_ok; then
  ok "Docker is ready."
  exit 0
fi

# One last nudge: if Colima socket exists, force DOCKER_HOST
if [[ -z "${DOCKER_HOST:-}" ]]; then
  ensure_socket_env
fi

if docker_ok; then
  ok "Docker is ready."
  exit 0
fi

# Give a concise diag
err "Failed to connect to Docker after attempting Colima start/restart."
warn "Tips:"
warn " • If using Colima: brew install colima && colima start"
warn " • Ensure your shell exports: DOCKER_HOST=unix://\$HOME/.colima/default/docker.sock"
warn " • Or switch context: docker context use colima"
exit 1