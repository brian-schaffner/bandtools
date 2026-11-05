#!/usr/bin/env bash
# Stage performance-day logistics secrets (drive times + email) on a Fly app.
# Only non-empty values are sent, so unset CI secrets never clear values already on Fly.
# Staged secrets take effect on the next deploy.
#
#   ./scripts/deploy/sync-logistics-secrets.sh bandtools-test
set -euo pipefail

app="${1:?usage: $0 <fly-app>}"
names=(
  GOOGLE_MAPS_API_KEY
  BAND_HOME_ADDRESS
  SMTP_HOST
  SMTP_PORT
  SMTP_USER
  SMTP_PASSWORD
  EMAIL_FROM
  LOGISTICS_EMAIL_TO
)

payload=""
synced=()
for name in "${names[@]}"; do
  value="${!name:-}"
  value="${value//$'\r'/}"
  [[ -z "$value" ]] && continue
  if [[ "$value" == *$'\n'* ]]; then
    echo "ERROR: ${name} contains a newline; fix the secret value." >&2
    exit 1
  fi
  payload+="${name}=${value}"$'\n'
  synced+=("$name")
done

if [[ ${#synced[@]} -eq 0 ]]; then
  echo "No logistics secrets set in CI — leaving ${app} secrets unchanged."
  exit 0
fi

printf '%s' "$payload" | flyctl secrets import --stage -a "$app"
echo "Staged on ${app}: ${synced[*]}"
