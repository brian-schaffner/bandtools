#!/usr/bin/env bash
# Copy local SQLite + user_data to the bandtools Fly volume.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${FLY_APP_NAME:-bandtools}"
USER_ID="${MIGRATE_USER_ID:-35e76f8b-65f7-48c1-9920-932122e98219}"

cd "$ROOT"

if [[ ! -f "$ROOT/setloader.db" ]]; then
  echo "ERROR: $ROOT/setloader.db not found"
  exit 1
fi

if [[ ! -d "$ROOT/user_data/$USER_ID" ]]; then
  echo "ERROR: user_data/$USER_ID not found"
  exit 1
fi

echo "==> Migrating SetLoader data to Fly app: $APP"
echo "    DB: $(sqlite3 "$ROOT/setloader.db" 'SELECT COUNT(*) FROM title_mappings;') title mappings"
echo "    user_data: user_data/$USER_ID"

MACHINE_ID="$(fly machines list -a "$APP" --json | python3 -c "import json,sys; m=json.load(sys.stdin); print(m[0]['id'] if m else '')")"
if [[ -z "$MACHINE_ID" ]]; then
  echo "ERROR: No machine found for $APP"
  exit 1
fi

echo "==> Stopping machine $MACHINE_ID (releases SQLite lock)..."
fly machine stop "$MACHINE_ID" -a "$APP" >/dev/null 2>&1 || true
sleep 2

echo "==> Starting machine for SFTP upload..."
fly machine start "$MACHINE_ID" -a "$APP"
sleep 5

echo "==> Pausing app and clearing remote DB (fly sftp won't overwrite)..."
fly ssh console -a "$APP" --machine "$MACHINE_ID" -C "pkill uvicorn || true"
fly ssh console -a "$APP" --machine "$MACHINE_ID" -C "pkill node || true"
fly ssh console -a "$APP" --machine "$MACHINE_ID" -C "rm -f /data/setloader.db"
echo "==> Uploading setloader.db..."
fly ssh sftp put -a "$APP" --machine "$MACHINE_ID" \
  "$ROOT/setloader.db" /data/setloader.db

echo "==> Uploading user_data/$USER_ID (includes backup + title_mapper.json)..."
fly ssh sftp put -a "$APP" --machine "$MACHINE_ID" -R \
  "$ROOT/user_data/$USER_ID" "/data/user_data/$USER_ID"

if [[ -d "$ROOT/oauth_credentials" ]]; then
  echo "==> Uploading oauth_credentials..."
  fly ssh sftp put -a "$APP" --machine "$MACHINE_ID" -R \
    "$ROOT/oauth_credentials" /data/oauth_credentials
fi

echo "==> Restarting machine (fresh app + migrated data)..."
fly machine restart "$MACHINE_ID" -a "$APP"

echo ""
echo "Done. Sign in again at https://${APP}.fly.dev/ — mappings should be restored."
echo "(OAuth looks up your account by email, so you'll get the same user id.)"
