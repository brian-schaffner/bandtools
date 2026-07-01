#!/usr/bin/env python3
"""Tests for regenerate (fresh round) workflow."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from gig_calendar import GigEvent  # noqa: E402
from state import begin_regenerate_round, can_regenerate, has_existing_generation, upsert_gig  # noqa: E402


class RegenerateStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        (self.tmp_path / "state.json").write_text(json.dumps({"gigs": {}, "last_poll_rowid": 0}))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_has_existing_generation(self) -> None:
        with patch("state.STATE_PATH", self.tmp_path / "state.json"):
            self.assertFalse(has_existing_generation("gig-1"))
            upsert_gig("gig-1", round=1, options={"A": "output/x.png"})
            self.assertTrue(has_existing_generation("gig-1"))

    def test_can_regenerate_when_pending(self) -> None:
        with patch("state.STATE_PATH", self.tmp_path / "state.json"):
            upsert_gig("gig-1", status="pending_review", round=2, options={"A": "x"})
            self.assertTrue(can_regenerate("gig-1"))

    def test_can_regenerate_when_approved(self) -> None:
        with patch("state.STATE_PATH", self.tmp_path / "state.json"):
            upsert_gig("gig-1", status="approved", round=2, options={"A": "x"})
            self.assertTrue(can_regenerate("gig-1"))

    def test_begin_regenerate_archives_approval(self) -> None:
        with patch("state.STATE_PATH", self.tmp_path / "state.json"):
            upsert_gig(
                "gig-1",
                status="approved",
                round=2,
                options={"A": "output/x.png"},
                approved_option="B",
                approved_path="output/approved/gig-1_B.png",
            )
            record = begin_regenerate_round("gig-1")
            self.assertEqual(record["status"], "regenerating")
            self.assertIsNone(record.get("approved_option"))
            self.assertEqual(len(record["approval_history"]), 1)
            self.assertEqual(record["approval_history"][0]["option"], "B")
            self.assertEqual(record["approval_history"][0]["round"], 2)


class RegenerateEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        gig_dir = self.tmp_path / "output/2026-07-14_stevie-ray-s-tuesday-jam"
        gig_dir.mkdir(parents=True)
        (gig_dir / "option-A_r1.png").write_bytes(b"x" * 1024)
        state = {
            "gigs": {
                "2026-07-14_stevie-ray-s-tuesday-jam": {
                    "status": "pending_review",
                    "round": 1,
                    "options": {"A": "output/2026-07-14_stevie-ray-s-tuesday-jam/option-A_r1.png"},
                    "event": {
                        "venue": "Stevie Ray's Tuesday Jam",
                        "short_date": "Jul 14",
                        "band": "Lindsey Lane Band",
                        "date": "2026-07-14",
                    },
                    "feedback_history": [],
                }
            },
            "last_poll_rowid": 0,
        }
        (self.tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")

        self.patches = [
            patch("state.ROOT", self.tmp_path),
            patch("state.STATE_PATH", self.tmp_path / "state.json"),
            patch("state.APPROVED_DIR", self.tmp_path / "output/approved"),
            patch("bridge.review.ROOT", self.tmp_path),
            patch("bridge.review.OUTPUT_DIR", self.tmp_path / "output"),
            patch.dict("os.environ", {"BRIDGE_PUBLIC_URL": "http://test.local/flyers"}),
        ]
        for p in self.patches:
            p.start()

        from bridge.server import app

        self.client = TestClient(app)
        self.gig_id = "2026-07-14_stevie-ray-s-tuesday-jam"

    def tearDown(self) -> None:
        from bridge.server import _generate_in_flight, _revise_in_flight

        _generate_in_flight.clear()
        _revise_in_flight.clear()
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_review_page_shows_regenerate_button(self) -> None:
        resp = self.client.get(f"/review/{self.gig_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Regenerate all options", resp.text)
        self.assertIn("/flyers/review/", resp.text)
        self.assertIn("/regenerate", resp.text)

    @patch("bridge.server._run_regenerate_background")
    def test_review_regenerate_starts_background(self, mock_bg) -> None:
        resp = self.client.post(f"/review/{self.gig_id}/regenerate")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Regenerating flyer options", resp.text)
        mock_bg.assert_called_once()

    @patch("bridge.server._run_regenerate_background")
    def test_pick_regenerate_starts_background(self, mock_bg) -> None:
        resp = self.client.post(f"/pick/{self.gig_id}/regenerate")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("fresh round", resp.text.lower())
        mock_bg.assert_called_once()

    def _approved_state(self) -> None:
        approved = self.tmp_path / "output/approved"
        approved.mkdir(parents=True, exist_ok=True)
        approved_file = approved / f"{self.gig_id}_A.png"
        approved_file.write_bytes(b"x" * 1024)
        state = json.loads((self.tmp_path / "state.json").read_text(encoding="utf-8"))
        state["gigs"][self.gig_id].update(
            {
                "status": "approved",
                "approved_option": "A",
                "approved_path": str(approved_file),
            }
        )
        (self.tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")

    def test_review_page_shows_regenerate_when_approved(self) -> None:
        self._approved_state()
        resp = self.client.get(f"/review/{self.gig_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Regenerate all options", resp.text)
        self.assertIn("Approved option A", resp.text)
        self.assertIn("Previous approval stays in history", resp.text)

    @patch("bridge.server._run_regenerate_background")
    def test_review_regenerate_on_approved_starts_background(self, mock_bg) -> None:
        self._approved_state()
        resp = self.client.post(f"/review/{self.gig_id}/regenerate")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Regenerating flyer options", resp.text)
        mock_bg.assert_called_once()
        record = json.loads((self.tmp_path / "state.json").read_text(encoding="utf-8"))
        gig = record["gigs"][self.gig_id]
        self.assertEqual(gig["status"], "regenerating")
        self.assertEqual(len(gig["approval_history"]), 1)
        self.assertEqual(gig["approval_history"][0]["option"], "A")

    def test_pick_page_shows_regenerate_for_approved(self) -> None:
        self._approved_state()
        with patch("bridge.interactive.get_future_gigs") as mock_gigs:
            from gig_calendar import GigEvent

            mock_gigs.return_value = [
                GigEvent(
                    event_date=date(2026, 7, 14),
                    time_label="8:00 pm",
                    title="Lindsey Lane Band at Stevie Ray's Tuesday Jam",
                    venue="Stevie Ray's Tuesday Jam",
                    suggested_name="Jul 14 Stevie Ray's Tuesday Jam",
                )
            ]
            with patch("bridge.interactive.get_local_today", return_value=date(2026, 6, 23)):
                resp = self.client.get("/pick")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Regenerate", resp.text)
        self.assertIn("Review", resp.text)


class RegenerateGeneratorTest(unittest.TestCase):
    def test_fresh_start_clears_used_variations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "state.json").write_text(
                json.dumps(
                    {
                        "gigs": {
                            "2026-07-14_test": {
                                "status": "pending_review",
                                "round": 1,
                                "used_variations": [
                                    "conservative",
                                    "medium",
                                    "creative",
                                ],
                                "event": {
                                    "date": "2026-07-14",
                                    "venue": "Test Venue",
                                    "title": "Lindsey Lane Band at Test Venue",
                                    "time": "8:00 pm",
                                },
                            }
                        },
                        "last_poll_rowid": 0,
                    }
                ),
                encoding="utf-8",
            )
            event = GigEvent(
                event_date=date(2026, 7, 14),
                time_label="8:00 pm",
                title="Lindsey Lane Band at Test Venue",
                venue="Test Venue",
                suggested_name="Jul 14 Test Venue",
            )
            with patch("flyer_generator.ROOT", tmp_path):
                with patch("flyer_generator.get_output_dir", return_value=tmp_path / "output"):
                    with patch("state.STATE_PATH", tmp_path / "state.json"):
                        with patch("state.APPROVED_DIR", tmp_path / "output" / "approved"):
                            with patch("flyer_generator.resolve_gig_event", return_value=event):
                                with patch("flyer_generator.generate_image"):
                                    from flyer_generator import generate_for_gig

                                    generate_for_gig(
                                        "2026-07-14_test",
                                        count=3,
                                        fresh_start=True,
                                        dry_run=True,
                                    )
            record = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
            used = record["gigs"]["2026-07-14_test"]["used_variations"]
            self.assertEqual(len(used), 3)
            self.assertEqual(len(set(used)), 3)

    def test_fresh_start_works_on_approved_gig(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "state.json").write_text(
                json.dumps(
                    {
                        "gigs": {
                            "2026-07-14_test": {
                                "status": "approved",
                                "round": 1,
                                "options": {"A": "output/x.png"},
                                "approved_option": "A",
                                "event": {
                                    "date": "2026-07-14",
                                    "venue": "Test Venue",
                                    "title": "Lindsey Lane Band at Test Venue",
                                    "time": "8:00 pm",
                                },
                            }
                        },
                        "last_poll_rowid": 0,
                    }
                ),
                encoding="utf-8",
            )
            event = GigEvent(
                event_date=date(2026, 7, 14),
                time_label="8:00 pm",
                title="Lindsey Lane Band at Test Venue",
                venue="Test Venue",
                suggested_name="Jul 14 Test Venue",
            )
            with patch("flyer_generator.ROOT", tmp_path):
                with patch("flyer_generator.get_output_dir", return_value=tmp_path / "output"):
                    with patch("state.STATE_PATH", tmp_path / "state.json"):
                        with patch("state.APPROVED_DIR", tmp_path / "output" / "approved"):
                            with patch("flyer_generator.resolve_gig_event", return_value=event):
                                with patch("flyer_generator.generate_image"):
                                    from flyer_generator import generate_for_gig

                                    manifest = generate_for_gig(
                                        "2026-07-14_test",
                                        count=3,
                                        fresh_start=True,
                                        dry_run=True,
                                    )
            self.assertNotIn("skipped", manifest)
            record = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(record["gigs"]["2026-07-14_test"]["status"], "pending_review")


if __name__ == "__main__":
    unittest.main(verbosity=2)
