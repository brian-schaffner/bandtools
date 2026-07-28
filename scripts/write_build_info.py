#!/usr/bin/env python3
"""Write /app/build-info.json from deploy-time environment variables."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def build_info_payload() -> dict[str, str]:
    sha = (os.environ.get("BANDTOOLS_GIT_SHA") or "unknown").strip()
    short = sha[:7] if sha != "unknown" else "unknown"
    build_number = (os.environ.get("BANDTOOLS_BUILD_NUMBER") or "dev").strip()
    built_at = (os.environ.get("BANDTOOLS_BUILD_TIME") or "").strip()
    if not built_at:
        built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    deploy_env = (os.environ.get("BANDTOOLS_DEPLOY_ENV") or "local").strip()
    label = f"{build_number}-{short}"
    return {
        "git_sha": sha,
        "git_sha_short": short,
        "build_number": build_number,
        "built_at": built_at,
        "deploy_env": deploy_env,
        "label": label,
    }


def main() -> None:
    data = build_info_payload()
    out = Path(os.environ.get("BANDTOOLS_BUILD_INFO_PATH", "/app/build-info.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote build info {data['label']} -> {out}")


if __name__ == "__main__":
    main()
