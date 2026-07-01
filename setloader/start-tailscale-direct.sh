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
TAILNET_IP="$(tailscale ip -4 | head -1)"
TAILNET_API_URL="http://${TAILNET_IP}:${BACKEND_PORT}"

echo "Direct tailnet IP mode (fallback when MagicDNS fails on iPhone)"
echo "  UI:  http://${TAILNET_IP}:${FRONTEND_PORT}"
echo "  API: ${TAILNET_API_URL}"
echo ""

cat > setlist-helper/.env.local <<EOF
NEXT_PUBLIC_API_URL=${TAILNET_API_URL}
NEXT_PUBLIC_API_SECRET=${NEXT_PUBLIC_API_SECRET:-change-me}
NEXT_PUBLIC_FRONTEND_PORT=${FRONTEND_PORT}
EOF

pkill -f "uvicorn server_simple_db:app" 2>/dev/null || true
pkill -f "next dev -p ${FRONTEND_PORT}" 2>/dev/null || true
sleep 1

echo "Starting backend on 0.0.0.0:${BACKEND_PORT}..."
SECRET="${SECRET:-change-me}" python3 -m uvicorn server_simple_db:app \
  --host 0.0.0.0 \
  --port "${BACKEND_PORT}" \
  --reload &
BACKEND_PID=$!

sleep 2

echo "Starting frontend on 0.0.0.0:${FRONTEND_PORT}..."
(
  cd setlist-helper
  PORT="${FRONTEND_PORT}" npm run dev
) &
FRONTEND_PID=$!

trap 'echo; echo "Stopping..."; kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null; exit' INT TERM

echo ""
echo "On iPhone (Tailscale connected), open:"
echo "  http://${TAILNET_IP}:${FRONTEND_PORT}"
echo ""
echo "Press Ctrl+C to stop."
wait
