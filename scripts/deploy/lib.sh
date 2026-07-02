#!/usr/bin/env bash
# Shared Fly.io deploy helpers for Band Tools.
set -euo pipefail

deploy_repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}

require_fly_cli() {
  if ! command -v fly >/dev/null 2>&1; then
    echo "ERROR: fly CLI not found. Install: https://fly.io/docs/hands-on/install-flyctl/" >&2
    return 1
  fi
  if ! fly auth whoami >/dev/null 2>&1; then
    echo "ERROR: fly CLI is not authenticated. Run: fly auth login" >&2
    return 1
  fi
}

print_deploy_context() {
  local label="$1"
  local app="$2"
  local url="$3"
  local config="$4"
  local root
  root="$(deploy_repo_root)"

  echo ""
  echo "╔══════════════════════════════════════════════════════════════╗"
  printf "║  %-60s║\n" "$label"
  echo "╠══════════════════════════════════════════════════════════════╣"
  printf "║  App:     %-51s║\n" "$app"
  printf "║  URL:     %-51s║\n" "$url"
  printf "║  Config:  %-51s║\n" "$config"
  if command -v git >/dev/null 2>&1 && git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local branch commit dirty
    branch="$(git -C "$root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
    commit="$(git -C "$root" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
    if [[ -n "$(git -C "$root" status --porcelain 2>/dev/null)" ]]; then
      dirty=" (uncommitted changes)"
    else
      dirty=""
    fi
    printf "║  Git:     %-51s║\n" "${branch} @ ${commit}${dirty}"
  fi
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo ""
}

ensure_fly_app() {
  local app="$1"
  if ! fly apps list 2>/dev/null | awk '{print $1}' | grep -qx "$app"; then
    echo "Creating Fly app ${app}..."
    fly apps create "$app"
  fi
}

ensure_fly_volume() {
  local app="$1"
  local volume="$2"
  local region="$3"
  if ! fly volumes list -a "$app" 2>/dev/null | grep -q "$volume"; then
    echo "Creating volume ${volume} in ${region}..."
    fly volumes create "$volume" --region "$region" --size 1 -a "$app" -y
  fi
}

sync_fly_secrets() {
  local app="$1"
  local env_file="$2"
  if [[ ! -f "$env_file" ]]; then
    echo "NOTE: ${env_file} not found — skipping secret sync (existing Fly secrets kept)."
    return 0
  fi

  echo "Syncing secrets from ${env_file} to ${app}..."
  # shellcheck disable=SC1090
  set -a
  source "$env_file"
  set +a
  fly secrets set -a "$app" \
    SECRET="${SECRET:-change-me}" \
    OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
    GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}" \
    GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}" \
    GOOGLE_REDIRECT_URI="https://${app}.fly.dev/auth/google/callback" \
    APP_URL="https://${app}.fly.dev" \
    NEXT_PUBLIC_API_SECRET="${NEXT_PUBLIC_API_SECRET:-${SECRET:-change-me}}" \
    BRIDGE_SECRET="${BRIDGE_SECRET:-${SECRET:-change-me}}" \
    BRIDGE_PUBLIC_URL="https://${app}.fly.dev/flyers" \
    BAND_TOOLS_URL="https://${app}.fly.dev"
}

fly_deploy_image() {
  local app="$1"
  local config="$2"
  local build_secret="$3"
  echo "Deploying image to ${app}..."
  fly deploy -a "$app" -c "$config" --ha=false \
    --build-arg "NEXT_PUBLIC_API_SECRET=${build_secret}"
}

resolve_build_secret() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "$env_file"
    set +a
  fi
  echo "${NEXT_PUBLIC_API_SECRET:-${SECRET:-change-me}}"
}

run_smoke_checks() {
  local url="$1"
  local root
  root="$(deploy_repo_root)"
  "${root}/scripts/smoke-test.sh" "$url"
}

print_deploy_success() {
  local app="$1"
  echo ""
  echo "Deploy complete: https://${app}.fly.dev/"
  echo "  /              Band Tools hub"
  echo "  /setlist-loader"
  echo "  /flyers/       Gig Flyers (shell studio: /flyers/shell)"
  echo "  /api/health    Setloader API health"
  echo ""
}
