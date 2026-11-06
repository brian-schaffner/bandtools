#!/usr/bin/env python3
"""Tests for the Facebook Page events calendar source."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gig_calendar  # noqa: E402
from gig_calendar import (  # noqa: E402
    _parse_facebook_events,
    get_all_events,
    get_cache_info,
    set_test_mode,
)

TOKEN = "EAAsecret-page-token"

PAGE_ONE = {
    "data": [
        {
            "id": "1502409618320369",
            "name": "Ernie's Tavern Presents The Lindsey Lane Band",
            "start_time": "2027-08-21T19:00:00-0400",
            "place": {
                "name": "Ernie's Tavern",
                "id": "114223291936146",
                "location": {"street": "104 Taylorsville Rd", "city": "Bloomfield", "state": "KY", "zip": "40008"},
            },
        },
        {
            "id": "2674098246285278",
            "name": "The Shop Presents The Lindsey Lane",
            "start_time": "2026-12-19T20:30:00-0500",
            "place": {"name": "133 Christian Church Rd, Brandenburg, KY"},
        },
        {
            "id": "29384907494530929",
            "name": "Lindsey Lane Band at Red Mile Gaming & Racetrack ",
            "start_time": "2027-05-22T21:00:00-0400",
            "end_time": "2027-05-23T00:30:00-0400",
            "place": {"name": "Red Mile Events", "id": "204740322961798"},
        },
    ],
    "paging": {"next": "https://graph.facebook.com/v21.0/340876651205/events?after=abc&access_token=" + TOKEN},
}

PAGE_TWO = {
    "data": [
        {
            "id": "1618212279679861",
            "name": "Lindsey Lane Tuesday Jam",
            "start_time": "2026-10-20T19:30:00-0400",
            "place": {"name": "Stevie Ray's Blues Bar", "id": "121909464486557"},
            "event_times": [
                {"id": "a", "start_time": "2026-11-10T19:30:00-0500", "end_time": "2026-11-10T22:30:00-0500"},
                {"id": "b", "start_time": "2026-11-17T19:30:00-0500", "end_time": "2026-11-17T22:30:00-0500"},
            ],
        },
        {
            "id": "999",
            "name": "Cancelled Show",
            "start_time": "2026-11-28T20:00:00-0500",
            "is_canceled": True,
            "place": {"name": "Nowhere Bar"},
        },
    ],
    "paging": {"cursors": {"before": "x", "after": "y"}},
}


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


class FacebookParseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict("os.environ", {"GIG_CALENDAR_TIMEZONE": "America/Kentucky/Louisville"})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()

    def test_maps_fields_and_sorts_by_date(self) -> None:
        events = _parse_facebook_events(PAGE_ONE["data"] + PAGE_TWO["data"])
        self.assertEqual(
            [(e.event_date.isoformat(), e.venue) for e in events],
            [
                ("2026-11-10", "Stevie Ray's Blues Bar"),
                ("2026-11-17", "Stevie Ray's Blues Bar"),
                ("2026-12-19", "The Shop"),
                ("2027-05-22", "Red Mile Events"),
                ("2027-08-21", "Ernie's Tavern"),
            ],
        )
        ernies = events[-1]
        self.assertEqual(ernies.time_label, "7:00 pm")
        self.assertEqual(ernies.address, "104 Taylorsville Rd, Bloomfield, KY 40008")
        self.assertEqual(ernies.gig_id, "2027-08-21_ernie-s-tavern")
        self.assertEqual(ernies.suggested_name, "Aug 21 Ernie's Tavern")

    def test_address_only_place_uses_title_for_venue(self) -> None:
        shop = _parse_facebook_events(PAGE_ONE["data"])[0]
        self.assertEqual(shop.venue, "The Shop")
        self.assertEqual(shop.address, "133 Christian Church Rd, Brandenburg, KY")
        self.assertEqual(shop.time_label, "8:30 pm")

    def test_end_time_and_trailing_whitespace(self) -> None:
        red_mile = [e for e in _parse_facebook_events(PAGE_ONE["data"]) if e.venue == "Red Mile Events"][0]
        self.assertEqual(red_mile.title, "Lindsey Lane Band at Red Mile Gaming & Racetrack")
        self.assertEqual(red_mile.time_label, "9:00 pm")
        self.assertEqual(red_mile.end_time_label, "12:30 am")

    def test_recurring_expands_and_cancelled_skipped(self) -> None:
        events = _parse_facebook_events(PAGE_TWO["data"])
        self.assertEqual([e.event_date for e in events], [date(2026, 11, 10), date(2026, 11, 17)])
        self.assertTrue(all(e.end_time_label == "10:30 pm" for e in events))

    def test_converts_to_band_timezone(self) -> None:
        events = _parse_facebook_events([{"name": "Late Show at X", "start_time": "2026-11-21T04:30:00+0000"}])
        self.assertEqual(events[0].event_date, date(2026, 11, 20))
        self.assertEqual(events[0].time_label, "11:30 pm")


class FacebookSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.tmp.name) / "calendar.json"
        set_test_mode(False)
        gig_calendar._cache.update({"fetched_at": 0.0, "events": [], "url": None})
        self.env = patch.dict(
            "os.environ",
            {
                "GIG_CALENDAR_CACHE_PATH": str(self.cache_path),
                "GIG_CALENDAR_SOURCE": "facebook",
                "FACEBOOK_PAGE_ID": "340876651205",
                "FACEBOOK_PAGE_ACCESS_TOKEN": TOKEN,
            },
        )
        self.env.start()
        self.requested: list[str] = []

    def tearDown(self) -> None:
        self.env.stop()
        gig_calendar._cache.update({"fetched_at": 0.0, "events": [], "url": None})
        self.tmp.cleanup()

    def _fake_urlopen(self, request, timeout=None):
        url = request.full_url
        self.requested.append(url)
        payload = PAGE_TWO if "after=abc" in url else PAGE_ONE
        return _FakeResponse(json.dumps(payload).encode())

    def test_fetches_all_pages_and_caches(self) -> None:
        with patch("gig_calendar.urlopen", side_effect=self._fake_urlopen), patch(
            "gig_calendar._fetch_calendar_html"
        ) as website:
            events = get_all_events(force_refresh=True)
        website.assert_not_called()
        self.assertEqual(len(events), 5)
        self.assertEqual(len(self.requested), 2)
        query = parse_qs(urlparse(self.requested[0]).query)
        self.assertEqual(urlparse(self.requested[0]).path, "/v21.0/340876651205/events")
        self.assertEqual(query["time_filter"], ["upcoming"])
        self.assertEqual(query["access_token"], [TOKEN])
        self.assertEqual(get_cache_info().source, "live")
        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["url"], "facebook:340876651205")
        self.assertNotIn(TOKEN, self.cache_path.read_text(encoding="utf-8"))

    def test_graph_error_hides_token_and_falls_back_to_cache(self) -> None:
        with patch("gig_calendar.urlopen", side_effect=self._fake_urlopen):
            get_all_events(force_refresh=True)

        def _expired(request, timeout=None):
            body = json.dumps({"error": {"message": "Error validating access token: Session has expired"}})
            raise HTTPError(request.full_url, 400, "Bad Request", {}, io.BytesIO(body.encode()))

        with patch("gig_calendar.urlopen", side_effect=_expired):
            with self.assertRaises(OSError) as ctx:
                gig_calendar._fetch_facebook_events()
            self.assertIn("Session has expired", str(ctx.exception))
            self.assertNotIn(TOKEN, str(ctx.exception))
            self.assertIsNone(ctx.exception.__cause__)
            events = get_all_events(force_refresh=True, allow_stale=True)
        self.assertEqual(len(events), 5)
        self.assertEqual(get_cache_info().source, "stale_disk")

    def test_missing_credentials_uses_website(self) -> None:
        with patch.dict("os.environ", {"FACEBOOK_PAGE_ACCESS_TOKEN": ""}), patch(
            "gig_calendar._fetch_calendar_html", return_value=""
        ) as website, patch("gig_calendar.urlopen") as graph:
            get_all_events(force_refresh=True)
        website.assert_called_once_with(gig_calendar.DEFAULT_CALENDAR_URL)
        graph.assert_not_called()

    def test_website_is_default_source(self) -> None:
        with patch.dict("os.environ", {"GIG_CALENDAR_SOURCE": ""}), patch(
            "gig_calendar._fetch_calendar_html", return_value=""
        ) as website, patch("gig_calendar.urlopen") as graph:
            get_all_events(force_refresh=True)
        website.assert_called_once()
        graph.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
