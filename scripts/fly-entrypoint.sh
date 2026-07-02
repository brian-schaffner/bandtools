#!/usr/bin/env bash
# Prepare persistent volume paths before supervisord starts all services.
set -euo pipefail

DATA="${DATA_DIR:-/data}"
SETLOADER="/app/setloader"
FLYERS="/app/gig-flyers"

mkdir -p "$DATA"/{user_data,oauth_credentials,downloads,work,forensic,cache,flyers-output}
mkdir -p "$FLYERS/logs"

for d in user_data oauth_credentials downloads work forensic; do
  rm -rf "$SETLOADER/$d" 2>/dev/null || true
  ln -sfn "$DATA/$d" "$SETLOADER/$d"
done

touch "$DATA/setloader.db"
ln -sfn "$DATA/setloader.db" "$SETLOADER/setloader.db"

# Replace output/cache dirs with symlinks (mkdir + ln without rm nests the link inside the dir).
rm -rf "$FLYERS/output" "$FLYERS/cache"
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

# Seed shell reference images from bundled assets (avoids Wikimedia rate limits on Fly).
if [[ -d "$FLYERS/assets/shell_references" ]]; then
  mkdir -p "$DATA/cache/shell_references"
  for src in "$FLYERS/assets/shell_references"/*; do
    [[ -f "$src" ]] || continue
    dest="$DATA/cache/shell_references/$(basename "$src")"
    dest_size=0
    if [[ -f "$dest" ]]; then
      dest_size="$(wc -c < "$dest" | tr -d ' ')"
    fi
    if [[ "${dest_size:-0}" -lt 5000 ]]; then
      cp "$src" "$dest"
    fi
  done
  seeded="$(find "$DATA/cache/shell_references" -type f 2>/dev/null | wc -l | tr -d ' ')"
  echo "[fly-entrypoint] shell reference cache: ${seeded} files"
fi

exec "$@"
