#!/usr/bin/env bash
# Stage performance-day logistics secrets (drive times + email) on a Fly app.
#
#   ./scripts/deploy/sync-logistics-secrets.sh bandtools-test
set -euo pipefail

app="${1:?usage: $0 <fly-app>}"
exec "$(dirname "$0")/stage-ci-secrets.sh" "$app" \
  GOOGLE_MAPS_API_KEY \
  BAND_HOME_ADDRESS \
  SMTP_HOST \
  SMTP_PORT \
  SMTP_USER \
  SMTP_PASSWORD \
  EMAIL_FROM \
  LOGISTICS_EMAIL_TO
