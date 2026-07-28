"""Deploy build metadata for health checks and UI stamps."""

from __future__ import annotations

import html
import json
import os
import subprocess
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILD_INFO_CANDIDATES = (
    Path("/app/build-info.json"),
    _REPO_ROOT / "build-info.json",
)


def _git_short_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


@lru_cache(maxsize=1)
def get_build_info() -> dict[str, str]:
    for path in _BUILD_INFO_CANDIDATES:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
            except (OSError, json.JSONDecodeError, TypeError):
                pass

    sha = (os.environ.get("BANDTOOLS_GIT_SHA") or "").strip()
    if not sha:
        sha = _git_short_sha() or "dev"
    short = sha[:7] if len(sha) > 7 else sha
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
    return dict(get_build_info())


def _format_built_at(iso: str) -> str:
    raw = (iso or "").strip()
    if not raw:
        return ""
    try:
        normalized = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return raw


def build_stamp_text() -> str:
    info = get_build_info()
    when = _format_built_at(info.get("built_at", ""))
    env = info.get("deploy_env", "")
    env_bit = f" · {env}" if env and env != "local" else ""
    return f"Build {info.get('label', '?')}{env_bit} · {when}"


def build_stamp_html(*, title: str | None = None) -> str:
    info = get_build_info()
    text = build_stamp_text()
    tip = title or (
        f"git {info.get('git_sha', '')} · built {info.get('built_at', '')} "
        f"· #{info.get('build_number', '')}"
    )
    return (
        f'<footer class="site-build-stamp" title="{html.escape(tip)}">'
        f"{html.escape(text)}</footer>"
    )
