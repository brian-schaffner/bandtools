#!/usr/bin/env bash
# Install SetLoader + Tailscale Serve as a macOS LaunchAgent (starts at login).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.setloader.services"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
GUI_DOMAIN="gui/$(id -u)"

echo "SetLoader autostart installer"
echo "=============================="
echo "Project: $ROOT"
echo ""

if ! command -v tailscale >/dev/null 2>&1; then
  echo "ERROR: tailscale CLI not found. Install from https://tailscale.com/download"
  exit 1
fi

if [[ ! -f "$ROOT/.env" ]]; then
  echo "WARN: $ROOT/.env not found — copy from .env.example or create before first boot."
fi

mkdir -p "$ROOT/logs"
chmod +x "$ROOT/scripts/setloader-service.sh"
chmod +x "$ROOT/configure-tailscale.sh"

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
    <string>${ROOT}/scripts/setloader-service.sh</string>
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

echo "Installed LaunchAgent: $PLIST_DEST"

launchctl bootout "${GUI_DOMAIN}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "$GUI_DOMAIN" "$PLIST_DEST"
launchctl enable "${GUI_DOMAIN}/${LABEL}" 2>/dev/null || true
launchctl kickstart -k "${GUI_DOMAIN}/${LABEL}" 2>/dev/null || launchctl start "$LABEL" 2>/dev/null || true

echo ""
echo "Done. SetLoader will start automatically when you log in."
echo ""
echo "Tailscale:"
echo "  In the Tailscale app → Settings, enable 'Start Tailscale at login'"
echo "  (The service script also opens Tailscale and waits if it is not up yet.)"
echo ""
echo "URLs (after startup):"
if tailscale status >/dev/null 2>&1; then
  HOST="$(tailscale status --json | python3 -c "import json,sys; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))")"
  echo "  https://${HOST}/"
else
  echo "  https://<your-machine>.<tailnet>.ts.net/"
fi
echo "  http://localhost:${FRONTEND_PORT:-3002}/"
echo ""
echo "Logs: $ROOT/logs/"
echo "Stop autostart:  ./uninstall-autostart.sh"
echo "Manual service:  ./scripts/setloader-service.sh"
