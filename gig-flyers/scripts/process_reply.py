#!/usr/bin/env python3
"""Manually process a flyer reply via API (iMessage text or web-equivalent)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge.imessage import parse_reply  # noqa: E402

load_dotenv(ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description="Process flyer reply manually")
    parser.add_argument("reply", nargs="?", help='e.g. "APPROVE B" or "REVISE A: bigger venue"')
    parser.add_argument("--gig", default="2026-07-14_stevie-ray-s-blues-bar")
    parser.add_argument("--web", action="store_true", help="Use web review JSON endpoints")
    args = parser.parse_args()

    port = os.getenv("BRIDGE_PORT", "8010")
    base = f"http://127.0.0.1:{port}"

    if args.web and not args.reply:
        print("Open review page in browser or pass a reply string.")
        print(f"{base}/review/{args.gig}")
        return 0

    if not args.reply:
        parser.print_help()
        return 1

    parsed = parse_reply(args.reply)
    if parsed.action == "unknown":
        print("Could not parse reply. Use APPROVE B or REVISE B: feedback")
        return 1

    if args.web:
        if parsed.action == "approve":
            resp = httpx.post(
                f"{base}/review/{args.gig}/approve.json",
                json={"option": parsed.option},
                timeout=300,
            )
        else:
            resp = httpx.post(
                f"{base}/review/{args.gig}/revise.json",
                json={"option": parsed.option, "feedback": parsed.feedback},
                timeout=300,
            )
    else:
        secret = os.getenv("BRIDGE_SECRET", "")
        payload = {
            "feedback": {
                "gig_id": args.gig,
                "action": parsed.action,
                "option": parsed.option,
                "feedback": parsed.feedback,
                "raw_text": parsed.raw_text,
                "rowid": 9_999_999,
            }
        }
        resp = httpx.post(
            f"{base}/process-feedback",
            json=payload,
            headers={"X-Secret": secret, "Content-Type": "application/json"},
            timeout=300,
        )

    print(resp.status_code)
    print(json.dumps(resp.json(), indent=2))
    return 0 if resp.is_success else 1


if __name__ == "__main__":
    sys.exit(main())
