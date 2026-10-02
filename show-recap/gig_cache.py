#!/usr/bin/env python3
"""
Gig Cache - Persist gig calendar events locally.

The band's public calendar only shows future events - past gigs are removed.
This cache stores all events we've ever seen, so we can match recordings
to past shows even after they're removed from the website.
"""

import json
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict

# Add setloader to path for gig_calendar access
sys.path.insert(0, str(Path(__file__).parent.parent / "setloader"))

try:
    from gig_calendar import get_all_events, get_local_today, GigEvent
    GIG_CALENDAR_AVAILABLE = True
except ImportError:
    GIG_CALENDAR_AVAILABLE = False

DEFAULT_CACHE_FILE = Path.home() / ".show-recap-gigs.json"


class GigCache:
    """
    Cache gig calendar events locally.
    
    Fetches from the live calendar and merges with cached events,
    preserving past events that have been removed from the website.
    """
    
    def __init__(self, cache_file: Path = None):
        self.cache_file = cache_file or DEFAULT_CACHE_FILE
        self.events: Dict[str, dict] = {}  # date+venue -> event info
        self._load()
    
    def _event_key(self, event_date: str, venue: str) -> str:
        """Create a unique key for an event."""
        return f"{event_date}|{venue}"
    
    def _load(self):
        """Load cached events from file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.events = data.get("events", {})
                print(f"[GIG CACHE] Loaded {len(self.events)} cached events")
            except Exception as e:
                print(f"[GIG CACHE] Failed to load cache: {e}")
                self.events = {}
    
    def _save(self):
        """Save events to cache file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump({
                    "events": self.events,
                    "last_updated": datetime.now().isoformat(),
                }, f, indent=2)
        except Exception as e:
            print(f"[GIG CACHE] Failed to save cache: {e}")
    
    def refresh_from_calendar(self) -> int:
        """
        Fetch events from the live calendar and merge with cache.
        
        Returns:
            Number of new events added
        """
        if not GIG_CALENDAR_AVAILABLE:
            print("[GIG CACHE] Calendar module not available")
            return 0
        
        try:
            live_events = get_all_events(force_refresh=True)
            new_count = 0
            
            for e in live_events:
                key = self._event_key(e.event_date.isoformat(), e.venue)
                if key not in self.events:
                    self.events[key] = {
                        "date": e.event_date.isoformat(),
                        "venue": e.venue,
                        "title": e.title,
                        "suggested_name": e.suggested_name,
                        "time": e.time_label,
                        "added_to_cache": datetime.now().isoformat(),
                    }
                    new_count += 1
            
            if new_count > 0:
                print(f"[GIG CACHE] Added {new_count} new events to cache")
                self._save()
            
            return new_count
        
        except Exception as e:
            print(f"[GIG CACHE] Failed to refresh: {e}")
            return 0
    
    def get_all_events(self) -> List[dict]:
        """Get all cached events, sorted by date."""
        events = list(self.events.values())
        events.sort(key=lambda e: e.get("date", ""), reverse=True)
        return events
    
    def get_past_events(self, days_back: int = 30) -> List[dict]:
        """Get past events within the specified number of days."""
        today = get_local_today() if GIG_CALENDAR_AVAILABLE else date.today()
        cutoff = today - timedelta(days=days_back)
        
        past = []
        for e in self.events.values():
            try:
                event_date = date.fromisoformat(e.get("date", ""))
                if cutoff <= event_date <= today:
                    past.append(e)
            except:
                continue
        
        past.sort(key=lambda e: e.get("date", ""), reverse=True)
        return past
    
    def get_most_recent_past_gig(self, days_back: int = 30) -> Optional[dict]:
        """Get the most recent past gig."""
        past = self.get_past_events(days_back)
        return past[0] if past else None
    
    def add_manual_event(self, event_date: str, venue: str, suggested_name: str = None):
        """Manually add an event to the cache."""
        key = self._event_key(event_date, venue)
        self.events[key] = {
            "date": event_date,
            "venue": venue,
            "title": venue,
            "suggested_name": suggested_name or f"{event_date} {venue}",
            "time": "",
            "added_to_cache": datetime.now().isoformat(),
            "manual": True,
        }
        self._save()
        print(f"[GIG CACHE] Added manual event: {event_date} {venue}")
    
    def list_events(self, limit: int = 20):
        """Print a list of cached events."""
        today = get_local_today() if GIG_CALENDAR_AVAILABLE else date.today()
        events = self.get_all_events()[:limit]
        
        print(f"\nCached Gigs ({len(self.events)} total):\n")
        for e in events:
            try:
                event_date = date.fromisoformat(e.get("date", ""))
                if event_date < today:
                    status = "PAST"
                elif event_date == today:
                    status = "TODAY"
                else:
                    status = "FUTURE"
            except:
                status = "?"
            
            print(f"  {e.get('date')} [{status:6}] {e.get('venue')}")
            print(f"           -> {e.get('suggested_name')}")


# Singleton instance
_cache: Optional[GigCache] = None

def get_gig_cache() -> GigCache:
    """Get the global gig cache instance."""
    global _cache
    if _cache is None:
        _cache = GigCache()
    return _cache


def get_most_recent_past_gig(days_back: int = 30) -> Optional[dict]:
    """
    Get the most recent past gig, refreshing from calendar first.
    
    This is the main function to use for auto-detecting show info.
    """
    cache = get_gig_cache()
    cache.refresh_from_calendar()
    return cache.get_most_recent_past_gig(days_back)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage gig cache")
    parser.add_argument("--refresh", action="store_true", help="Refresh from calendar")
    parser.add_argument("--list", action="store_true", help="List cached events")
    parser.add_argument("--recent", action="store_true", help="Show most recent past gig")
    parser.add_argument("--add", nargs=2, metavar=("DATE", "VENUE"), help="Add manual event")
    parser.add_argument("--days", type=int, default=30, help="Days back to search")
    
    args = parser.parse_args()
    cache = get_gig_cache()
    
    if args.refresh:
        cache.refresh_from_calendar()
    
    if args.add:
        cache.add_manual_event(args.add[0], args.add[1])
    
    if args.list:
        cache.list_events()
    
    if args.recent:
        gig = cache.get_most_recent_past_gig(args.days)
        if gig:
            print(f"\nMost recent past gig:")
            print(f"  Date: {gig.get('date')}")
            print(f"  Venue: {gig.get('venue')}")
            print(f"  Suggested name: {gig.get('suggested_name')}")
        else:
            print(f"\nNo past gigs found in last {args.days} days")
            print("You can add one manually:")
            print("  python gig_cache.py --add 2026-09-06 'The Dock'")
