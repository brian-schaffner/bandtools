"""Rolling average timing for per-option generation progress estimates."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
TIMING_PATH = ROOT / "cache" / "gen_timing.json"

DEFAULT_OPTION_SECONDS = 45.0
DEFAULT_GENERATE_SECONDS = 30.0
DEFAULT_REVIEW_SECONDS = 15.0
MIN_GENERATE_ESTIMATE_SECONDS = 25.0
MIN_RECORD_GENERATE_SECONDS = 15.0
MAX_SAMPLES = 50
MAX_RECENT = 50
MIN_BUCKET_SAMPLES = 3
EMA_ALPHA = 0.2

OPTION_TIER_BY_LETTER = {"A": "conservative", "B": "medium", "C": "creative"}

_lock = threading.Lock()


def tier_for_option(letter: str) -> str:
    return OPTION_TIER_BY_LETTER.get((letter or "").upper(), "medium")


def quality_for_tier(tier: str, *, use_reference: bool = True) -> str:
    """OpenAI quality per creativity tier (conservative saves cost, creative gets detail)."""
    if use_reference:
        ref_quality = os.getenv("OPENAI_IMAGE_QUALITY_REFERENCE", "high").strip().lower()
        if ref_quality:
            return ref_quality
    explicit = os.getenv(f"OPENAI_IMAGE_QUALITY_{tier.upper()}", "").strip().lower()
    if explicit:
        return explicit
    defaults = {"conservative": "medium", "medium": "medium", "creative": "high"}
    return defaults.get(tier, os.getenv("OPENAI_IMAGE_QUALITY", "medium").strip().lower() or "medium")


def _bucket_key(provider: str, quality: str, tier: str) -> str:
    return f"{provider}:{quality}:{tier}"


def _default_data() -> dict[str, Any]:
    return {
        "option_total_seconds": DEFAULT_OPTION_SECONDS,
        "generate_seconds": DEFAULT_GENERATE_SECONDS,
        "review_seconds": DEFAULT_REVIEW_SECONDS,
        "samples": 0,
        "buckets": {},
    }


def _load_unlocked() -> dict[str, Any]:
    if not TIMING_PATH.is_file():
        return _default_data()
    try:
        raw = json.loads(TIMING_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_data()
    if not isinstance(raw, dict):
        return _default_data()
    merged = _default_data()
    merged.update({k: raw[k] for k in merged if k in raw})
    if isinstance(raw.get("buckets"), dict):
        merged["buckets"] = raw["buckets"]
    return merged


def _save_unlocked(data: dict[str, Any]) -> None:
    TIMING_PATH.parent.mkdir(parents=True, exist_ok=True)
    TIMING_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _clamp_generate_estimate(seconds: float) -> float:
    return max(MIN_GENERATE_ESTIMATE_SECONDS, float(seconds))


def _usable_recent(values: list[float]) -> list[float]:
    return [float(v) for v in values if float(v) >= MIN_RECORD_GENERATE_SECONDS]


def _p75(values: list[float]) -> float:
    usable = _usable_recent(values)
    if not usable:
        return _clamp_generate_estimate(DEFAULT_GENERATE_SECONDS)
    ordered = sorted(usable)
    idx = int(0.75 * (len(ordered) - 1))
    return _clamp_generate_estimate(ordered[idx])


def _collect_recent_for_prefix(buckets: dict[str, Any], prefix: str) -> list[float]:
    recent: list[float] = []
    for key, bucket in buckets.items():
        if not isinstance(bucket, dict):
            continue
        if not str(key).startswith(prefix):
            continue
        for value in bucket.get("recent", []):
            recent.append(float(value))
    return recent


def _get_or_create_bucket(data: dict[str, Any], key: str) -> dict[str, Any]:
    buckets = data.setdefault("buckets", {})
    if key not in buckets or not isinstance(buckets[key], dict):
        buckets[key] = {
            "samples": 0,
            "ema": DEFAULT_GENERATE_SECONDS,
            "recent": [],
        }
    return buckets[key]


def _best_bucket_generate_estimate(buckets: dict[str, Any]) -> Optional[float]:
    estimates: list[float] = []
    for bucket in buckets.values():
        if not isinstance(bucket, dict):
            continue
        recent = _usable_recent(list(bucket.get("recent", [])))
        if recent:
            estimates.append(_p75(recent))
    if not estimates:
        return None
    return max(estimates)


def get_estimates() -> dict[str, float]:
    with _lock:
        data = _load_unlocked()
    buckets = data.get("buckets", {})
    if not isinstance(buckets, dict):
        buckets = {}
    generate_seconds = float(data.get("generate_seconds", DEFAULT_GENERATE_SECONDS))
    if int(data.get("samples", 0)) <= 0:
        bucket_estimate = _best_bucket_generate_estimate(buckets)
        if bucket_estimate is not None:
            generate_seconds = bucket_estimate
    return {
        "option_total_seconds": float(data.get("option_total_seconds", DEFAULT_OPTION_SECONDS)),
        "generate_seconds": _clamp_generate_estimate(generate_seconds),
        "review_seconds": float(data.get("review_seconds", DEFAULT_REVIEW_SECONDS)),
    }


def get_generate_estimate(provider: str, quality: str, tier: str) -> float:
    """Return p75 generate estimate with bucket fallback chain."""
    provider = (provider or "openai").strip().lower()
    quality = (quality or "medium").strip().lower()
    tier = (tier or "medium").strip().lower()

    with _lock:
        data = _load_unlocked()
        buckets = data.get("buckets", {})
        if not isinstance(buckets, dict):
            buckets = {}

        exact = _bucket_key(provider, quality, tier)
        exact_bucket = buckets.get(exact)
        if isinstance(exact_bucket, dict):
            exact_recent = _usable_recent(list(exact_bucket.get("recent", [])))
            if exact_recent:
                return _p75(exact_recent)

        pq_recent = _usable_recent(
            _collect_recent_for_prefix(buckets, f"{provider}:{quality}:")
        )
        if len(pq_recent) >= MIN_BUCKET_SAMPLES:
            return _p75(pq_recent)

        provider_recent = _usable_recent(_collect_recent_for_prefix(buckets, f"{provider}:"))
        if len(provider_recent) >= MIN_BUCKET_SAMPLES:
            return _p75(provider_recent)

        return _clamp_generate_estimate(
            float(data.get("generate_seconds", DEFAULT_GENERATE_SECONDS))
        )


def record_generate_timing(
    generate_seconds: float,
    *,
    provider: str,
    quality: str,
    tier: str,
) -> None:
    """Update bucketed EMA + recent samples after a successful image generate."""
    generate_seconds = float(generate_seconds)
    if generate_seconds < MIN_RECORD_GENERATE_SECONDS:
        return
    provider = (provider or "openai").strip().lower()
    quality = (quality or "medium").strip().lower()
    tier = (tier or "medium").strip().lower()
    key = _bucket_key(provider, quality, tier)

    with _lock:
        data = _load_unlocked()
        bucket = _get_or_create_bucket(data, key)
        samples = int(bucket.get("samples", 0))
        prev_ema = float(bucket.get("ema", DEFAULT_GENERATE_SECONDS))
        if samples <= 0:
            bucket["ema"] = generate_seconds
        else:
            bucket["ema"] = EMA_ALPHA * generate_seconds + (1.0 - EMA_ALPHA) * prev_ema
        recent = bucket.setdefault("recent", [])
        if not isinstance(recent, list):
            recent = []
            bucket["recent"] = recent
        recent.append(generate_seconds)
        if len(recent) > MAX_RECENT:
            bucket["recent"] = recent[-MAX_RECENT:]
        bucket["samples"] = samples + 1

        global_samples = int(data.get("samples", 0))
        prev_global = float(data.get("generate_seconds", DEFAULT_GENERATE_SECONDS))
        if global_samples <= 0:
            data["generate_seconds"] = generate_seconds
        else:
            weight = min(global_samples, MAX_SAMPLES)
            data["generate_seconds"] = (prev_global * weight + generate_seconds) / (weight + 1)
        data["samples"] = global_samples + 1
        _save_unlocked(data)


def record_review_timing(review_seconds: float, generate_seconds: Optional[float] = None) -> None:
    """Update rolling review + option totals after an option completes review."""
    review_seconds = max(0.5, float(review_seconds))
    generate_seconds = max(1.0, float(generate_seconds or DEFAULT_GENERATE_SECONDS))
    total = generate_seconds + review_seconds

    with _lock:
        data = _load_unlocked()
        samples = int(data.get("samples", 0))

        def _roll(key: str, value: float) -> float:
            prev = float(data.get(key, value))
            if samples <= 0:
                return value
            weight = min(samples, MAX_SAMPLES)
            return (prev * weight + value) / (weight + 1)

        data["review_seconds"] = _roll("review_seconds", review_seconds)
        data["option_total_seconds"] = _roll("option_total_seconds", total)
        _save_unlocked(data)


def record_option_timing(generate_seconds: float, review_seconds: float) -> None:
    """Backward-compatible wrapper: record generate globally + review totals."""
    record_generate_timing(
        generate_seconds,
        provider="openai",
        quality="medium",
        tier="medium",
    )
    record_review_timing(review_seconds, generate_seconds=generate_seconds)


def reset_timing_cache() -> None:
    """Test helper."""
    with _lock:
        if TIMING_PATH.is_file():
            TIMING_PATH.unlink()
