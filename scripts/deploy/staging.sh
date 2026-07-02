#!/usr/bin/env bash
# Deploy Band Tools to staging (bandtools-test.fly.dev).
#
# Usage:
#   ./scripts/deploy-staging.sh              # deploy + smoke test
#   ./scripts/deploy-staging.sh --no-smoke   # deploy only
#   ./scripts/deploy-staging.sh --dry-run    # show plan, no deploy
#   ./scripts/deploy-staging.sh --skip-secrets
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"
# shellcheck source=staging.env
source "${SCRIPT_DIR}/staging.env"

ROOT="$(deploy_repo_root)"
cd "$ROOT"

RUN_SMOKE=1
DRY_RUN=0
SKIP_SECRETS=0

usage() {
  cat <<EOF
Deploy Band Tools to staging (${STAGING_URL}).

Options:
  --no-smoke       Skip post-deploy smoke tests
  --skip-secrets   Do not sync secrets from .env (image deploy only)
  --dry-run        Print deploy plan without changing Fly
  -h, --help       Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-smoke) RUN_SMOKE=0 ;;
    --skip-secrets) SKIP_SECRETS=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

ENV_FILE="${ENV_FILE:-${ROOT}/.env}"
CONFIG_PATH="${ROOT}/${FLY_CONFIG}"

print_deploy_context "Band Tools — STAGING DEPLOY" "$FLY_APP_NAME" "$STAGING_URL" "$FLY_CONFIG"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] Would deploy:"
  echo "  fly deploy -a ${FLY_APP_NAME} -c ${FLY_CONFIG}"
  echo "  secrets: $([[ "$SKIP_SECRETS" -eq 1 ]] && echo skip || echo sync from ${ENV_FILE})"
  echo "  smoke:   $([[ "$RUN_SMOKE" -eq 1 ]] && echo yes || echo no)"
  exit 0
fi

require_fly_cli
ensure_fly_app "$FLY_APP_NAME"
ensure_fly_volume "$FLY_APP_NAME" "$FLY_VOLUME_NAME" "$FLY_REGION"

if [[ "$SKIP_SECRETS" -eq 0 ]]; then
  sync_fly_secrets "$FLY_APP_NAME" "$ENV_FILE"
fi

BUILD_SECRET="$(resolve_build_secret "$ENV_FILE")"
fly_deploy_image "$FLY_APP_NAME" "$CONFIG_PATH" "$BUILD_SECRET"

print_deploy_success "$FLY_APP_NAME"

if [[ "$RUN_SMOKE" -eq 1 ]]; then
  echo "==> Post-deploy smoke tests"
  run_smoke_checks "$STAGING_URL"
fi

echo "Staging is ready: ${STAGING_URL}/flyers/shell"
