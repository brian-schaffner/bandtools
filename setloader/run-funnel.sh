#!/usr/bin/env bash
set -euo pipefail

# Usage: ./funnel-up.sh [LOCAL_PORT] [PUBLIC_PORT: 443|8443|10000]
LOCAL_PORT="${1:-8000}"
PUBLIC_PORT="${2:-443}"

log()  { printf "%s\n" "$*"; }
ok()   { printf "✅ %s\n" "$*"; }
warn() { printf "⚠️  %s\n" "$*" >&2; }
err()  { printf "❌ %s\n" "$*" >&2; }

# Require tailscale CLI
if ! command -v tailscale >/dev/null 2>&1; then
  err "tailscale CLI not found (brew install tailscale)."
  exit 127
fi

# Ensure tailscaled is running (works for standalone installs)
if ! pgrep -x tailscaled >/dev/null 2>&1; then
  warn "tailscaled not running; attempting to start (may need sudo)…"
  if command -v tailscaled >/dev/null 2>&1; then
    sudo tailscaled >/tmp/tailscaled.log 2>&1 &
    sleep 2
  else
    # App Store / GUI install path
    open -ga "Tailscale"
    sleep 2
  fi
fi

# Must be logged in
if ! tailscale status >/dev/null 2>&1; then
  err "Not logged in. Run 'tailscale up' once, then re-run this script."
  exit 1
fi

# Configure Funnel (new CLI)
# Expose https://<your-node>.ts.net/ on PUBLIC_PORT and proxy to http://127.0.0.1:LOCAL_PORT
# Notes: Funnel HTTPS ports are limited to 443, 8443, or 10000.
log "Enabling Funnel: public :$PUBLIC_PORT → localhost:$LOCAL_PORT …"
tailscale funnel --bg --yes --https="${PUBLIC_PORT}" "localhost:${LOCAL_PORT}"

# Show status + URL
STATUS_JSON="$(tailscale funnel status --json || true)"
URL="$(tailscale funnel status 2>/dev/null | grep -Eo 'https://[^ ]+' | head -n1 || true)"

if [[ -n "${URL}" ]]; then
  ok "Funnel is live at: ${URL}"
else
  warn "Funnel enabled, but no URL parsed. Raw status:"
  printf "%s\n" "${STATUS_JSON:-<none>}"
fi

ok "Funnel runs persistently in background (survives restart). To disable:"
echo "  tailscale funnel --https=${PUBLIC_PORT} off"