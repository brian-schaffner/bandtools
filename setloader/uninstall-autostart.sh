#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.setloader.services"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
GUI_DOMAIN="gui/$(id -u)"

echo "Removing SetLoader autostart..."

launchctl bootout "${GUI_DOMAIN}/${LABEL}" 2>/dev/null || true
rm -f "$PLIST_DEST"

pkill -f "uvicorn server_simple_db:app" 2>/dev/null || true
pkill -f "next dev -p" 2>/dev/null || true

echo "Uninstalled. LaunchAgent removed; running servers stopped."
echo "Tailscale Serve routes were left as-is. Reset with: tailscale serve reset"
