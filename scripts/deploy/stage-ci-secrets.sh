#!/usr/bin/env bash
# Stage the named CI environment variables as secrets on a Fly app.
# Only non-empty values are sent, so unset CI secrets never clear values already on Fly.
# Staged secrets take effect on the next deploy.
#
#   ./scripts/deploy/stage-ci-secrets.sh bandtools-test FACEBOOK_PAGE_ID FACEBOOK_PAGE_ACCESS_TOKEN
set -euo pipefail

app="${1:?usage: $0 <fly-app> NAME [NAME...]}"
shift
[[ $# -gt 0 ]] || { echo "usage: $0 <fly-app> NAME [NAME...]" >&2; exit 2; }

payload=""
synced=()
for name in "$@"; do
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
  echo "None of [$*] set in CI — leaving ${app} secrets unchanged."
  exit 0
fi

printf '%s' "$payload" | flyctl secrets import --stage -a "$app"
echo "Staged on ${app}: ${synced[*]}"
