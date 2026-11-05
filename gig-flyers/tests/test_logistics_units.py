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
from logistics.drive_time import google_drive_minutes, query_routes, resolve_drive, round_up_to_5  # noqa: E402
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

    def test_routes_request_and_traffic_duration(self) -> None:
        sent = []

        def fake_post(url, body, headers):
            sent.append((url, body, headers))
            return {"routes": [{"duration": "1980s", "staticDuration": "1500s"}]}

        departure = datetime(2030, 1, 5, 18, 10)
        minutes = google_drive_minutes("Home", "Venue", departure, api_key="k", http_post=fake_post)
        self.assertEqual(minutes, 35)
        url, body, headers = sent[0]
        self.assertEqual(url, "https://routes.googleapis.com/directions/v2:computeRoutes")
        self.assertEqual(body["origin"], {"address": "Home"})
        self.assertEqual(body["destination"], {"address": "Venue"})
        self.assertEqual(body["travelMode"], "DRIVE")
        self.assertEqual(body["routingPreference"], "TRAFFIC_AWARE")
        # 6:10 PM Eastern (EST in January) is 23:10 UTC regardless of the server's clock zone.
        self.assertEqual(body["departureTime"], "2030-01-05T23:10:00Z")
        self.assertEqual(headers["X-Goog-Api-Key"], "k")
        self.assertEqual(headers["X-Goog-FieldMask"], "routes.duration,routes.staticDuration")

    def test_past_departure_is_not_sent(self) -> None:
        sent = []

        def fake_post(url, body, headers):
            sent.append(body)
            return {"routes": [{"duration": "600s"}]}

        query_routes("Home", "Venue", datetime(2020, 1, 1, 12, 0), api_key="k", http_post=fake_post)
        self.assertNotIn("departureTime", sent[0])

    def test_google_failures_return_none(self) -> None:
        self.assertIsNone(google_drive_minutes("Home", "Venue", api_key="", http_post=lambda u, b, h: {}))
        self.assertIsNone(google_drive_minutes("Home", "Nowhere", api_key="k", http_post=lambda u, b, h: {}))

        def boom(url, body, headers):
            raise OSError("offline")

        self.assertIsNone(google_drive_minutes("Home", "Offline Venue", api_key="k", http_post=boom))

    def test_query_reports_google_status_and_error(self) -> None:
        denied = query_routes(
            "Home",
            "Venue",
            api_key="k",
            http_post=lambda u, b, h: {
                "error": {"code": 403, "status": "PERMISSION_DENIED", "message": "Routes API has not been used in project 123"}
            },
        )
        self.assertEqual(
            (denied.minutes, denied.status, denied.error_message),
            (None, "PERMISSION_DENIED", "Routes API has not been used in project 123"),
        )
        self.assertEqual(query_routes("Home", "Venue", api_key="").status, "NO_API_KEY")
        self.assertEqual(query_routes("", "Venue", api_key="k").status, "NO_HOME_ADDRESS")
        self.assertEqual(query_routes("Home", "Venue", api_key="k", http_post=lambda u, b, h: {}).status, "NO_ROUTE")

    def test_successful_lookups_are_cached(self) -> None:
        calls = []

        def fake_post(url, body, headers):
            calls.append(body)
            return {"routes": [{"duration": "1200s"}]}

        with patch.dict(drive_time._cache, clear=True):
            departure = datetime(2030, 1, 5, 18, 10)
            self.assertEqual(google_drive_minutes("Home", "Cached Venue", departure, api_key="k", http_post=fake_post), 20)
            self.assertEqual(google_drive_minutes("Home", "Cached Venue", departure, api_key="k", http_post=fake_post), 20)
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
