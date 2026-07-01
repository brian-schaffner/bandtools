#!/usr/bin/env bash
# Prepare persistent volume paths before supervisord starts all services.
set -euo pipefail

DATA="${DATA_DIR:-/data}"
SETLOADER="/app/setloader"
FLYERS="/app/gig-flyers"

mkdir -p "$DATA"/{user_data,oauth_credentials,downloads,work,forensic,cache,flyers-output}
mkdir -p "$FLYERS/output" "$FLYERS/cache" "$FLYERS/logs"

for d in user_data oauth_credentials downloads work forensic; do
  rm -rf "$SETLOADER/$d" 2>/dev/null || true
  ln -sfn "$DATA/$d" "$SETLOADER/$d"
done

touch "$DATA/setloader.db"
ln -sfn "$DATA/setloader.db" "$SETLOADER/setloader.db"

ln -sfn "$DATA/flyers-output" "$FLYERS/output"
ln -sfn "$DATA/cache" "$FLYERS/cache"
if [[ ! -s "$DATA/flyers-state.json" ]]; then
  printf '%s\n' '{"gigs": {}, "last_poll_rowid": 0}' > "$DATA/flyers-state.json"
fi
ln -sfn "$DATA/flyers-state.json" "$FLYERS/state.json"

if [[ -z "${APP_URL:-}" && -n "${FLY_APP_NAME:-}" ]]; then
  export APP_URL="https://${FLY_APP_NAME}.fly.dev"
fi
if [[ -z "${GOOGLE_REDIRECT_URI:-}" && -n "${APP_URL:-}" ]]; then
  export GOOGLE_REDIRECT_URI="${APP_URL}/auth/google/callback"
fi
if [[ -z "${BRIDGE_PUBLIC_URL:-}" && -n "${APP_URL:-}" ]]; then
  export BRIDGE_PUBLIC_URL="${APP_URL}/flyers"
fi
if [[ -z "${BAND_TOOLS_URL:-}" && -n "${APP_URL:-}" ]]; then
  export BAND_TOOLS_URL="${APP_URL}"
fi

echo "[fly-entrypoint] APP_URL=${APP_URL:-unset} DATA_DIR=$DATA"
exec "$@"
