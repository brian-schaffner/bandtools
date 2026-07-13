"""Tests for agent secret resolution (local .env vs cloud secrets)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_secrets import (  # noqa: E402
    bootstrap_google_api_key_env,
    bootstrap_secrets,
    candidate_env_paths,
    is_cloud_agent,
    resolve_google_api_key,
    resolve_google_api_key_source,
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
            self.assertEqual(resolve_google_api_key_source(), ("gemini api key", key))
            self.assertEqual(resolve_google_api_key(), key)

    def test_bootstrap_exports_env(self) -> None:
        key = "AIza" + "a" * 35
        with patch.dict(os.environ, {"Apikey": key}, clear=True):
            bootstrap_google_api_key_env()
            self.assertEqual(os.environ.get("GOOGLE_API_KEY"), key)
            self.assertTrue(resolve_google_api_key())

    def test_local_env_path_in_candidates(self) -> None:
        paths = [str(p) for p in candidate_env_paths(anchor=ROOT)]
        self.assertIn("/Users/brian/dev/bandtools/gig-flyers/.env", paths)
        self.assertIn(str(ROOT / ".env"), paths)

    def test_cloud_agent_detection(self) -> None:
        with patch.dict(os.environ, {"CLOUD_AGENT_ALL_SECRET_NAMES": "gemini api key"}, clear=True):
            self.assertTrue(is_cloud_agent())
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_cloud_agent())

    def test_local_agent_loads_env_file(self) -> None:
        key = "AIza" + "b" * 35
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(f"GOOGLE_API_KEY={key}\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                with patch.object(sys.modules["agent_secrets"], "is_cloud_agent", return_value=False):
                    with patch.object(
                        sys.modules["agent_secrets"],
                        "candidate_env_paths",
                        return_value=[env_path],
                    ):
                        result = bootstrap_secrets()
                        self.assertTrue(result["google_key_configured"])
                        self.assertEqual(result["env_files_loaded"], [str(env_path)])
                        self.assertEqual(resolve_google_api_key(), key)

    def test_cloud_agent_prefers_injected_secret(self) -> None:
        key = "AIza" + "c" * 35
        with patch.dict(os.environ, {"gemini api key": key, "CLOUD_AGENT_ALL_SECRET_NAMES": "x"}, clear=True):
            result = bootstrap_secrets()
            self.assertTrue(result["cloud_agent"])
            self.assertEqual(resolve_google_api_key(), key)
            # Normalized into standard env var for downstream libraries.
            self.assertEqual(os.environ.get("GOOGLE_API_KEY"), key)


if __name__ == "__main__":
    unittest.main()
