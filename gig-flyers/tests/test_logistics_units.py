#!/usr/bin/env python3
"""Unit tests for logistics helpers: address parsing, drive time, formatting, venue config."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import event_from_dict, extract_address  # noqa: E402
from logistics import drive_time  # noqa: E402
from logistics.drive_time import google_drive_minutes, query_distance_matrix, resolve_drive, round_up_to_5  # noqa: E402
from logistics.profiles import load_config  # noqa: E402
from logistics.render import city_state, fmt_range  # noqa: E402
from logistics.schedule import parse_clock  # noqa: E402


class AddressTests(unittest.TestCase):
    def test_extract_address(self) -> None:
        cases = {
            "Two Lane Tavern 9702 Old Bardstown Rd, Louisville, KY 40291": "9702 Old Bardstown Rd, Louisville, KY 40291",
            "American Legion Post 28 Bonnie Sloan 1930 McDonald Ln, New Albany, IN 47150": "1930 McDonald Ln, New Albany, IN 47150",
            "Boondocks Bar and Grill 3850 KY-1494 Shepherdsville, KY  40165": "3850 KY-1494 Shepherdsville, KY 40165",
            "Volt Lounge at Caesars 11999 Casino Center Dr SE, Elizabeth, IN 47117": "11999 Casino Center Dr SE, Elizabeth, IN 47117",
            "NEW YEARS EVE@The Alibi Bar 115 E Poplar St, Corydon, IN 47112 NO COVER": "115 E Poplar St, Corydon, IN 47112",
            "Hosting Stevie Ray’s World Famous Tuesday Jam": "",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(extract_address(title), expected)

    def test_event_from_dict_keeps_gig_id_and_adds_fields(self) -> None:
        event = event_from_dict(
            {"date": "2026-11-07", "time": "8:00 pm", "title": "Two Lane Tavern 9702 Old Bardstown Rd, Louisville, KY 40291", "venue": "Two Lane Tavern"}
        )
        self.assertEqual(event.gig_id, "2026-11-07_two-lane-tavern")
        self.assertEqual(event.to_dict()["address"], "9702 Old Bardstown Rd, Louisville, KY 40291")
        self.assertEqual(event.to_dict()["end_time"], "")

    def test_city_state(self) -> None:
        self.assertEqual(city_state("9702 Old Bardstown Rd, Louisville, KY 40291"), "Louisville, KY")
        self.assertEqual(city_state("3850 KY-1494 Shepherdsville, KY 40165"), "")


class FormatTests(unittest.TestCase):
    def test_parse_clock(self) -> None:
        self.assertEqual(parse_clock("8:00 pm"), time(20, 0))
        self.assertEqual(parse_clock("12:00 am"), time(0, 0))
        self.assertEqual(parse_clock("12:30 PM"), time(12, 30))
        self.assertEqual(parse_clock("7 pm"), time(19, 0))
        self.assertIsNone(parse_clock(""))

    def test_fmt_range(self) -> None:
        base = datetime(2026, 11, 7, 18, 0)
        self.assertEqual(fmt_range(base, base + timedelta(hours=4)), "6:00–10:00 PM")
        self.assertEqual(fmt_range(base + timedelta(hours=2), base + timedelta(hours=6)), "8:00 PM–12:00 AM")
        self.assertEqual(fmt_range(base + timedelta(hours=6), base + timedelta(hours=7)), "12:00–1:00 AM")
        self.assertEqual(fmt_range(base, None), "6:00 PM")


class DriveTimeTests(unittest.TestCase):
    def test_round_up_to_5(self) -> None:
        self.assertEqual(round_up_to_5(22 * 60), 25)
        self.assertEqual(round_up_to_5(25 * 60), 25)
        self.assertEqual(round_up_to_5(25 * 60 + 1), 30)

    def test_google_prefers_traffic_duration_and_sends_departure(self) -> None:
        urls = []

        def fake_get(url):
            urls.append(url)
            return {
                "status": "OK",
                "rows": [{"elements": [{"status": "OK", "duration": {"value": 1500}, "duration_in_traffic": {"value": 1980}}]}],
            }

        departure = datetime.now() + timedelta(days=1)
        minutes = google_drive_minutes("Home", "Venue", departure, api_key="k", http_get=fake_get)
        self.assertEqual(minutes, 35)
        self.assertIn("departure_time=", urls[0])

    def test_google_failures_return_none(self) -> None:
        self.assertIsNone(google_drive_minutes("Home", "Venue", api_key="", http_get=lambda u: {}))
        self.assertIsNone(
            google_drive_minutes("Home", "Venue", api_key="k", http_get=lambda u: {"status": "OK", "rows": [{"elements": [{"status": "NOT_FOUND"}]}]})
        )

        def boom(url):
            raise OSError("offline")

        self.assertIsNone(google_drive_minutes("Home", "Venue", api_key="k", http_get=boom))

    def test_query_reports_google_status_and_error(self) -> None:
        denied = query_distance_matrix(
            "Home",
            "Venue",
            api_key="k",
            http_get=lambda u: {"status": "REQUEST_DENIED", "error_message": "This API is not activated", "rows": []},
        )
        self.assertEqual((denied.minutes, denied.status, denied.error_message), (None, "REQUEST_DENIED", "This API is not activated"))
        self.assertEqual(query_distance_matrix("Home", "Venue", api_key="").status, "NO_API_KEY")
        self.assertEqual(query_distance_matrix("", "Venue", api_key="k").status, "NO_HOME_ADDRESS")
        empty = query_distance_matrix("Home", "Venue", api_key="k", http_get=lambda u: {"status": "OK", "rows": []})
        self.assertEqual(empty.status, "NO_ROUTE")

    def test_successful_lookups_are_cached(self) -> None:
        calls = []

        def fake_get(url):
            calls.append(url)
            return {"status": "OK", "rows": [{"elements": [{"status": "OK", "duration": {"value": 1200}}]}]}

        with patch.dict(drive_time._cache, clear=True):
            departure = datetime(2030, 1, 5, 18, 10)
            self.assertEqual(google_drive_minutes("Home", "Cached Venue", departure, api_key="k", http_get=fake_get), 20)
            self.assertEqual(google_drive_minutes("Home", "Cached Venue", departure, api_key="k", http_get=fake_get), 20)
        self.assertEqual(len(calls), 1)

    @patch.dict(os.environ, {"BAND_HOME_ADDRESS": "Home"})
    def test_resolve_order(self) -> None:
        config = load_config()
        profiled = config.match_venue("The Alibi Bar 115 E Poplar St, Corydon, IN 47112")
        self.assertEqual(resolve_drive(profiled, "x", lookup=lambda *a: 99).minutes, 45)
        unknown = config.profile_for("New Place 1 Main St, Town, KY 40000", "New Place")
        google = resolve_drive(unknown, "x", lookup=lambda *a: 20)
        self.assertEqual((google.minutes, google.source, google.confirmed), (20, "Google Maps", True))
        fallback = resolve_drive(unknown, "x", lookup=lambda *a: None)
        self.assertEqual((fallback.minutes, fallback.confirmed), (45, False))


class ConfigTests(unittest.TestCase):
    def test_defaults_and_matching(self) -> None:
        config = load_config()
        self.assertEqual(config.defaults["gig_length_minutes"], 240)
        self.assertTrue(config.is_excluded("Hosting Stevie Ray&#8217;s World Famous Tuesday Jam"))
        self.assertFalse(config.is_excluded("Two Lane Tavern 9702 Old Bardstown Rd"))
        self.assertEqual(config.match_venue("Rowdy’s Dance Hall & Saloon 101 Fairfield Hill Road").key, "rowdys")
        self.assertIsNone(config.match_venue("Fraternal Order of Eagles 201 Outerloop Lou Ky 40214"))
        self.assertEqual(config.match_venue("Fraternal Order of Eagles 3501 College Drive").key, "eagles_jeffersontown")


if __name__ == "__main__":
    unittest.main()
