"""Read deploy build metadata written at image build time."""

from __future__ import annotations

import json
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

_BUILD_INFO_PATHS = (
    Path("/app/build-info.json"),
    Path(__file__).resolve().parents[1] / "build-info.json",
)


@lru_cache(maxsize=1)
def load_build_info() -> dict[str, str]:
    for path in _BUILD_INFO_PATHS:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
            except (OSError, json.JSONDecodeError, TypeError):
                pass
    sha = (os.environ.get("BANDTOOLS_GIT_SHA") or "dev").strip()
    short = sha[:7]
    build_number = (os.environ.get("BANDTOOLS_BUILD_NUMBER") or "dev").strip()
    built_at = (os.environ.get("BANDTOOLS_BUILD_TIME") or "").strip()
    if not built_at:
        built_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    deploy_env = (os.environ.get("BANDTOOLS_DEPLOY_ENV") or "local").strip()
    return {
        "git_sha": sha,
        "git_sha_short": short,
        "build_number": build_number,
        "built_at": built_at,
        "deploy_env": deploy_env,
        "label": f"{build_number}-{short}",
    }


def build_info_for_api() -> dict[str, Any]:
    return dict(load_build_info())
