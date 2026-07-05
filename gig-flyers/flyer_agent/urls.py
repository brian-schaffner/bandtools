"""URL helpers for Flyer Agent assets."""

from __future__ import annotations

from urllib.parse import quote

from bridge.review import asset_url


def flyer_asset_url(path: str, *, round_num: int = 0, updated_at: str = "") -> str:
    """Return a cache-busted asset URL for flyer previews."""
    base = asset_url(path)
    stamp = quote((updated_at or str(round_num))[:32], safe="")
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}v={int(round_num)}&t={stamp}"
