#!/usr/bin/env python3
"""
Notifier - Send notifications to band members about processed shows.

Supports:
    - SMS via Twilio
    - Email (future)
    - Slack (future)

Requires:
    - TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER env vars
    - pip install twilio
"""

import os
from typing import List, Dict, Optional

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False


class Notifier:
    """Send notifications about processed shows."""
    
    def __init__(
        self,
        twilio_sid: str = None,
        twilio_token: str = None,
        twilio_from: str = None,
        band_members: List[Dict[str, str]] = None,
    ):
        """
        Initialize the notifier.
        
        Args:
            twilio_sid: Twilio account SID (or TWILIO_ACCOUNT_SID env)
            twilio_token: Twilio auth token (or TWILIO_AUTH_TOKEN env)
            twilio_from: Twilio phone number to send from (or TWILIO_FROM_NUMBER env)
            band_members: List of band members with 'name' and 'phone' keys
        """
        self.twilio_sid = twilio_sid or os.environ.get("TWILIO_ACCOUNT_SID")
        self.twilio_token = twilio_token or os.environ.get("TWILIO_AUTH_TOKEN")
        self.twilio_from = twilio_from or os.environ.get("TWILIO_FROM_NUMBER")
        self.band_members = band_members or []
        
        self.twilio = None
        if TWILIO_AVAILABLE and self.twilio_sid and self.twilio_token:
            self.twilio = TwilioClient(self.twilio_sid, self.twilio_token)
            print(f"[NOTIFIER] Twilio initialized")
        elif not TWILIO_AVAILABLE:
            print("[NOTIFIER] Warning: twilio package not installed")
        else:
            print("[NOTIFIER] Warning: Twilio credentials not configured")
    
    @property
    def sms_available(self) -> bool:
        """Check if SMS is available."""
        return self.twilio is not None and self.twilio_from is not None
    
    def load_band_members_from_env(self):
        """
        Load band members from environment variables.
        
        Format: BAND_MEMBERS="Name1:+1234567890,Name2:+0987654321"
        """
        members_str = os.environ.get("BAND_MEMBERS", "")
        if not members_str:
            return
        
        for entry in members_str.split(","):
            if ":" in entry:
                name, phone = entry.strip().split(":", 1)
                self.band_members.append({
                    "name": name.strip(),
                    "phone": phone.strip(),
                })
        
        if self.band_members:
            print(f"[NOTIFIER] Loaded {len(self.band_members)} band members from env")
    
    def send_sms(self, to_number: str, message: str) -> bool:
        """
        Send an SMS message.
        
        Args:
            to_number: Phone number to send to (E.164 format: +1234567890)
            message: Message text
            
        Returns:
            True if sent successfully
        """
        if not self.sms_available:
            print(f"[NOTIFIER] SMS not available, would send to {to_number}:")
            print(f"  {message}")
            return False
        
        try:
            msg = self.twilio.messages.create(
                body=message,
                from_=self.twilio_from,
                to=to_number,
            )
            print(f"[NOTIFIER] SMS sent to {to_number}: {msg.sid}")
            return True
        
        except Exception as e:
            print(f"[NOTIFIER] Failed to send SMS to {to_number}: {e}")
            return False
    
    def notify_band(
        self,
        show_name: str,
        show_date: str,
        share_link: str,
        set_count: int,
    ) -> int:
        """
        Notify all band members about a processed show.
        
        Args:
            show_name: Name of the show/venue
            show_date: Date of the show
            share_link: Dropbox share link
            set_count: Number of sets
            
        Returns:
            Number of notifications sent successfully
        """
        message = self._format_message(show_name, show_date, share_link, set_count)
        
        sent = 0
        for member in self.band_members:
            name = member.get("name", "Unknown")
            phone = member.get("phone")
            
            if not phone:
                continue
            
            print(f"[NOTIFIER] Notifying {name}...")
            if self.send_sms(phone, message):
                sent += 1
        
        return sent
    
    def _format_message(
        self,
        show_name: str,
        show_date: str,
        share_link: str,
        set_count: int,
    ) -> str:
        """Format the notification message."""
        sets_text = "set" if set_count == 1 else "sets"
        
        return (
            f"🎸 Show Recap Ready!\n\n"
            f"{show_name} ({show_date})\n"
            f"{set_count} {sets_text} processed\n\n"
            f"Listen here:\n{share_link}"
        )
    
    def test_notification(self, phone: str = None):
        """Send a test notification."""
        phone = phone or (self.band_members[0].get("phone") if self.band_members else None)
        
        if not phone:
            print("[NOTIFIER] No phone number to test with")
            return
        
        message = "🎸 Test notification from Show Recap!"
        self.send_sms(phone, message)


if __name__ == "__main__":
    import sys
    
    notifier = Notifier()
    notifier.load_band_members_from_env()
    
    if len(sys.argv) > 1:
        # Send test to provided number
        notifier.test_notification(sys.argv[1])
    else:
        print("Usage: python notifier.py <phone_number>")
        print("  Sends a test notification")
        print()
        print("Environment variables:")
        print("  TWILIO_ACCOUNT_SID - Twilio account SID")
        print("  TWILIO_AUTH_TOKEN - Twilio auth token")
        print("  TWILIO_FROM_NUMBER - Your Twilio phone number")
        print("  BAND_MEMBERS - Comma-separated name:phone pairs")
