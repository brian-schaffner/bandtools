#!/usr/bin/env python3
"""Tests for monotonic vessel fill progress (mirrors bridge/review.py JS)."""

from __future__ import annotations

import unittest


def effective_estimate(base_estimate: float, elapsed_sec: float, *, fill_duration: float = 45.0) -> float:
    base = max(1.0, base_estimate or fill_duration)
    if elapsed_sec <= base:
        return base
    overdue = elapsed_sec - base
    stretches = int(overdue // 5) + 1
    return base * (1 + 0.1 * stretches)


def compute_fill_ratio(elapsed_sec: float, estimate_sec: float, *, fill_duration: float = 45.0) -> float:
    eff = effective_estimate(estimate_sec, elapsed_sec, fill_duration=fill_duration)
    return min(0.95, elapsed_sec / eff)


def monotonic_fill_ratio(
    elapsed_sec: float,
    estimate_sec: float,
    *,
    max_progress: float = 0.0,
    fill_duration: float = 45.0,
) -> tuple[float, float]:
    computed = compute_fill_ratio(elapsed_sec, estimate_sec, fill_duration=fill_duration)
    ratio = max(max_progress, computed)
    return ratio, ratio


class FillProgressMonotonicTest(unittest.TestCase):
    def test_stretch_logic_dips_without_max_progress(self) -> None:
        """Overdue stretch increases effective estimate and can lower raw ratio past 95%."""
        estimate = 45.0
        at_deadline = compute_fill_ratio(45.0, estimate)
        self.assertAlmostEqual(at_deadline, 0.95)
        after_stretch = compute_fill_ratio(46.0, estimate)
        self.assertLess(after_stretch, at_deadline)

    def test_max_progress_prevents_dip_past_cap(self) -> None:
        estimate = 45.0
        max_p = 0.0
        samples: list[float] = []
        for elapsed in range(0, 120):
            ratio, max_p = monotonic_fill_ratio(float(elapsed), estimate, max_progress=max_p)
            samples.append(ratio)
        for prev, cur in zip(samples, samples[1:]):
            self.assertGreaterEqual(cur, prev - 1e-9)

    def test_max_progress_holds_at_cap_until_review(self) -> None:
        estimate = 30.0
        max_p = 0.0
        for elapsed in range(0, 200):
            ratio, max_p = monotonic_fill_ratio(float(elapsed), estimate, max_progress=max_p)
        self.assertAlmostEqual(max_p, 0.95)

    def test_new_attempt_resets_max_progress(self) -> None:
        _, max_p = monotonic_fill_ratio(60.0, 45.0, max_progress=0.0)
        self.assertGreater(max_p, 0.9)
        fresh_ratio, fresh_max = monotonic_fill_ratio(1.0, 45.0, max_progress=0.0)
        self.assertLess(fresh_ratio, 0.1)
        self.assertLess(fresh_max, 0.1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
