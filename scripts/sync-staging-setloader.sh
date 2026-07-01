#!/usr/bin/env bash
# Copy Setlist Loader backup + title mappings from production to staging.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.fly/bin:${PATH}"

PROD_APP="${PROD_APP:-bandtools}"
STAGING_APP="${STAGING_APP:-bandtools-test}"
WORKDIR="${TMPDIR:-/tmp}/bandtools-setloader-sync-$$"
REMOTE="/tmp/sync_setloader_data.py"
ARCHIVE="/tmp/setloader-sync.tgz"

mkdir -p "$WORKDIR/export"
trap 'rm -rf "$WORKDIR"' EXIT

echo "==> Upload sync helper to $PROD_APP"
fly ssh sftp put -a "$PROD_APP" "$ROOT/scripts/sync_setloader_data.py" "$REMOTE"

echo "==> Export from production"
fly ssh console -a "$PROD_APP" -C "python3 $REMOTE export --out-dir /tmp/setloader-export" | tee "$WORKDIR/export.log"
fly ssh console -a "$PROD_APP" -C "python3 $REMOTE pack --in-dir /tmp/setloader-export --archive $ARCHIVE"
fly ssh sftp get -a "$PROD_APP" "$ARCHIVE" "$WORKDIR/setloader-sync.tgz"
python3 "$ROOT/scripts/sync_setloader_data.py" unpack --archive "$WORKDIR/setloader-sync.tgz" --out-dir "$WORKDIR"

echo "==> Import into staging"
fly ssh sftp put -a "$STAGING_APP" "$ROOT/scripts/sync_setloader_data.py" "$REMOTE"
fly ssh sftp put -a "$STAGING_APP" "$WORKDIR/export/manifest.json" /tmp/setloader-export/manifest.json
if [[ -f "$WORKDIR/export/backup.sbpbackup" ]]; then
  fly ssh sftp put -a "$STAGING_APP" "$WORKDIR/export/backup.sbpbackup" /tmp/setloader-export/backup.sbpbackup
fi
fly ssh console -a "$STAGING_APP" -C "python3 $REMOTE import --in-dir /tmp/setloader-export"

echo "==> Done: https://${STAGING_APP}.fly.dev/setlist-loader (Song Mapping tab should now have catalog + mappings)"
