#!/usr/bin/env python3
"""Tests for calendar disk cache and stale fallback."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gig_calendar import (  # noqa: E402
    CalendarUnavailableError,
    GigEvent,
    _save_disk_cache,
    get_all_events,
    get_cache_info,
    set_test_mode,
)


SAMPLE_HTML = """
<article class="mec-event-article mec-clear">
  <span class="mec-start-date-label">Jul 25 2026</span>
  <h3 class="mec-event-title"><a href="#">Lindsey Lane Band at King's Landing</a></h3>
  <span class="mec-start-time">8:00 pm</span>
</article>
<article class="mec-event-article mec-clear">
  <span class="mec-start-date-label">Jul 25 2026</span>
  <h3 class="mec-event-title"><a href="#">Lindsey Lane Band at King's Landing</a></h3>
  <span class="mec-start-time">8:00 pm</span>
</article>
"""


class CalendarCacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.cache_path = self.tmp_path / "calendar.json"
        set_test_mode(False)
        self.patches = [
            patch.dict(
                "os.environ",
                {
                    "GIG_CALENDAR_CACHE_PATH": str(self.cache_path),
                    "GIG_CALENDAR_CACHE_TTL_SECONDS": "3600",
                },
                clear=False,
            ),
            patch("gig_calendar.is_test_mode", return_value=False),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in self.patches:
            p.stop()
        set_test_mode(False)
        self.tmp.cleanup()

    def _sample_events(self) -> list[GigEvent]:
        event = GigEvent(
            event_date=date(2026, 7, 25),
            time_label="8:00 pm",
            title="Lindsey Lane Band at King's Landing",
            venue="King's Landing",
            suggested_name="Jul 25 King's Landing",
        )
        return [event]

    def test_disk_cache_hit_avoids_fetch(self) -> None:
        url = "https://example.com/dates/"
        _save_disk_cache(url, self._sample_events(), time.time())
        with patch("gig_calendar._fetch_calendar_html") as mock_fetch:
            events = get_all_events(force_refresh=False, calendar_url=url, background_refresh=False)
        mock_fetch.assert_not_called()
        self.assertEqual(len(events), 1)
        self.assertEqual(get_cache_info().source, "disk")

    def test_stale_fallback_on_fetch_failure(self) -> None:
        url = "https://example.com/dates/"
        stale_at = time.time() - 99999
        _save_disk_cache(url, self._sample_events(), stale_at)
        with patch("gig_calendar._fetch_calendar_html", side_effect=TimeoutError("timed out")):
            events = get_all_events(force_refresh=True, calendar_url=url, allow_stale=True)
        self.assertEqual(len(events), 1)
        info = get_cache_info()
        self.assertTrue(info.is_stale)
        self.assertEqual(info.source, "stale_disk")

    def test_no_cache_fetch_failure_raises(self) -> None:
        url = "https://example.com/dates/"
        with patch("gig_calendar._fetch_calendar_html", side_effect=TimeoutError("timed out")):
            with self.assertRaises(CalendarUnavailableError):
                get_all_events(force_refresh=True, calendar_url=url, allow_stale=True)

    def test_live_fetch_writes_disk_cache(self) -> None:
        url = "https://example.com/dates/"
        with patch("gig_calendar._fetch_calendar_html", return_value=SAMPLE_HTML):
            events = get_all_events(force_refresh=True, calendar_url=url)
        self.assertEqual(len(events), 1)
        self.assertTrue(self.cache_path.is_file())
        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["event_count"], 1)
        self.assertEqual(get_cache_info().source, "live")


if __name__ == "__main__":
    unittest.main(verbosity=2)
