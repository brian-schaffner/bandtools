#!/usr/bin/env python3
"""Tests for shell job pause/resume status."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge.job_status import (  # noqa: E402
    clear_all_jobs,
    get_job_status,
    pause_job_for_route,
    resume_job,
    start_job,
)


class ShellJobStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_all_jobs()

    def tearDown(self) -> None:
        clear_all_jobs()

    def test_pause_and_resume_route_flow(self) -> None:
        start_job("shell-test", "shell_design", title="Test shell")
        pause_job_for_route("shell-test", "Choose path")
        snap = get_job_status("shell-test")
        self.assertEqual(snap["status"], "awaiting_route")
        self.assertEqual(snap["step"], "prepass")

        resume_job("shell-test", message="Final pass starting")
        snap = get_job_status("shell-test")
        self.assertEqual(snap["status"], "running")
        self.assertIn("Final", snap["message"])


if __name__ == "__main__":
    unittest.main()
