#!/usr/bin/env python3
"""Tests for deploy build metadata."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge.build_info import build_stamp_html, build_stamp_text, get_build_info  # noqa: E402
from bridge.ui import page_close  # noqa: E402


class BuildInfoTest(unittest.TestCase):
    def test_stamp_from_build_info_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "build-info.json"
            path.write_text(
                json.dumps(
                    {
                        "git_sha": "abc1234567890",
                        "git_sha_short": "abc1234",
                        "build_number": "42",
                        "built_at": "2026-07-28T06:00:00Z",
                        "deploy_env": "staging",
                        "label": "42-abc1234",
                    }
                ),
                encoding="utf-8",
            )
            with patch("bridge.build_info._BUILD_INFO_CANDIDATES", (path,)):
                get_build_info.cache_clear()
                text = build_stamp_text()
                self.assertIn("42-abc1234", text)
                self.assertIn("staging", text)
                self.assertIn("2026-07-28", text)
                html = build_stamp_html()
                self.assertIn("site-build-stamp", html)
                get_build_info.cache_clear()

    def test_page_close_includes_stamp(self) -> None:
        self.assertIn("site-build-stamp", page_close())


if __name__ == "__main__":
    unittest.main()
