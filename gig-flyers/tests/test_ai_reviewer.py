#!/usr/bin/env python3
"""Tests for AI flyer reviewer."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_reviewer import _filter_text_errors, _is_trivial_text_error, _normalize_verdict, review_flyer_image  # noqa: E402
from gig_calendar import GigEvent  # noqa: E402


class AIReviewerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.event = GigEvent(
            event_date=date(2026, 7, 14),
            time_label="8:00 pm",
            title="Lindsey Lane Band at Test Venue",
            venue="Test Venue",
            suggested_name="Jul 14 Test Venue",
        )
        self.variation = {"id": "conservative", "label": "A) Conservative", "tier": "conservative"}

    def test_normalize_verdict_pass(self) -> None:
        verdict = _normalize_verdict({"pass": True, "score": 9, "issues": []})
        self.assertTrue(verdict["pass"])
        self.assertFalse(verdict["remake_recommended"])
        self.assertEqual(verdict["display_note"], "Passed")

    def test_normalize_verdict_remake(self) -> None:
        verdict = _normalize_verdict(
            {
                "pass": False,
                "score": 4,
                "issues": ["Face cropped awkwardly"],
                "remake_recommended": True,
                "feedback_for_regen": "Show full band photo without cropping faces.",
            },
            retry_count=1,
        )
        self.assertTrue(verdict["remake_recommended"])
        self.assertIn("Remade", verdict["display_note"])

    def test_normalize_ignores_pm_casing_nitpick(self) -> None:
        verdict = _normalize_verdict(
            {
                "pass": False,
                "score": 6,
                "issues": ["Time should read 7:00 PM not 7:00pm"],
                "remake_recommended": True,
                "text_errors": ["PM capitalization in showtime"],
            }
        )
        self.assertTrue(verdict["pass"])
        self.assertFalse(verdict["remake_recommended"])
        self.assertEqual(verdict["text_errors"], [])

    def test_trivial_text_error_helpers(self) -> None:
        self.assertTrue(_is_trivial_text_error("PM capitalization in 7:00pm"))
        self.assertTrue(_is_trivial_text_error("7:00pm vs 7:00 PM casing"))
        self.assertFalse(_is_trivial_text_error("Wrong venue name: Stevie Ray"))
        self.assertEqual(
            _filter_text_errors(["PM casing", "Wrong date on flyer"]),
            ["Wrong date on flyer"],
        )

    def test_member_count_low_confidence_passes(self) -> None:
        verdict = _normalize_verdict(
            {
                "pass": False,
                "score": 6,
                "issues": ["Only 3 of 4 band members visible"],
                "remake_recommended": True,
                "members_visible": 3,
                "member_count_confidence": 0.5,
            },
            expected_members=4,
        )
        self.assertTrue(verdict["pass"])
        self.assertFalse(verdict["remake_recommended"])
        self.assertEqual(verdict["members_visible"], 3)

    def test_member_count_high_confidence_fails_without_reference(self) -> None:
        verdict = _normalize_verdict(
            {
                "pass": False,
                "score": 4,
                "issues": ["Member cropped off at left edge"],
                "remake_recommended": True,
                "members_visible": 3,
                "member_count_confidence": 0.95,
            },
            expected_members=4,
            has_reference=False,
        )
        self.assertFalse(verdict["pass"])
        self.assertTrue(verdict["remake_recommended"])

    def test_member_count_high_confidence_passes_with_reference(self) -> None:
        verdict = _normalize_verdict(
            {
                "pass": False,
                "score": 6,
                "issues": ["Only 3 of 4 band members visible"],
                "remake_recommended": True,
                "members_visible": 3,
                "member_count_confidence": 0.95,
            },
            expected_members=4,
            has_reference=True,
        )
        self.assertTrue(verdict["pass"])
        self.assertFalse(verdict["remake_recommended"])
        self.assertEqual(verdict["issues"], [])

    def test_photo_matches_reference_clears_distortion_issues(self) -> None:
        verdict = _normalize_verdict(
            {
                "pass": True,
                "score": 8,
                "issues": ["Only 3 of 4 band members visible"],
                "remake_recommended": True,
                "members_visible": 3,
                "member_count_confidence": 0.9,
                "photo_matches_reference": True,
            },
            expected_members=4,
            has_reference=True,
        )
        self.assertTrue(verdict["pass"])
        self.assertFalse(verdict["remake_recommended"])

    def test_photo_matches_reference_false_fails_even_when_model_passes(self) -> None:
        """Regression: option-B_r5 passed with photo_matches_reference=false."""
        verdict = _normalize_verdict(
            {
                "pass": True,
                "score": 7,
                "issues": [
                    "Band photo is cut off at the heads of two members",
                    "Generated photo does not match the reference photo due to cropping",
                ],
                "remake_recommended": False,
                "photo_matches_reference": False,
                "members_visible": 4,
            },
            expected_members=4,
            has_reference=True,
        )
        self.assertFalse(verdict["pass"])
        self.assertTrue(verdict["remake_recommended"])

    def test_graphics_over_face_fails_with_reference(self) -> None:
        verdict = _normalize_verdict(
            {
                "pass": True,
                "score": 7,
                "issues": ["Blue starburst covers rightmost band member face"],
                "remake_recommended": False,
                "photo_matches_reference": True,
            },
            has_reference=True,
        )
        self.assertFalse(verdict["pass"])
        self.assertTrue(verdict["remake_recommended"])

    def test_double_photo_issue_fails_with_reference(self) -> None:
        verdict = _normalize_verdict(
            {
                "pass": True,
                "score": 7,
                "issues": ["Duplicate band photo inset pasted over larger generated photo"],
                "remake_recommended": False,
                "photo_matches_reference": False,
            },
            has_reference=True,
        )
        self.assertFalse(verdict["pass"])
        self.assertTrue(verdict["remake_recommended"])

    def test_four_members_visible_passes(self) -> None:
        verdict = _normalize_verdict(
            {
                "pass": True,
                "score": 8,
                "issues": [],
                "members_visible": 4,
                "member_count_confidence": 0.9,
            },
            expected_members=4,
        )
        self.assertTrue(verdict["pass"])
        self.assertFalse(verdict["remake_recommended"])

    def test_review_skipped_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flyer.png"
            path.write_bytes(b"x" * 2000)
            verdict = review_flyer_image(path, {}, self.event, self.variation, dry_run=True)
            self.assertTrue(verdict["pass"])

    @patch("openai.OpenAI")
    def test_review_calls_vision_api(self, mock_openai_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "pass": False,
                            "score": 5,
                            "issues": ["Unreadable date text"],
                            "remake_recommended": True,
                            "feedback_for_regen": "Make date and venue text larger and clearer.",
                        }
                    )
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flyer.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 2000)
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key", "AI_REVIEWER_ENABLED": "1"}):
                verdict = review_flyer_image(path, {"core_principles": []}, self.event, self.variation)

        self.assertTrue(verdict["remake_recommended"])
        self.assertIn("Unreadable", verdict["issues"][0])
        mock_client.chat.completions.create.assert_called_once()


class AIReviewerIntegrationTest(unittest.TestCase):
    @patch("flyer_generator.review_flyer_image")
    @patch("flyer_generator.generate_image")
    @patch("flyer_generator.resolve_gig_event")
    def test_generate_retries_on_reviewer_fail(
        self,
        mock_resolve: MagicMock,
        mock_generate: MagicMock,
        mock_review: MagicMock,
    ) -> None:
        from flyer_generator import generate_for_gig

        event = GigEvent(
            event_date=date(2026, 7, 14),
            time_label="8:00 pm",
            title="Lindsey Lane Band at Test Venue",
            venue="Test Venue",
            suggested_name="Jul 14 Test Venue",
        )
        mock_resolve.return_value = event
        review_calls: dict[str, int] = {"A": 0, "B": 0, "C": 0}

        def review_side_effect(*_args, **kwargs):
            option = str(kwargs.get("option") or "A")
            review_calls[option] = review_calls.get(option, 0) + 1
            if option == "A" and review_calls[option] == 1:
                return {
                    "pass": False,
                    "score": 4,
                    "issues": ["AI glow effect"],
                    "remake_recommended": True,
                    "feedback_for_regen": "Remove polished AI lighting.",
                    "retry_count": 0,
                    "display_note": "Remade (1x): AI glow effect",
                }
            if option == "A" and review_calls[option] == 2:
                return {
                    "pass": True,
                    "score": 8,
                    "issues": [],
                    "remake_recommended": False,
                    "feedback_for_regen": "",
                    "retry_count": 1,
                    "display_note": "Remade (1x): quality fixes applied",
                }
            return {
                "pass": True,
                "score": 9,
                "issues": [],
                "remake_recommended": False,
                "feedback_for_regen": "",
                "retry_count": 0,
                "display_note": "Passed",
            }

        mock_review.side_effect = review_side_effect

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "state.json").write_text(json.dumps({"gigs": {}, "last_poll_rowid": 0}))
            with patch("flyer_generator.ROOT", tmp_path):
                with patch("flyer_generator.get_output_dir", return_value=tmp_path / "output"):
                    with patch("state.STATE_PATH", tmp_path / "state.json"):
                        with patch("state.APPROVED_DIR", tmp_path / "output" / "approved"):
                            with patch.dict("os.environ", {"AI_REVIEWER_ENABLED": "1"}):
                                manifest = generate_for_gig("2026-07-14_test", count=3, dry_run=False)

        self.assertEqual(mock_generate.call_count, 4)
        verdict_a = manifest["reviewer_verdicts"]["A"]
        self.assertTrue(verdict_a["pass"])
        self.assertEqual(verdict_a["retry_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
