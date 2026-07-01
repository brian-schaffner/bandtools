#!/usr/bin/env bash
# Deploy Band Tools to Fly.io (production or test via FLY_CONFIG).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CONFIG="${FLY_CONFIG:-fly.toml}"
if [[ "$CONFIG" == *test* ]]; then
  APP="${FLY_APP_NAME:-bandtools-test}"
  VOLUME="${FLY_VOLUME_NAME:-bandtools_test_data}"
else
  APP="${FLY_APP_NAME:-bandtools}"
  VOLUME="${FLY_VOLUME_NAME:-bandtools_data}"
fi
REGION="${FLY_REGION:-ord}"

echo "==> Band Tools Fly deploy (app: ${APP}, config: ${CONFIG})"

if ! fly apps list 2>/dev/null | awk '{print $1}' | grep -qx "$APP"; then
  echo "Creating Fly app ${APP}..."
  fly apps create "$APP"
fi

if ! fly volumes list -a "$APP" 2>/dev/null | grep -q "$VOLUME"; then
  echo "Creating volume ${VOLUME} in ${REGION}..."
  fly volumes create "$VOLUME" --region "$REGION" --size 1 -a "$APP" -y
fi

ENV_FILE="${ENV_FILE:-$ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  echo "Setting secrets from ${ENV_FILE}..."
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
  fly secrets set -a "$APP" \
    SECRET="${SECRET:-change-me}" \
    OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
    GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}" \
    GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}" \
    GOOGLE_REDIRECT_URI="https://${APP}.fly.dev/auth/google/callback" \
    APP_URL="https://${APP}.fly.dev" \
    NEXT_PUBLIC_API_SECRET="${NEXT_PUBLIC_API_SECRET:-${SECRET:-change-me}}" \
    BRIDGE_SECRET="${BRIDGE_SECRET:-${SECRET:-change-me}}" \
    BRIDGE_PUBLIC_URL="https://${APP}.fly.dev/flyers" \
    BAND_TOOLS_URL="https://${APP}.fly.dev"
fi

echo "Deploying..."
fly deploy -a "$APP" -c "$CONFIG" --ha=false

echo ""
echo "Done: https://${APP}.fly.dev/"
echo "  /              Band Tools hub"
echo "  /setlist-loader"
echo "  /flyers/       Gig Flyers"
echo "  /api/health    Setloader API health"
echo ""
echo "Add to Google OAuth authorized redirect URIs:"
echo "  https://${APP}.fly.dev/auth/google/callback"
