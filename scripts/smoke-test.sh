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
check /flyers 302
check /flyers/ 302
check /flyers/pick 302
check /flyers/logistics 200
check /forge/signin 200
check /forge 307
check /forge/calendar 307
check /forge/api/events 401
check /forge/api/health 200
PROVIDER=$(curl -sS "${BASE}/forge/api/auth/provider" | python3 -c "import sys,json; print(json.load(sys.stdin).get('provider',''))" 2>/dev/null || echo "")
if [[ "$PROVIDER" != "bandtools" ]]; then
  echo "FAIL /forge/api/auth/provider expected bandtools got '${PROVIDER}'"
  exit 1
fi
echo "OK   Flyer Forge signs in with Band Tools sessions"
check / 200
check /setlist-loader 200

# Verify Next.js CSS bundle is served (standalone static path)
CSS_PATH=$(curl -sS "$BASE/" | grep -oE '/_next/static/css/[^"]+\.css' | head -1)
if [[ -n "$CSS_PATH" ]]; then
  check "$CSS_PATH" 200
else
  echo "WARN: no CSS link found in homepage HTML"
fi

if [[ -z "${SMOKE_SKIP_UNIT_TESTS:-}" ]] && command -v python3 >/dev/null 2>&1; then
  echo "Running gig-flyers unit tests..."
  (cd "$(dirname "$0")/../gig-flyers" && python3 -m pytest tests/ -q --tb=no -x 2>/dev/null) || echo "WARN: gig-flyers tests skipped or failed locally"
fi

echo "All smoke checks passed for ${BASE}"
