#!/usr/bin/env bash
# Gig Flyer bridge autostart (LaunchAgent)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.gigflyers.bridge"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
GUI_DOMAIN="gui/$(id -u)"

echo "Gig Flyers bridge autostart installer"
echo "Project: $ROOT"

mkdir -p "$ROOT/logs"
chmod +x "$ROOT/scripts/bridge-service.sh"
chmod +x "$ROOT/configure-tailscale.sh"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "WARN: copy .env.example to .env and configure before first boot."
fi

cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${ROOT}/scripts/bridge-service.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>StandardOutPath</key>
  <string>${ROOT}/logs/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${ROOT}/logs/launchd.err.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>HOME</key>
    <string>${HOME}</string>
  </dict>
</dict>
</plist>
EOF

launchctl bootout "${GUI_DOMAIN}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "$GUI_DOMAIN" "$PLIST_DEST"
launchctl enable "${GUI_DOMAIN}/${LABEL}" 2>/dev/null || true
launchctl kickstart -k "${GUI_DOMAIN}/${LABEL}" 2>/dev/null || launchctl start "$LABEL" 2>/dev/null || true

echo "Installed LaunchAgent: $PLIST_DEST"
echo "Logs: $ROOT/logs/"
