#!/usr/bin/env python3
"""Periodic design research for the Flyer Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flyer_agent.agent import FlyerAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh Flyer Agent design research cache")
    parser.add_argument("--llm", action="store_true", help="Include optional LLM design scan")
    parser.add_argument("--sync-catalog", action="store_true", help="Import approved flyers into catalog")
    args = parser.parse_args()

    agent = FlyerAgent()
    result = agent.refresh_research(use_llm=args.llm)
    if args.sync_catalog:
        added = agent.sync_catalog_from_approvals()
        result["catalog_added"] = added
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
