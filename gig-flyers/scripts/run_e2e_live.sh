#!/usr/bin/env bash
# End-to-end smoke test. Use --test when lindseylane.com is unreachable.
set -euo pipefail
cd "$(dirname "$0")/.."

TEST_MODE=0
if [[ "${1:-}" == "--test" ]]; then
  TEST_MODE=1
  shift
fi

source .venv/bin/activate 2>/dev/null || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }

set -a
# shellcheck disable=SC1091
[[ -f .env ]] && source .env
set +a

TEST_FLAG=()
if [[ "$TEST_MODE" == "1" ]]; then
  export GIG_FLYERS_TEST_MODE=1
  TEST_FLAG=(--test)
  echo "== Test mode: using fixtures/mock_gigs.json =="
fi

echo "== Scan =="
python3 flyer_generator.py "${TEST_FLAG[@]}" --scan

GIG_ID="$(python3 flyer_generator.py "${TEST_FLAG[@]}" --scan | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['needs_generation'][0] if d.get('needs_generation') else '')")"
if [[ -z "$GIG_ID" ]]; then
  echo "No gigs in 21-28 day window. Trying first upcoming gig with --min-days 0..."
  GIG_ID="$(python3 - <<PY
from gig_calendar import get_all_events, get_local_today, set_test_mode
import os
if os.getenv("GIG_FLYERS_TEST_MODE"):
    set_test_mode(True)
today = get_local_today()
for e in get_all_events(force_refresh=True):
    if e.event_date >= today:
        print(e.gig_id)
        break
PY
)"
fi

if [[ -z "$GIG_ID" ]]; then
  echo "No upcoming gigs found."
  exit 1
fi

echo "== Generate dry-run for $GIG_ID =="
python3 flyer_generator.py "${TEST_FLAG[@]}" --gig "$GIG_ID" --count 3 --dry-run

if [[ -n "${OPENAI_API_KEY:-}" && "$TEST_MODE" != "1" ]]; then
  echo "== Generate live for $GIG_ID =="
  python3 flyer_generator.py --gig "$GIG_ID" --count 3
elif [[ -n "${OPENAI_API_KEY:-}" && "$TEST_MODE" == "1" ]]; then
  echo "== Skipping live OpenAI generation in --test mode (use without --test when site is up) =="
fi

echo "== Bridge health =="
curl -sS "http://127.0.0.1:${BRIDGE_PORT:-8010}/health" 2>/dev/null || echo "Start bridge: ./scripts/bridge-service.sh"

echo "Done."
