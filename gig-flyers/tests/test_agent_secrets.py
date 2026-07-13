"""Tests for agent secret resolution."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_secrets import (  # noqa: E402
    bootstrap_google_api_key_env,
    google_api_key_configured,
    resolve_google_api_key,
)


class AgentSecretsTests(unittest.TestCase):
    def test_direct_google_key(self) -> None:
        key = "AIza" + "x" * 35
        with patch.dict(os.environ, {"GOOGLE_API_KEY": key}, clear=True):
            self.assertEqual(resolve_google_api_key(), key)

    def test_apikey_alias(self) -> None:
        key = "AIza" + "y" * 35
        with patch.dict(os.environ, {"Apikey": key}, clear=True):
            self.assertEqual(resolve_google_api_key(), key)

    def test_gemini_api_key_agent_alias(self) -> None:
        key = "AIza" + "g" * 35
        with patch.dict(os.environ, {"gemini api key": key}, clear=True):
            from agent_secrets import resolve_google_api_key_source

            self.assertEqual(resolve_google_api_key_source(), ("gemini api key", key))
            self.assertEqual(resolve_google_api_key(), key)

    def test_bootstrap_exports_env(self) -> None:
        key = "AIza" + "a" * 35
        with patch.dict(os.environ, {"Apikey": key}, clear=True):
            bootstrap_google_api_key_env()
            self.assertEqual(os.environ.get("GOOGLE_API_KEY"), key)
            self.assertTrue(google_api_key_configured())


if __name__ == "__main__":
    unittest.main()
