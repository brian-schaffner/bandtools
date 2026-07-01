#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Tailscale phone access checklist"
echo "================================="
echo ""

if ! command -v tailscale >/dev/null 2>&1; then
  echo "Tailscale CLI not found on this Mac."
  exit 1
fi

TAILNET_HOST="$(tailscale status --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['Self']['DNSName'].rstrip('.'))
")"
TAILNET_IP="$(tailscale ip -4 | head -1)"

echo "Mac tailnet name: https://${TAILNET_HOST}/"
echo "Mac tailnet IP:   ${TAILNET_IP}"
echo ""

echo "Devices on your tailnet:"
tailscale status --json | python3 -c "
import json, sys
data = json.load(sys.stdin)
peers = data.get('Peer', {})
ios = [p for p in peers.values() if (p.get('OS') or '').lower().startswith('ios')]
online = [p for p in peers.values() if p.get('Online')]
print(f'  Total peers: {len(peers)}')
print(f'  Online peers: {len(online)}')
print(f'  iOS devices: {len(ios)}')
for p in ios:
    name = p.get('HostName', '?')
    dns = p.get('DNSName', '?').rstrip('.')
    state = 'online' if p.get('Online') else 'offline'
    print(f'    - {name} ({dns}) [{state}]')
if not ios:
    print('  *** No iPhone/iPad found on this tailnet ***')
    print('      Install Tailscale on your phone and sign in as brian@schaffner.net')
"

echo ""
echo "Serve config:"
tailscale serve status 2>/dev/null || echo "  (not configured)"
echo ""

echo "Local services:"
for port in 3002 8002; do
  code="$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 "http://127.0.0.1:${port}/" 2>/dev/null || echo 'down')"
  echo "  127.0.0.1:${port} -> ${code}"
done
code="$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 "http://127.0.0.1:8002/health" 2>/dev/null || echo 'down')"
echo "  127.0.0.1:8002/health -> ${code}"
echo ""

echo "On your iPhone, verify:"
echo "  1. Tailscale app installed and signed in as brian@schaffner.net"
echo "  2. Tailscale toggle is ON (connected) before opening Safari"
echo "  3. Tailscale app -> Settings -> DNS -> 'Use Tailscale DNS Settings' ON"
echo "  4. Tailscale app -> Settings -> VPN On Demand -> 'Detect MagicDNS hostnames' ON"
echo "  5. iOS Settings -> VPN -> Tailscale should show 'Connected'"
echo ""
echo "Then open in Safari:"
echo "  https://${TAILNET_HOST}/"
echo ""
echo "If MagicDNS still fails, try this fallback (HTTP, tailnet IP only):"
echo "  http://${TAILNET_IP}:3002"
echo "  (requires ./start-tailscale-direct.sh and Tailscale connected on phone)"
echo ""
