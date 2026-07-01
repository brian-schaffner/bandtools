#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v tailscale >/dev/null 2>&1; then
  echo "Tailscale is not installed. Install from https://tailscale.com/download"
  exit 1
fi

if ! tailscale status >/dev/null 2>&1; then
  echo "Tailscale is not connected. Run: tailscale up"
  exit 1
fi

BACKEND_PORT="${BACKEND_PORT:-8002}"
FRONTEND_PORT="${FRONTEND_PORT:-3002}"
FLYERS_PORT="${FLYERS_PORT:-8010}"

TAILNET_HOST="$(tailscale status --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['Self']['DNSName'].rstrip('.'))
")"

echo "Configuring Tailscale Serve for ${TAILNET_HOST}"
echo "  /        -> http://127.0.0.1:${FRONTEND_PORT} (Band Tools / Setlist Loader)"
echo "  /api     -> http://127.0.0.1:${BACKEND_PORT} (SetLoader API)"
echo "  /flyers  -> http://127.0.0.1:${FLYERS_PORT} (Gig Flyers bridge)"
echo ""

tailscale serve reset
tailscale serve --bg "${FRONTEND_PORT}"
tailscale serve --bg --set-path=/api "http://127.0.0.1:${BACKEND_PORT}"
tailscale serve --bg --set-path=/flyers "http://127.0.0.1:${FLYERS_PORT}"

echo ""
tailscale serve status
echo ""
echo "Open on any device signed into your tailnet:"
echo "  https://${TAILNET_HOST}/"
echo ""
echo "iPhone not loading? Run: ./check-tailscale-phone.sh"
