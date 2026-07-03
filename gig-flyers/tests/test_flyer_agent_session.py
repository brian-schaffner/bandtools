#!/usr/bin/env python3
"""Tests for Flyer Agent session sync."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flyer_agent.session_sync import agent_session_sync_script, render_session_bootstrap  # noqa: E402


class SessionSyncTest(unittest.TestCase):
    def test_bootstrap_page_includes_sync_script(self) -> None:
        html = render_session_bootstrap(redirect_to="/flyers/agent")
        self.assertIn("localStorage.getItem('session_token')", html)
        self.assertIn("document.cookie", html)
        self.assertIn("Checking session", html)

    def test_sync_script_sets_cookie_before_redirect(self) -> None:
        script = agent_session_sync_script(redirect_to="/flyers/agent")
        self.assertIn("setSessionCookie(token)", script)
        self.assertIn("/agent/api/session", script)


if __name__ == "__main__":
    unittest.main()
