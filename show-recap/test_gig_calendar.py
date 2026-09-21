#!/usr/bin/env python3
"""Test harness for gig calendar integration."""

import sys
from pathlib import Path
from datetime import date, timedelta

# Add setloader to path
sys.path.insert(0, str(Path(__file__).parent.parent / "setloader"))

def test_gig_calendar():
    print("=" * 60)
    print("  GIG CALENDAR TEST HARNESS")
    print("=" * 60)
    
    # Test 1: Import
    print("\n[TEST 1] Importing gig_calendar module...")
    try:
        from gig_calendar import (
            get_all_events, 
            get_local_today, 
            get_gig_suggestions,
            DEFAULT_CALENDAR_URL,
        )
        print(f"  ✓ Import successful")
        print(f"  Calendar URL: {DEFAULT_CALENDAR_URL}")
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False
    
    # Test 2: Get local date
    print("\n[TEST 2] Getting local date...")
    try:
        today = get_local_today()
        print(f"  ✓ Today's date: {today}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        today = date.today()
        print(f"  Using fallback: {today}")
    
    # Test 3: Fetch all events
    print("\n[TEST 3] Fetching all events from calendar...")
    try:
        events = get_all_events(force_refresh=True)
        print(f"  ✓ Found {len(events)} events")
    except Exception as e:
        print(f"  ✗ Failed to fetch: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    if not events:
        print("  ⚠ No events found on calendar!")
        print("  Check if the calendar URL is correct and has events.")
        return False
    
    # Test 4: List all events
    print("\n[TEST 4] All events on calendar:")
    for e in events:
        past_future = "PAST" if e.event_date < today else "FUTURE" if e.event_date > today else "TODAY"
        print(f"  {e.event_date} [{past_future:6}] {e.venue}")
        print(f"           Suggested: {e.suggested_name}")
    
    # Test 5: Find past events
    print("\n[TEST 5] Past events (potential recordings):")
    past_events = [e for e in events if e.event_date <= today]
    if past_events:
        for e in sorted(past_events, key=lambda x: x.event_date, reverse=True)[:5]:
            days_ago = (today - e.event_date).days
            print(f"  {e.event_date} ({days_ago} days ago) - {e.venue}")
    else:
        print("  No past events found!")
        print("  All events are in the future.")
    
    # Test 6: Find events in last 7 days
    print("\n[TEST 6] Events in last 7 days:")
    week_ago = today - timedelta(days=7)
    recent = [e for e in events if week_ago <= e.event_date <= today]
    if recent:
        for e in recent:
            print(f"  {e.event_date} - {e.suggested_name}")
    else:
        print("  No events in last 7 days")
    
    # Test 7: Find events in last 30 days
    print("\n[TEST 7] Events in last 30 days:")
    month_ago = today - timedelta(days=30)
    recent_month = [e for e in events if month_ago <= e.event_date <= today]
    if recent_month:
        for e in recent_month:
            print(f"  {e.event_date} - {e.suggested_name}")
    else:
        print("  No events in last 30 days")
    
    # Test 8: Get gig suggestions API
    print("\n[TEST 8] Testing get_gig_suggestions()...")
    try:
        suggestions = get_gig_suggestions()
        print(f"  Target date: {suggestions.get('target_date')}")
        print(f"  Primary suggestion: {suggestions.get('primary_suggestion')}")
        print(f"  Note: {suggestions.get('note')}")
        print(f"  Events today: {len(suggestions.get('events', []))}")
        print(f"  Upcoming: {len(suggestions.get('upcoming', []))}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
    
    print("\n" + "=" * 60)
    print("  TEST COMPLETE")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_gig_calendar()
    sys.exit(0 if success else 1)
