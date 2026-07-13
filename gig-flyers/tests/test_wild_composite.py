"""Tests for wild D PIL composite (H3)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import GigEvent  # noqa: E402
from wild_design.composite import render_wild_composite_poster  # noqa: E402
from wild_design.metrics import score_output  # noqa: E402

REF = ROOT / "bandphotos" / "475779793_1030489528887965_3935557413007700748_n.jpg"


class WildCompositeTests(unittest.TestCase):
    def test_render_passes_compose_validation(self) -> None:
        if not REF.is_file():
            self.skipTest("reference band photo missing")
        event = GigEvent(
            event_date=date(2026, 6, 28),
            time_label="7:00 PM",
            title="Lindsey Lane Band",
            venue="Two Lane Tavern",
            suggested_name="Jun 28 Two Lane Tavern",
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "wild_d.png"
            meta = render_wild_composite_poster(event, REF, out, tier="creative", seed=99)
            self.assertTrue(out.is_file())
            metrics = score_output(
                "test",
                out,
                REF,
                elapsed_sec=0.0,
                compose=meta["compose"],
            )
            self.assertTrue(metrics.compose_validation_passed)
            self.assertGreater(metrics.band_hist_correlation, 0.3)


if __name__ == "__main__":
    unittest.main()
