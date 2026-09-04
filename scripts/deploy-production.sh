#!/usr/bin/env bash
# Deploy Band Tools to production (bandtools.fly.dev).
#
# Usage:
#   ./scripts/deploy-production.sh              # deploy + smoke test
#   ./scripts/deploy-production.sh --no-smoke   # deploy only
#   ./scripts/deploy-production.sh --dry-run    # show plan, no deploy
#   ./scripts/deploy-production.sh --skip-secrets
#   ./scripts/deploy-production.sh --skip-backup
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/deploy/lib.sh"
# shellcheck source=deploy/production.env
source "${SCRIPT_DIR}/deploy/production.env"

ROOT="$(deploy_repo_root)"
cd "$ROOT"

RUN_SMOKE=1
DRY_RUN=0
SKIP_SECRETS=0
SKIP_BACKUP=0

usage() {
  cat <<EOF
Deploy Band Tools to production (${PRODUCTION_URL}).

⚠️  WARNING: This deploys to PRODUCTION!

Options:
  --no-smoke       Skip post-deploy smoke tests
  --skip-secrets   Do not sync secrets from .env (image deploy only)
  --skip-backup    Skip pre-deploy volume snapshot
  --dry-run        Print deploy plan without changing Fly
  -h, --help       Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-smoke) RUN_SMOKE=0 ;;
    --skip-secrets) SKIP_SECRETS=1 ;;
    --skip-backup) SKIP_BACKUP=1 ;;
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

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ⚠️   PRODUCTION DEPLOY                                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

print_deploy_context "Band Tools — PRODUCTION DEPLOY" "$FLY_APP_NAME" "$PRODUCTION_URL" "$FLY_CONFIG"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] Would deploy:"
  echo "  fly deploy -a ${FLY_APP_NAME} -c ${FLY_CONFIG}"
  echo "  backup:  $([[ "$SKIP_BACKUP" -eq 1 ]] && echo skip || echo create volume snapshot)"
  echo "  secrets: $([[ "$SKIP_SECRETS" -eq 1 ]] && echo skip || echo sync from ${ENV_FILE})"
  echo "  smoke:   $([[ "$RUN_SMOKE" -eq 1 ]] && echo yes || echo no)"
  exit 0
fi

require_fly_cli
ensure_fly_app "$FLY_APP_NAME"
ensure_fly_volume "$FLY_APP_NAME" "$FLY_VOLUME_NAME" "$FLY_REGION"

# Create backup snapshot before deploying
if [[ "$SKIP_BACKUP" -eq 0 ]]; then
  echo "==> Creating pre-deploy backup snapshot..."
  VOLUME_ID=$(fly volumes list -a "$FLY_APP_NAME" --json | jq -r '.[0].id')
  if [[ -n "$VOLUME_ID" && "$VOLUME_ID" != "null" ]]; then
    fly volumes snapshots create "$VOLUME_ID" -a "$FLY_APP_NAME"
    SNAPSHOT_ID=$(fly volumes snapshots list "$VOLUME_ID" -a "$FLY_APP_NAME" --json | jq -r '.[0].id')
    echo "✅ Backup snapshot created: $SNAPSHOT_ID"
    echo ""
    echo "To restore if needed:"
    echo "  fly volumes snapshots restore $SNAPSHOT_ID -a $FLY_APP_NAME"
    echo ""
  else
    echo "⚠️  No volume found, skipping backup"
  fi
fi

if [[ "$SKIP_SECRETS" -eq 0 ]]; then
  sync_fly_secrets "$FLY_APP_NAME" "$ENV_FILE"
fi

BUILD_SECRET="$(resolve_build_secret "$ENV_FILE")"
export BANDTOOLS_DEPLOY_ENV="production"
fly_deploy_image "$FLY_APP_NAME" "$CONFIG_PATH" "$BUILD_SECRET"

print_deploy_success "$FLY_APP_NAME"

if [[ "$RUN_SMOKE" -eq 1 ]]; then
  echo "==> Post-deploy smoke tests"
  run_smoke_checks "$PRODUCTION_URL"
fi

echo "Production is ready: ${PRODUCTION_URL}"
