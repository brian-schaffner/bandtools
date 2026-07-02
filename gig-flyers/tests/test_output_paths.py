"""Tests for output path helpers when GIG_OUTPUT_DIR is external."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from output_paths import OUTPUT_PREFIX, get_output_dir, output_relative, resolve_output_path


class OutputPathsTests(unittest.TestCase):
    def test_default_output_dir(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GIG_OUTPUT_DIR", None)
            self.assertEqual(get_output_dir(), Path(__file__).resolve().parents[1] / OUTPUT_PREFIX)

    def test_external_output_dir_round_trip(self) -> None:
        with patch.dict(os.environ, {"GIG_OUTPUT_DIR": "/data/flyers-output"}):
            abs_path = Path("/data/flyers-output/2026-07-04_gig/prototype/prototype_r1_1.png")
            rel = output_relative(abs_path)
            self.assertEqual(rel, "output/2026-07-04_gig/prototype/prototype_r1_1.png")
            self.assertEqual(resolve_output_path(rel), abs_path)

    def test_local_output_relative(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GIG_OUTPUT_DIR", None)
            out_dir = get_output_dir()
            abs_path = out_dir / "2026-07-04_gig" / "option-A_r1.png"
            rel = output_relative(abs_path)
            self.assertEqual(rel, "output/2026-07-04_gig/option-A_r1.png")
            self.assertEqual(resolve_output_path(rel), abs_path)

    def test_already_logical_path(self) -> None:
        with patch.dict(os.environ, {"GIG_OUTPUT_DIR": "/data/flyers-output"}):
            rel = "output/2026-07-04_gig/prototype/prototype_r1_1.png"
            self.assertEqual(output_relative(rel), rel)
            self.assertEqual(
                resolve_output_path(rel),
                Path("/data/flyers-output/2026-07-04_gig/prototype/prototype_r1_1.png"),
            )


if __name__ == "__main__":
    unittest.main()
