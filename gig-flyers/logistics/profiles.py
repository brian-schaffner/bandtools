"""Venue profiles and timing defaults for performance-day logistics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from html import unescape
from pathlib import Path
from typing import Any, Optional

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "venues.yaml"

TIMING_KEYS = (
    "setup_minutes",
    "soundcheck_minutes",
    "final_adjustments_minutes",
    "dead_stage_minutes",
    "travel_cushion_minutes",
    "teardown_minutes",
    "gig_length_minutes",
    "unknown_drive_minutes",
)


@dataclass(frozen=True)
class VenueProfile:
    key: str
    name: str
    timing: dict[str, int]
    match: tuple[str, ...] = ()
    address: str = ""
    header: str = ""
    location: str = ""
    drive_minutes: Optional[int] = None
    drive_source: str = ""
    include_return: bool = False
    setup_label: str = ""
    setup_bullets: tuple[str, ...] = ()
    soundcheck_bullets: tuple[str, ...] = ()
    adjustments_label: str = ""
    notes: tuple[str, ...] = ()
    timeline: tuple[dict[str, Any], ...] = ()
    known: bool = True

    def minutes(self, key: str) -> int:
        return int(self.timing[key])


@dataclass(frozen=True)
class LogisticsConfig:
    defaults: dict[str, int]
    venues: tuple[VenueProfile, ...]
    exclude_title_patterns: tuple[str, ...] = field(default_factory=tuple)

    def is_excluded(self, title: str) -> bool:
        text = unescape(title or "")
        return any(re.search(p, text, re.I) for p in self.exclude_title_patterns)

    def match_venue(self, title: str) -> Optional[VenueProfile]:
        text = _normalize(title)
        for venue in self.venues:
            if any(_normalize(m) in text for m in venue.match):
                return venue
        return None

    def profile_for(self, title: str, fallback_name: str, address: str = "") -> VenueProfile:
        found = self.match_venue(title)
        if found:
            return found
        return VenueProfile(
            key="unknown",
            name=fallback_name or title,
            timing=dict(self.defaults),
            address=address,
            known=False,
        )

    def defaults_profile(self, base: VenueProfile) -> VenueProfile:
        """Same venue identity and drive time, but default timing and layout (cold-start prediction)."""
        return VenueProfile(
            key=base.key,
            name=base.name,
            timing=dict(self.defaults),
            match=base.match,
            address=base.address,
            drive_minutes=base.drive_minutes,
            drive_source=base.drive_source,
            known=False,
        )


def _normalize(text: str) -> str:
    text = unescape(text or "").lower().replace("’", "'")
    return re.sub(r"\s+", " ", text)


def _venue_from_dict(key: str, raw: dict[str, Any], defaults: dict[str, int]) -> VenueProfile:
    timing = dict(defaults)
    for timing_key in TIMING_KEYS:
        if timing_key in raw:
            timing[timing_key] = int(raw[timing_key])
    return VenueProfile(
        key=key,
        name=raw.get("name", key),
        timing=timing,
        match=tuple(raw.get("match") or (raw.get("name", key),)),
        address=raw.get("address", ""),
        header=raw.get("header", ""),
        location=raw.get("location", ""),
        drive_minutes=int(raw["drive_minutes"]) if raw.get("drive_minutes") is not None else None,
        drive_source=raw.get("drive_source", ""),
        include_return=bool(raw.get("include_return", False)),
        setup_label=raw.get("setup_label", ""),
        setup_bullets=tuple(raw.get("setup_bullets") or ()),
        soundcheck_bullets=tuple(raw.get("soundcheck_bullets") or ()),
        adjustments_label=raw.get("adjustments_label", ""),
        notes=tuple(raw.get("notes") or ()),
        timeline=tuple(raw.get("timeline") or ()),
    )


def load_config(path: Optional[Path] = None) -> LogisticsConfig:
    return _load_config_cached(str(path or DEFAULT_CONFIG_PATH))


@lru_cache(maxsize=8)
def _load_config_cached(path: str) -> LogisticsConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    defaults = {k: int(v) for k, v in (data.get("defaults") or {}).items()}
    missing = [k for k in TIMING_KEYS if k not in defaults]
    if missing:
        raise ValueError(f"venues.yaml defaults missing: {', '.join(missing)}")
    venues = tuple(
        _venue_from_dict(key, raw or {}, defaults) for key, raw in (data.get("venues") or {}).items()
    )
    return LogisticsConfig(
        defaults=defaults,
        venues=venues,
        exclude_title_patterns=tuple(data.get("exclude_title_patterns") or ()),
    )
