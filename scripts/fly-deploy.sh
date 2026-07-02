#!/usr/bin/env bash
# Deploy Band Tools to Fly.io (production or staging via FLY_CONFIG).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=deploy/lib.sh
source "${ROOT}/scripts/deploy/lib.sh"

CONFIG="${FLY_CONFIG:-fly.toml}"
if [[ "$CONFIG" == *test* ]]; then
  APP="${FLY_APP_NAME:-bandtools-test}"
  VOLUME="${FLY_VOLUME_NAME:-bandtools_test_data}"
else
  APP="${FLY_APP_NAME:-bandtools}"
  VOLUME="${FLY_VOLUME_NAME:-bandtools_data}"
fi
REGION="${FLY_REGION:-ord}"

print_deploy_context "Band Tools Fly deploy" "$APP" "https://${APP}.fly.dev" "$CONFIG"

require_fly_cli
ensure_fly_app "$APP"
ensure_fly_volume "$APP" "$VOLUME" "$REGION"

ENV_FILE="${ENV_FILE:-$ROOT/.env}"
sync_fly_secrets "$APP" "$ENV_FILE"

BUILD_SECRET="$(resolve_build_secret "$ENV_FILE")"
fly_deploy_image "$APP" "${ROOT}/${CONFIG}" "$BUILD_SECRET"

print_deploy_success "$APP"

echo "Add to Google OAuth authorized redirect URIs (if not already):"
echo "  https://bandtools.fly.dev/auth/google/callback"
echo "  https://bandtools-test.fly.dev/auth/google/callback"
