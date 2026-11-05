#!/usr/bin/env python3
"""On-demand day-schedule pages: pick a published gig, view, adjust, download, email."""

from __future__ import annotations

import email
import email.policy
import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import gig_calendar  # noqa: E402
from logistics.backtest import FIXTURES  # noqa: E402

TWO_LANE = "2026-11-07_two-lane-tavern"


def _snapshot_events() -> list[gig_calendar.GigEvent]:
    return gig_calendar._parse_events((FIXTURES / "calendar_2026-11-05.html").read_text(encoding="utf-8"))


class LogisticsWebTest(unittest.TestCase):
    def setUp(self) -> None:
        events = _snapshot_events()
        by_id = {e.gig_id: e for e in events}
        self.patches = [
            patch.dict(
                os.environ,
                {"ROOT_PATH": "/flyers", "GOOGLE_MAPS_API_KEY": "", "BAND_HOME_ADDRESS": "", "SMTP_HOST": ""},
            ),
            patch("bridge.logistics_page.get_future_gigs", return_value=events),
            patch("bridge.logistics_page.find_gig_by_id", side_effect=by_id.get),
            patch("bridge.logistics_page.get_local_today", return_value=date(2026, 11, 5)),
        ]
        for p in self.patches:
            p.start()
        from bridge.logistics_page import register_logistics_routes

        app = FastAPI()
        register_logistics_routes(app)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        for p in reversed(self.patches):
            p.stop()

    def test_list_page_offers_every_published_gig(self) -> None:
        res = self.client.get("/flyers/logistics")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Two Lane Tavern", res.text)
        self.assertIn(f'href="/flyers/logistics/{TWO_LANE}"', res.text)
        self.assertIn("Skipped in weekly run", res.text)
        self.assertIn("Day schedule", res.text)

    def test_gig_page_builds_schedule(self) -> None:
        res = self.client.get(f"/flyers/logistics/{TWO_LANE}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("<strong>4:15 PM — PULL OUT FROM HOME</strong>", res.text)
        self.assertIn("<strong>7:30 PM — DEAD STAGE</strong>", res.text)
        self.assertIn("NEEDS CONFIRMATION", res.text)
        self.assertIn("Email isn’t configured", res.text)

    def test_overrides_rebuild_schedule(self) -> None:
        res = self.client.get(f"/flyers/logistics/{TWO_LANE}", params={"end": "11:00 pm", "drive": "25"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("4:35 PM — PULL OUT FROM HOME", res.text)
        self.assertIn("Gig: 8:00–11:00 PM", res.text)
        self.assertIn("25-minute drive (entered)", res.text)
        self.assertNotIn("End time not published", res.text)
        self.assertNotIn("Drive time is an estimate", res.text)
        self.assertIn('value="11:00 pm"', res.text)

    def test_bad_override_is_reported_and_ignored(self) -> None:
        res = self.client.get(f"/flyers/logistics/{TWO_LANE}", params={"drive": "abc"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("Drive minutes must be a whole number", res.text)
        self.assertIn("4:15 PM — PULL OUT FROM HOME", res.text)

    def test_text_download(self) -> None:
        res = self.client.get(f"/flyers/logistics/{TWO_LANE}/text", params={"drive": "25"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("attachment", res.headers["content-disposition"])
        self.assertIn("4:35 PM — PULL OUT FROM HOME", res.text)
        self.assertNotIn("**", res.text)

    def test_unknown_gig_is_404(self) -> None:
        self.assertEqual(self.client.get("/flyers/logistics/2026-01-01_nowhere").status_code, 404)
        self.assertEqual(self.client.get("/flyers/logistics/2026-01-01_nowhere/text").status_code, 404)

    def test_email_sends_schedule(self) -> None:
        smtp = MagicMock()
        with patch.dict(os.environ, {"SMTP_HOST": "smtp.example.com", "SMTP_PORT": "587", "SMTP_USER": "u", "SMTP_PASSWORD": "p"}), patch(
            "logistics.delivery.smtplib.SMTP", return_value=smtp
        ):
            page = self.client.get(f"/flyers/logistics/{TWO_LANE}")
            self.assertIn("Email to brian@schaffner.net", page.text)
            res = self.client.post(f"/flyers/logistics/{TWO_LANE}/email", data={"end": "", "drive": "30"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("Emailed to brian@schaffner.net", res.text)
        server = smtp.__enter__.return_value
        server.starttls.assert_called_once()
        server.login.assert_called_once_with("u", "p")
        sender, recipients, raw = server.sendmail.call_args.args
        self.assertEqual(recipients, ["brian@schaffner.net"])
        message = email.message_from_string(raw, policy=email.policy.default)
        self.assertEqual(message["Subject"], "Gig day schedule — Sat Nov 7 · Two Lane Tavern")
        plain = message.get_body(preferencelist=("plain",)).get_content()
        self.assertIn("4:30 PM — PULL OUT FROM HOME", plain)
        self.assertNotIn("**", plain)
        html_body = message.get_body(preferencelist=("html",)).get_content()
        self.assertIn("<strong>7:30 PM — DEAD STAGE</strong>", html_body)

    def test_email_failure_is_shown(self) -> None:
        res = self.client.post(f"/flyers/logistics/{TWO_LANE}/email", data={})
        self.assertEqual(res.status_code, 502)
        self.assertIn("Email failed", res.text)


if __name__ == "__main__":
    unittest.main()
