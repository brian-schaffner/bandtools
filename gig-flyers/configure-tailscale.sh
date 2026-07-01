#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

if ! command -v tailscale >/dev/null 2>&1; then
  echo "Tailscale is not installed."
  exit 1
fi

if ! tailscale status >/dev/null 2>&1; then
  echo "Tailscale is not connected. Run: tailscale up"
  exit 1
fi

BRIDGE_PORT="${BRIDGE_PORT:-8010}"

TAILNET_HOST="$(tailscale status --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['Self']['DNSName'].rstrip('.'))
")"

echo "Configuring Tailscale Serve for gig-flyers bridge"
echo "  /flyers -> http://127.0.0.1:${BRIDGE_PORT}"
echo ""

# Add path without resetting other serve routes if possible
tailscale serve --bg --set-path=/flyers "http://127.0.0.1:${BRIDGE_PORT}"

echo ""
tailscale serve status
echo ""
echo "Bridge URL:"
echo "  https://${TAILNET_HOST}/flyers/"
echo "  https://${TAILNET_HOST}/flyers/pick"
echo "  https://${TAILNET_HOST}/flyers/health"
echo "  https://${TAILNET_HOST}/flyers/review/{gig_id}"
echo ""
echo "Set in .env:"
echo "  BRIDGE_PUBLIC_URL=https://${TAILNET_HOST}/flyers"
