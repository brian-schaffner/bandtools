#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

BACKEND_PORT="${BACKEND_PORT:-8002}"
FRONTEND_PORT="${FRONTEND_PORT:-3002}"

TAILNET_HOST="$(tailscale status --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['Self']['DNSName'].rstrip('.'))
")"

TAILNET_API_URL="https://${TAILNET_HOST}/api"

echo "Tailnet host: ${TAILNET_HOST}"
echo "API URL:      ${TAILNET_API_URL}"
echo ""

./configure-tailscale.sh

cat > setlist-helper/.env.local <<EOF
NEXT_PUBLIC_API_URL=${TAILNET_API_URL}
NEXT_PUBLIC_API_SECRET=${NEXT_PUBLIC_API_SECRET:-${SECRET:-change-me}}
NEXT_PUBLIC_FRONTEND_PORT=${FRONTEND_PORT}
EOF

echo "Wrote setlist-helper/.env.local"
echo ""

pkill -f "uvicorn server_simple_db:app" 2>/dev/null || true
pkill -f "next dev -p ${FRONTEND_PORT}" 2>/dev/null || true
sleep 1

echo "Starting backend on port ${BACKEND_PORT}..."
SECRET="${SECRET:-change-me}" python3 -m uvicorn server_simple_db:app \
  --host 127.0.0.1 \
  --port "${BACKEND_PORT}" \
  --reload &
BACKEND_PID=$!

sleep 2

echo "Starting frontend on port ${FRONTEND_PORT}..."
(
  cd setlist-helper
  PORT="${FRONTEND_PORT}" npm run dev
) &
FRONTEND_PID=$!

trap 'echo; echo "Stopping..."; kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null; exit' INT TERM

echo ""
echo "SetLoader is available on your tailnet at:"
echo "  https://${TAILNET_HOST}/"
echo ""
echo "On your iPhone: open Tailscale, then visit that URL in Safari."
echo "Press Ctrl+C to stop both servers (Tailscale Serve keeps running)."
echo ""

wait
