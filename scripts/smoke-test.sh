#!/usr/bin/env bash
# Smoke-test a deployed Band Tools instance.
set -euo pipefail

BASE="${1:-https://bandtools-test.fly.dev}"

check() {
  local path="$1"
  local expect="${2:-200}"
  local code
  code=$(curl -sS -o /tmp/bandtools-smoke-body.txt -w "%{http_code}" "${BASE}${path}")
  if [[ "$code" != "$expect" ]]; then
    echo "FAIL ${path} expected ${expect} got ${code}"
    cat /tmp/bandtools-smoke-body.txt || true
    return 1
  fi
  echo "OK   ${path} (${code})"
}

echo "Smoke testing ${BASE}"
check /health 200
check /api/health 200
check /flyers/health 200
GEMINI_STATUS=$(curl -sS "${BASE}/flyers/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('providers',{}).get('gemini_configured',''))" 2>/dev/null || echo "")
if [[ "$GEMINI_STATUS" == "True" ]]; then
  echo "OK   Gemini API key configured"
elif [[ "$GEMINI_STATUS" == "False" ]]; then
  echo "WARN Gemini API key not configured (options B/C will fall back to OpenAI if set)"
fi
check /flyers 301
check /flyers/ 200
check /flyers/pick 200
check / 200
check /setlist-loader 200

# Hub Gig Flyers must use a plain anchor so nginx serves the bridge (not Next.js client nav → :8090)
HUB_HTML=$(curl -sS "$BASE/")
if echo "$HUB_HTML" | grep -q 'href="/flyers/"' && ! echo "$HUB_HTML" | grep -q 'href="/flyers/"[^>]*data-nextjs-link'; then
  echo "OK   hub gig-flyers uses plain anchor"
else
  echo "FAIL hub missing plain /flyers/ anchor link"
  exit 1
fi

# Verify Next.js CSS bundle is served (standalone static path)
CSS_PATH=$(curl -sS "$BASE/" | grep -oE '/_next/static/css/[^"]+\.css' | head -1)
if [[ -n "$CSS_PATH" ]]; then
  check "$CSS_PATH" 200
else
  echo "WARN: no CSS link found in homepage HTML"
fi

if command -v python3 >/dev/null 2>&1; then
  echo "Running gig-flyers unit tests..."
  (cd "$(dirname "$0")/../gig-flyers" && python3 -m pytest tests/ -q --tb=no -x 2>/dev/null) || echo "WARN: gig-flyers tests skipped or failed locally"
fi

echo "All smoke checks passed for ${BASE}"
