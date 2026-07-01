#!/usr/bin/env python3
"""Additional reviewer and status tests."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai_reviewer import build_review_prompt, review_flyer_image  # noqa: E402
from bridge.job_status import clear_all_jobs, report_progress, start_job  # noqa: E402
from gig_calendar import GigEvent  # noqa: E402
from image_providers.reference_compose import prepare_photo_compose  # noqa: E402
from progress_helper import heartbeat_during  # noqa: E402
from PIL import Image  # noqa: E402


def _write_test_jpeg(path: Path, size: tuple[int, int] = (800, 600)) -> None:
    Image.new("RGB", size, color=(120, 80, 60)).save(path, format="JPEG")


def _valid_single_pass_flyer(ref: Path, flyer: Path, *, tier: str = "medium") -> None:
    """Single-pass compose canvas — passes automated photo validation."""
    with tempfile.TemporaryDirectory() as tmp:
        compose = prepare_photo_compose(
            ref,
            (1024, 1536),
            tier=tier,
            work_dir=Path(tmp),
            create_mask=False,
        )
        Image.open(compose.canvas_path).convert("RGB").save(flyer, format="PNG")


class ReviewerFidelityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.event = GigEvent(
            event_date=date(2026, 7, 14),
            time_label="8:00 pm",
            title="Lindsey Lane Band at Stevie Ray's",
            venue="Stevie Ray's Blues Bar",
            suggested_name="Jul 14 Stevie Ray's",
        )

    def test_prompt_includes_fidelity_and_crop_checks(self) -> None:
        prompt = build_review_prompt(
            self.event,
            {"id": "conservative", "tier": "conservative"},
            selected_photo={"member_count": 4, "type": "group_standing"},
            has_reference=True,
        )
        self.assertIn("BAND PHOTO FIDELITY", prompt)
        self.assertIn("100% fidelity", prompt)
        self.assertIn("Stevie Ray's Blues Bar", prompt)
        self.assertIn("Do NOT fail based on counting members", prompt)
        self.assertIn("photo_matches_reference", prompt)
        self.assertIn("7:00pm vs 7:00 PM vs 7:00 pm is NOT a failure", prompt)
        self.assertIn("text_errors", prompt)
        self.assertIn("member_count_confidence", prompt)

    @patch("openai.OpenAI")
    def test_reviewer_ignores_three_of_four_with_reference(self, mock_openai_cls) -> None:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.return_value = type(
            "R",
            (),
            {
                "choices": [
                    type(
                        "C",
                        (),
                        {
                            "message": type(
                                "M",
                                (),
                                {
                                    "content": json.dumps(
                                        {
                                            "pass": False,
                                            "score": 4,
                                            "issues": ["Only 3 of 4 band members visible"],
                                            "remake_recommended": True,
                                            "feedback_for_regen": "Show all 4 members",
                                            "members_visible": 3,
                                            "member_count_confidence": 0.92,
                                            "photo_matches_reference": True,
                                            "text_errors": [],
                                        }
                                    )
                                },
                            )()
                        },
                    )()
                ]
            },
        )()

        with tempfile.TemporaryDirectory() as tmp:
            flyer = Path(tmp) / "flyer.png"
            ref = Path(tmp) / "ref.jpg"
            _write_test_jpeg(ref)
            _valid_single_pass_flyer(ref, flyer, tier="medium")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test", "AI_REVIEWER_ENABLED": "1"}):
                verdict = review_flyer_image(
                    flyer,
                    {},
                    self.event,
                    {"id": "v"},
                    reference_photo_path=ref,
                    selected_photo={"member_count": 4},
                    tier="medium",
                )
        self.assertFalse(verdict["remake_recommended"])
        self.assertTrue(verdict["pass"])
        self.assertEqual(verdict["members_visible"], 3)
        mock_client.chat.completions.create.assert_called_once()

    @patch("openai.OpenAI")
    def test_reviewer_fails_clear_distortion_with_reference(self, mock_openai_cls) -> None:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.return_value = type(
            "R",
            (),
            {
                "choices": [
                    type(
                        "C",
                        (),
                        {
                            "message": type(
                                "M",
                                (),
                                {
                                    "content": json.dumps(
                                        {
                                            "pass": False,
                                            "score": 4,
                                            "issues": ["Band faces warped and distorted vs reference"],
                                            "remake_recommended": True,
                                            "feedback_for_regen": "Preserve reference photo exactly",
                                            "photo_matches_reference": False,
                                            "text_errors": [],
                                        }
                                    )
                                },
                            )()
                        },
                    )()
                ]
            },
        )()

        with tempfile.TemporaryDirectory() as tmp:
            flyer = Path(tmp) / "flyer.png"
            ref = Path(tmp) / "ref.jpg"
            _write_test_jpeg(ref)
            _valid_single_pass_flyer(ref, flyer, tier="medium")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test", "AI_REVIEWER_ENABLED": "1"}):
                verdict = review_flyer_image(
                    flyer,
                    {},
                    self.event,
                    {"id": "v"},
                    reference_photo_path=ref,
                    selected_photo={"member_count": 4},
                    tier="medium",
                )
        self.assertTrue(verdict["remake_recommended"])

    @patch("openai.OpenAI")
    def test_reviewer_fails_photo_matches_reference_false_without_model_remake(self, mock_openai_cls) -> None:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.return_value = type(
            "R",
            (),
            {
                "choices": [
                    type(
                        "C",
                        (),
                        {
                            "message": type(
                                "M",
                                (),
                                {
                                    "content": json.dumps(
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
                                            "text_errors": [],
                                        }
                                    )
                                },
                            )()
                        },
                    )()
                ]
            },
        )()

        with tempfile.TemporaryDirectory() as tmp:
            flyer = Path(tmp) / "flyer.png"
            ref = Path(tmp) / "ref.jpg"
            _write_test_jpeg(ref)
            _valid_single_pass_flyer(ref, flyer, tier="medium")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test", "AI_REVIEWER_ENABLED": "1"}):
                verdict = review_flyer_image(
                    flyer,
                    {},
                    self.event,
                    {"id": "medium", "tier": "medium"},
                    reference_photo_path=ref,
                    selected_photo={"member_count": 4},
                    tier="medium",
                )
        self.assertFalse(verdict["pass"])
        self.assertTrue(verdict["remake_recommended"])

    @patch("openai.OpenAI")
    def test_reviewer_passes_ambiguous_member_count(self, mock_openai_cls) -> None:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.return_value = type(
            "R",
            (),
            {
                "choices": [
                    type(
                        "C",
                        (),
                        {
                            "message": type(
                                "M",
                                (),
                                {
                                    "content": json.dumps(
                                        {
                                            "pass": False,
                                            "score": 6,
                                            "issues": ["Only 3 of 4 band members visible"],
                                            "remake_recommended": True,
                                            "feedback_for_regen": "Show all 4 members",
                                            "members_visible": 3,
                                            "member_count_confidence": 0.55,
                                            "text_errors": [],
                                        }
                                    )
                                },
                            )()
                        },
                    )()
                ]
            },
        )()

        with tempfile.TemporaryDirectory() as tmp:
            flyer = Path(tmp) / "flyer.png"
            ref = Path(tmp) / "ref.jpg"
            _write_test_jpeg(ref)
            _valid_single_pass_flyer(ref, flyer, tier="medium")
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test", "AI_REVIEWER_ENABLED": "1"}):
                verdict = review_flyer_image(
                    flyer,
                    {},
                    self.event,
                    {"id": "v"},
                    reference_photo_path=ref,
                    selected_photo={"member_count": 4},
                    tier="medium",
                )
        self.assertFalse(verdict["remake_recommended"])
        self.assertTrue(verdict["pass"])

    @patch("openai.OpenAI")
    def test_reviewer_hard_fails_automated_photo_validation_before_vision(self, mock_openai_cls) -> None:
        """Automated validate_flyer_photo runs before vision API; duplicate photo hard-fails."""
        from PIL import ImageDraw

        from image_providers.reference_compose import prepare_photo_compose

        def _synthetic_band(path: Path, size: tuple[int, int] = (800, 600)) -> None:
            img = Image.new("RGB", size, color=(120, 80, 60))
            draw = ImageDraw.Draw(img)
            draw.rectangle([80, 60, 720, 540], fill=(180, 140, 100))
            draw.ellipse([200, 120, 320, 240], fill=(220, 190, 160))
            img.save(path, format="JPEG")

        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.jpg"
            flyer = Path(tmp) / "flyer.png"
            _synthetic_band(ref, (400, 300))
            compose = prepare_photo_compose(
                ref, (1024, 1536), tier="medium", work_dir=Path(tmp) / "work", create_mask=False
            )
            plate = Image.open(compose.canvas_path).convert("RGB")
            left, top, right, bottom = compose.photo_bbox
            ref_img = Image.open(ref).convert("RGB")
            dup_w = max(96, (right - left) // 4)
            dup_h = max(72, (bottom - top) // 4)
            plate.paste(ref_img.resize((dup_w, dup_h)), (40, 40))
            plate.save(flyer, format="PNG")

            with patch.dict("os.environ", {"OPENAI_API_KEY": "test", "AI_REVIEWER_ENABLED": "1"}):
                verdict = review_flyer_image(
                    flyer,
                    {},
                    self.event,
                    {"id": "medium", "tier": "medium"},
                    reference_photo_path=ref,
                    selected_photo={"member_count": 4},
                    tier="medium",
                )

        mock_openai_cls.assert_not_called()
        self.assertFalse(verdict["pass"])
        self.assertTrue(verdict["remake_recommended"])
        self.assertIn("photo_validation", verdict)
        self.assertFalse(verdict["photo_validation"]["passed"])


class StatusHeartbeatTest(unittest.TestCase):
    def tearDown(self) -> None:
        clear_all_jobs()

    def test_heartbeat_during_blocking_updates_revision(self) -> None:
        events: list[dict] = []

        def cb(**kwargs):
            events.append(kwargs)

        start_job("gig-1", "generate")
        with heartbeat_during(cb, step="generate", message_template="wait {seconds}s", interval=0.2):
            time.sleep(0.55)
        self.assertGreaterEqual(len(events), 2)
        self.assertTrue(all(e.get("log") is False for e in events))

    def test_thread_safe_progress(self) -> None:
        start_job("gig-2", "generate")

        def worker(n: int) -> None:
            for i in range(10):
                report_progress("gig-2", step="generate", substep=f"w{n}", message=f"t{i}", progress=i)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        from bridge.job_status import get_job_status

        snap = get_job_status("gig-2")
        self.assertEqual(snap["status"], "running")
        self.assertGreater(snap["log_revision"], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
