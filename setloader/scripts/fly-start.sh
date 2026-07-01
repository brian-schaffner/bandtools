#!/usr/bin/env bash
# Start Band Tools on Fly: Caddy (8080) → Next.js + FastAPI + Gig Flyers proxy
set -euo pipefail

ROOT="/app"
DATA="${DATA_DIR:-/data}"
BACKEND_PORT="${BACKEND_PORT:-8002}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

mkdir -p "$DATA"/{user_data,oauth_credentials,downloads,work,forensic}
for d in user_data oauth_credentials downloads work forensic; do
  rm -rf "$ROOT/$d" 2>/dev/null || true
  mkdir -p "$DATA/$d"
  ln -sfn "$DATA/$d" "$ROOT/$d"
done

touch "$DATA/setloader.db"
ln -sfn "$DATA/setloader.db" "$ROOT/setloader.db"

# Public URL for OAuth + CORS
if [[ -z "${APP_URL:-}" && -n "${FLY_APP_NAME:-}" ]]; then
  export APP_URL="https://${FLY_APP_NAME}.fly.dev"
fi
if [[ -z "${GOOGLE_REDIRECT_URI:-}" && -n "${APP_URL:-}" ]]; then
  export GOOGLE_REDIRECT_URI="${APP_URL}/auth/google/callback"
fi

echo "[fly-start] APP_URL=${APP_URL:-unset} API on :${BACKEND_PORT} UI on :${FRONTEND_PORT}"

python3 -m uvicorn server_simple_db:app \
  --host 127.0.0.1 \
  --port "$BACKEND_PORT" &

(
  cd "$ROOT/setlist-helper"
  export PORT="$FRONTEND_PORT"
  export HOSTNAME=127.0.0.1
  node server.js
) &

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
