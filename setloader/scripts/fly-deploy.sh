#!/usr/bin/env bash
# Deploy Band Tools to Fly.io (https://bandtools.fly.dev)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP="${FLY_APP_NAME:-bandtools}"
REGION="${FLY_REGION:-ord}"
VOLUME="${FLY_VOLUME_NAME:-bandtools_data}"

echo "==> Band Tools Fly deploy (app: ${APP})"

if ! fly apps list 2>/dev/null | grep -q "^${APP}[[:space:]]"; then
  echo "Creating Fly app ${APP}..."
  fly apps create "$APP"
fi

if ! fly volumes list -a "$APP" 2>/dev/null | grep -q "$VOLUME"; then
  echo "Creating volume ${VOLUME} in ${REGION}..."
  fly volumes create "$VOLUME" --region "$REGION" --size 1 -a "$APP" -y
fi

if [[ -f "$ROOT/.env" ]]; then
  echo "Setting secrets from .env..."
  # shellcheck disable=SC1091
  set -a
  source "$ROOT/.env"
  set +a
  fly secrets set -a "$APP" \
    SECRET="${SECRET:-change-me}" \
    OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
    GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}" \
    GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}" \
    GOOGLE_REDIRECT_URI="https://${APP}.fly.dev/auth/google/callback" \
    APP_URL="https://${APP}.fly.dev" \
    NEXT_PUBLIC_API_SECRET="${NEXT_PUBLIC_API_SECRET:-${SECRET:-change-me}}"
fi

echo "Deploying..."
fly deploy -a "$APP" --ha=false

echo ""
echo "Done: https://${APP}.fly.dev/"
echo "  /              Band Tools hub"
echo "  /setlist-loader"
echo "  /flyers/       → gig-flyers.fly.dev"
echo ""
echo "Add to Google OAuth authorized redirect URIs:"
echo "  https://${APP}.fly.dev/auth/google/callback"
