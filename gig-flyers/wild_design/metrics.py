"""Scoring helpers for wild-D band photo experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

from image_providers.reference_compose import (
    ComposeResult,
    validate_flyer_photo,
)


@dataclass
class WildBandMetrics:
    hypothesis: str
    output_path: str
    band_hist_correlation: float
    band_mse: float
    compose_validation_passed: Optional[bool]
    compose_checks: list[dict[str, Any]]
    elapsed_sec: float
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _center_photo_region(size: tuple[int, int]) -> tuple[int, int, int, int]:
    w, h = size
    cw = int(w * 0.78)
    ch = int(h * 0.42)
    left = (w - cw) // 2
    top = int(h * 0.26)
    return left, top, left + cw, top + ch


def band_region_similarity(
    poster_path: Path,
    reference_path: Path,
    *,
    region: Optional[tuple[int, int, int, int]] = None,
) -> tuple[float, float]:
    """Return (histogram_correlation, mse) for band region vs reference."""
    poster = Image.open(poster_path).convert("RGB")
    ref = Image.open(reference_path).convert("RGB")
    if region is None:
      region = _center_photo_region(poster.size)
    left, top, right, bottom = region
    crop = poster.crop((left, top, right, bottom))
    ref_fit = ref.resize(crop.size, Image.Resampling.LANCZOS)

    a = np.asarray(crop, dtype=np.float32)
    b = np.asarray(ref_fit, dtype=np.float32)
    mse = float(np.mean((a - b) ** 2))

    corrs: list[float] = []
    for ch in range(3):
      ha, _ = np.histogram(a[:, :, ch], bins=32, range=(0, 255), density=True)
      hb, _ = np.histogram(b[:, :, ch], bins=32, range=(0, 255), density=True)
      if ha.std() == 0 or hb.std() == 0:
        corrs.append(0.0)
      else:
        corrs.append(float(np.corrcoef(ha, hb)[0, 1]))
    return float(np.mean(corrs)), mse


def score_output(
    hypothesis: str,
    poster_path: Path,
    reference_path: Path,
    *,
    elapsed_sec: float,
    compose: Optional[ComposeResult] = None,
    notes: str = "",
) -> WildBandMetrics:
    region = compose.photo_bbox if compose else None
    corr, mse = band_region_similarity(poster_path, reference_path, region=region)
    compose_passed: Optional[bool] = None
    checks: list[dict[str, Any]] = []
    if compose is not None:
      result = validate_flyer_photo(poster_path, reference_path, compose)
      compose_passed = result.passed
      checks = result.checks
    return WildBandMetrics(
      hypothesis=hypothesis,
      output_path=str(poster_path),
      band_hist_correlation=round(corr, 4),
      band_mse=round(mse, 2),
      compose_validation_passed=compose_passed,
      compose_checks=checks,
      elapsed_sec=round(elapsed_sec, 2),
      notes=notes,
    )
