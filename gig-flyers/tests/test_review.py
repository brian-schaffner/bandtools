#!/usr/bin/env python3
"""Tests for web review endpoints."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402


class ReviewEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        (self.tmp_path / "output" / "2026-07-14_stevie-ray-s-blues-bar").mkdir(parents=True)
        img = self.tmp_path / "output/2026-07-14_stevie-ray-s-blues-bar/option-A_r1.png"
        img.write_bytes(b"x" * 1024)
        img2 = self.tmp_path / "output/2026-07-14_stevie-ray-s-blues-bar/option-A_r2.png"
        img2.write_bytes(b"x" * 1024)
        manifest = {
            "gig_id": "2026-07-14_stevie-ray-s-blues-bar",
            "round": 1,
            "event": {
                "venue": "Stevie Ray's Blues Bar",
                "short_date": "Jul 14",
                "band": "Lindsey Lane Band",
            },
            "options": {"A": "output/2026-07-14_stevie-ray-s-blues-bar/option-A_r1.png"},
        }
        (self.tmp_path / "output/2026-07-14_stevie-ray-s-blues-bar/manifest_r1.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        state = {
            "gigs": {
                "2026-07-14_stevie-ray-s-blues-bar": {
                    "status": "pending_review",
                    "round": 1,
                    "options": manifest["options"],
                    "event": manifest["event"],
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

    def tearDown(self) -> None:
        from bridge.server import _generate_in_flight, _revise_in_flight

        _generate_in_flight.clear()
        _revise_in_flight.clear()
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_review_page_renders(self) -> None:
        resp = self.client.get("/review/2026-07-14_stevie-ray-s-blues-bar")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Stevie Ray", resp.text)
        self.assertIn("Option A", resp.text)

    def test_review_page_form_paths(self) -> None:
        resp = self.client.get("/review/2026-07-14_stevie-ray-s-blues-bar")
        self.assertIn('action="/flyers/review/2026-07-14_stevie-ray-s-blues-bar/approve"', resp.text)
        self.assertIn('action="/flyers/review/2026-07-14_stevie-ray-s-blues-bar/revise"', resp.text)

    def test_route_path_helpers(self) -> None:
        from bridge.review import approve_action, review_page_path, root_path

        self.assertEqual(root_path(), "/flyers")
        self.assertEqual(
            approve_action("2026-07-14_stevie-ray-s-blues-bar"),
            "/flyers/review/2026-07-14_stevie-ray-s-blues-bar/approve",
        )
        self.assertEqual(
            review_page_path("2026-07-14_stevie-ray-s-blues-bar"),
            "/flyers/review/2026-07-14_stevie-ray-s-blues-bar",
        )

    def test_resolve_gig_from_state(self) -> None:
        from flyer_generator import resolve_gig_event

        event = resolve_gig_event("2026-07-14_stevie-ray-s-blues-bar")
        self.assertEqual(event.venue, "Stevie Ray's Blues Bar")

    @patch("bridge.server._revise_gig_background")
    def test_revise_web(self, mock_bg) -> None:
        resp = self.client.post(
            "/review/2026-07-14_stevie-ray-s-blues-bar/revise",
            data={"option": "C", "feedback": "more color"},
            follow_redirects=False,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Generating new options", resp.text)
        mock_bg.assert_called_once()

    def test_review_link_message(self) -> None:
        from bridge.review import build_review_link_message

        msg = build_review_link_message(
            {"venue": "Stevie Ray's", "short_date": "Jul 14", "band": "LLB"},
            "2026-07-14_stevie-ray-s-blues-bar",
            3,
        )
        self.assertIn("/review/2026-07-14_stevie-ray-s-blues-bar", msg)
        self.assertNotIn("APPROVE", msg)

    def test_history_excludes_current_round(self) -> None:
        from bridge.review import build_review_data

        gig_dir = self.tmp_path / "output/2026-07-14_stevie-ray-s-blues-bar"
        for rnd, letter in ((1, "A"), (2, "A")):
            p = gig_dir / f"option-{letter}_r{rnd}.png"
            p.write_bytes(b"x" * 1024)
            manifest = {
                "gig_id": "2026-07-14_stevie-ray-s-blues-bar",
                "round": rnd,
                "event": {"venue": "Stevie Ray's Blues Bar"},
                "options": {letter: f"output/2026-07-14_stevie-ray-s-blues-bar/option-{letter}_r{rnd}.png"},
            }
            (gig_dir / f"manifest_r{rnd}.json").write_text(json.dumps(manifest), encoding="utf-8")

        state = {
            "gigs": {
                "2026-07-14_stevie-ray-s-blues-bar": {
                    "status": "pending_review",
                    "round": 2,
                    "options": {"A": "output/2026-07-14_stevie-ray-s-blues-bar/option-A_r2.png"},
                    "event": {"venue": "Stevie Ray's Blues Bar"},
                    "feedback_history": [],
                }
            },
            "last_poll_rowid": 0,
        }
        (self.tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")

        data = build_review_data("2026-07-14_stevie-ray-s-blues-bar")
        self.assertEqual(data["current_round"], 2)
        self.assertIn("option-A_r2", data["current_options"]["A"])
        self.assertEqual([r["round"] for r in data["history_rounds"]], [1])

    def test_empty_rounds_filtered_from_history(self) -> None:
        from bridge.review import build_review_data

        gig_dir = self.tmp_path / "output/2026-07-14_stevie-ray-s-blues-bar"
        (gig_dir / "option-A_r1.png").write_bytes(b"")
        (gig_dir / "option-A_r2.png").write_bytes(b"x" * 1024)
        for rnd in (1, 2):
            manifest = {
                "gig_id": "2026-07-14_stevie-ray-s-blues-bar",
                "round": rnd,
                "options": {"A": f"output/2026-07-14_stevie-ray-s-blues-bar/option-A_r{rnd}.png"},
            }
            (gig_dir / f"manifest_r{rnd}.json").write_text(json.dumps(manifest), encoding="utf-8")

        state = {
            "gigs": {
                "2026-07-14_stevie-ray-s-blues-bar": {
                    "status": "pending_review",
                    "round": 2,
                    "options": {"A": "output/2026-07-14_stevie-ray-s-blues-bar/option-A_r2.png"},
                    "event": {"venue": "Stevie Ray's Blues Bar"},
                    "feedback_history": [],
                }
            },
            "last_poll_rowid": 0,
        }
        (self.tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")

        data = build_review_data("2026-07-14_stevie-ray-s-blues-bar")
        self.assertEqual([r["round"] for r in data["history_rounds"]], [])

    def test_review_page_shows_research_panel(self) -> None:
        state = json.loads((self.tmp_path / "state.json").read_text(encoding="utf-8"))
        state["gigs"]["2026-07-14_stevie-ray-s-blues-bar"]["research"] = {
            "venue_type": "blues_bar",
            "demographics": ["blues_fans", "30_to_60"],
            "design_language": "blues_club_handbill",
            "design_notes": ["Blues club handbill aesthetic"],
            "date_context": {"holiday": None},
        }
        state["gigs"]["2026-07-14_stevie-ray-s-blues-bar"]["selected_photo"] = {
            "id": "instruments",
            "path": "bandphotos/679394308_1366641221939459_1410337987474015419_n.jpg",
            "reason": "Best match for blues_bar",
        }
        (self.tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
        resp = self.client.get("/review/2026-07-14_stevie-ray-s-blues-bar")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Gig context", resp.text)
        self.assertIn("blues_bar", resp.text)
        self.assertIn("instruments", resp.text)

    @patch("bridge.server.send_text")
    @patch("bridge.server.send_flyer_image", return_value="mail_app")
    @patch("bridge.server.send_image")
    def test_approve_json(self, _img, _email, _text) -> None:
        resp = self.client.post(
            "/review/2026-07-14_stevie-ray-s-blues-bar/approve.json",
            json={"option": "A"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "approved")


if __name__ == "__main__":
    unittest.main(verbosity=2)
