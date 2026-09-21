#!/usr/bin/env python3
"""
Auto Recap - Automated show processing pipeline.

Watches for USB drives with A&H Qu-16 recordings, processes them into
set MP3s, uploads to Dropbox, and notifies band members.

Usage:
    python auto_recap.py                    # Watch for USB drives
    python auto_recap.py --process-now      # Process currently mounted drive
    python auto_recap.py --volume /Volumes/NO\ NAME  # Process specific volume
    
Environment Variables:
    ACRCLOUD_KEY, ACRCLOUD_SECRET      - For break music detection
    DROPBOX_ACCESS_TOKEN               - For Dropbox upload
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER - For SMS
    BAND_MEMBERS                       - "Name1:+1234567890,Name2:+0987654321"
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

from usb_watcher import USBWatcher, QuSession, ProcessingHistory
from cli import process_recording
from dropbox_uploader import DropboxUploader
from notifier import Notifier


class AutoRecap:
    """Automated show processing pipeline."""
    
    def __init__(
        self,
        output_base: Path = None,
        detect_breaks: bool = True,
        skip_start: float = 3600,  # Skip first hour by default
        left_track: int = 17,
        right_track: int = 18,
        silence_threshold: float = -30,
        min_break: float = 60,
        min_set: float = 1800,  # 30 min minimum set
        pad_start: float = 8,
        pad_end: float = 3,
    ):
        """
        Initialize the auto recap pipeline.
        
        Args:
            output_base: Base directory for output files
            detect_breaks: Use ACRCloud to detect break music
            skip_start: Seconds to skip from start (pre-show)
            left_track: Track number for left channel (default: 17)
            right_track: Track number for right channel (default: 18)
            silence_threshold: dB threshold for silence detection
            min_break: Minimum break duration in seconds
            min_set: Minimum set duration in seconds
            pad_start: Padding before each set
            pad_end: Padding after each set
        """
        self.output_base = output_base or Path.home() / "Music" / "Show Recaps"
        self.detect_breaks = detect_breaks
        self.skip_start = skip_start
        self.left_track = left_track
        self.right_track = right_track
        self.silence_threshold = silence_threshold
        self.min_break = min_break
        self.min_set = min_set
        self.pad_start = pad_start
        self.pad_end = pad_end
        
        # Initialize components
        self.history = ProcessingHistory()
        self.watcher = USBWatcher(history=self.history)
        self.uploader = DropboxUploader()
        self.notifier = Notifier()
        self.notifier.load_band_members_from_env()
        
        print(f"\n{'='*60}")
        print(f"  AUTO RECAP PIPELINE")
        print(f"{'='*60}")
        print(f"  Output: {self.output_base}")
        print(f"  Stereo tracks: TRK{left_track} (L) + TRK{right_track} (R)")
        print(f"  Skip start: {skip_start/60:.0f} minutes")
        print(f"  Break detection: {'Enabled' if detect_breaks else 'Disabled'}")
        print(f"  Dropbox: {'Ready' if self.uploader.available else 'Not configured'}")
        print(f"  SMS: {'Ready' if self.notifier.sms_available else 'Not configured'}")
        print(f"{'='*60}\n")
    
    def process_session(
        self,
        session: QuSession,
        show_name: str = None,
        show_date: str = None,
        force: bool = False,
    ) -> dict:
        """
        Process a recording session.
        
        Args:
            session: QuSession to process
            show_name: Override show name (default: use session folder name)
            show_date: Override date (default: use session date)
            force: Process even if already processed
            
        Returns:
            Dict with processing results
        """
        # Check if already processed
        if not force and self.history.is_processed(session):
            info = self.history.get_info(session)
            print(f"\n[SKIP] Session already processed:")
            print(f"  Folder: {session.name}")
            print(f"  Fingerprint: {session.fingerprint[:8]}...")
            print(f"  Previously processed as: {info.get('show_name')}")
            print(f"  Output: {info.get('output_dir')}")
            print(f"  Use --force to reprocess")
            return {"success": False, "error": "Already processed", "skipped": True}
        
        # Determine show name and date
        show_name = show_name or self._parse_show_name(session.name)
        show_date = show_date or (
            session.recording_date.strftime("%Y-%m-%d") 
            if session.recording_date 
            else datetime.now().strftime("%Y-%m-%d")
        )
        
        print(f"\n{'#'*60}")
        print(f"  PROCESSING: {show_name}")
        print(f"  Date: {show_date}")
        print(f"  Session: {session.name} [fp:{session.fingerprint[:8]}]")
        print(f"{'#'*60}\n")
        
        # Get stereo pair
        pair = session.get_stereo_pair(self.left_track, self.right_track)
        if not pair:
            print("Error: Could not find stereo pair tracks")
            return {"success": False, "error": "No stereo pair found"}
        
        left_file, right_file = pair
        print(f"Using tracks: {left_file.name} (L), {right_file.name} (R)")
        
        # Setup output directory
        output_dir = self.output_base / f"{show_date} - {show_name}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Run processing
        result = process_recording(
            file_paths=[str(left_file), str(right_file)],
            show_name=show_name,
            show_date=show_date,
            output_dir=str(output_dir),
            silence_threshold_db=self.silence_threshold,
            min_silence_duration=self.min_break,
            min_set_duration=self.min_set,
            skip_start=self.skip_start,
            pad_start=self.pad_start,
            pad_end=self.pad_end,
            detect_breaks=self.detect_breaks,
        )
        
        if result != 0:
            return {"success": False, "error": "Processing failed"}
        
        # Find output MP3s
        mp3_files = list(output_dir.glob("*.mp3"))
        
        # Mark session as processed
        self.history.mark_processed(session, show_name, str(output_dir))
        
        return {
            "success": True,
            "show_name": show_name,
            "show_date": show_date,
            "output_dir": output_dir,
            "mp3_files": mp3_files,
            "set_count": len(mp3_files),
            "session": session,
        }
    
    def upload_and_notify(self, result: dict) -> dict:
        """
        Upload processed files and notify band.
        
        Args:
            result: Processing result from process_session
            
        Returns:
            Updated result with upload info
        """
        if not result.get("success"):
            return result
        
        show_name = result["show_name"]
        show_date = result["show_date"]
        mp3_files = result["mp3_files"]
        
        # Upload to Dropbox
        if self.uploader.available and mp3_files:
            print(f"\n[UPLOAD] Uploading to Dropbox...")
            
            links = self.uploader.upload_show(mp3_files, show_name, show_date)
            result["dropbox_links"] = links
            
            # Get folder link
            folder_link = self.uploader.create_folder_link(show_name, show_date)
            result["folder_link"] = folder_link
            
            if folder_link:
                print(f"\n[UPLOAD] Share link: {folder_link}")
        else:
            result["dropbox_links"] = {}
            result["folder_link"] = None
        
        # Notify band
        folder_link = result.get("folder_link")
        if folder_link and self.notifier.band_members:
            print(f"\n[NOTIFY] Notifying band members...")
            
            sent = self.notifier.notify_band(
                show_name=show_name,
                show_date=show_date,
                share_link=folder_link,
                set_count=result["set_count"],
            )
            result["notifications_sent"] = sent
        else:
            result["notifications_sent"] = 0
        
        return result
    
    def process_volume(self, volume: Path, show_name: str = None, force: bool = False, process_all: bool = False) -> list:
        """
        Process sessions on a volume.
        
        Args:
            volume: Volume path to scan
            show_name: Override show name for all sessions
            force: Process even if already processed
            process_all: Process all unprocessed sessions (not just newest)
            
        Returns:
            List of processing results
        """
        sessions = self.watcher.find_qu_recordings(volume)
        
        if not sessions:
            print(f"No Qu-16 recordings found on {volume}")
            return []
        
        # Show what's available
        print(f"\nFound {len(sessions)} session(s) on {volume.name}:")
        for s in sessions:
            is_processed = self.history.is_processed(s)
            status = " [PROCESSED]" if is_processed else " [NEW]"
            print(f"  - {s}{status}")
        print()
        
        # Filter to unprocessed unless force
        if not force:
            to_process = [s for s in sessions if not self.history.is_processed(s)]
        else:
            to_process = sessions
        
        if not to_process:
            print("All sessions already processed. Use --force to reprocess.")
            return []
        
        results = []
        for session in to_process:
            result = self.process_session(session, show_name=show_name, force=force)
            if result.get("success"):
                result = self.upload_and_notify(result)
            results.append(result)
            
            if not process_all:
                break  # Just process first (most recent unprocessed) session
        
        return results
    
    def on_usb_detected(self, volume: Path, sessions: list):
        """Callback when USB with recordings is detected."""
        print(f"\n{'*'*60}")
        print(f"  USB DETECTED: {volume.name}")
        print(f"  Found {len(sessions)} recording session(s)")
        print(f"{'*'*60}\n")
        
        # Process the most recent session
        if sessions:
            session = sessions[0]  # Most recent
            print(f"Processing most recent: {session}")
            
            result = self.process_session(session)
            result = self.upload_and_notify(result)
            
            self._print_summary(result)
    
    def watch(self):
        """Watch for USB drives and process automatically."""
        self.watcher.watch(self.on_usb_detected)
    
    def _parse_show_name(self, session_name: str) -> str:
        """Parse show name from session folder name."""
        # A&H Qu-16 session names are often like "Session001"
        # Try to make a better name
        if session_name.lower().startswith("session"):
            return "Live Show"
        return session_name.replace("_", " ").replace("-", " ")
    
    def _print_summary(self, result: dict):
        """Print processing summary."""
        print(f"\n{'='*60}")
        print(f"  PROCESSING COMPLETE")
        print(f"{'='*60}")
        
        if result.get("success"):
            print(f"  Show: {result['show_name']}")
            print(f"  Date: {result['show_date']}")
            print(f"  Sets: {result['set_count']}")
            print(f"  Output: {result['output_dir']}")
            
            if result.get("folder_link"):
                print(f"  Dropbox: {result['folder_link']}")
            
            if result.get("notifications_sent"):
                print(f"  Notifications: {result['notifications_sent']} sent")
        else:
            print(f"  Error: {result.get('error', 'Unknown error')}")
        
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Automated show recap processing pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  ACRCLOUD_KEY, ACRCLOUD_SECRET    - Break music detection
  DROPBOX_ACCESS_TOKEN             - Dropbox upload
  TWILIO_ACCOUNT_SID               - SMS notifications
  TWILIO_AUTH_TOKEN
  TWILIO_FROM_NUMBER
  BAND_MEMBERS                     - "Name:+1234567890,Name2:+0987654321"

Examples:
  %(prog)s                         # Watch for USB drives
  %(prog)s --volume "/Volumes/NO NAME"  # Process specific drive
  %(prog)s --scan-now              # Scan all mounted drives
        """
    )
    
    parser.add_argument("--volume", "-v", type=str,
                       help="Process a specific volume")
    parser.add_argument("--scan-now", action="store_true",
                       help="Scan currently mounted drives")
    parser.add_argument("--show-name", "-n", type=str,
                       help="Override show name")
    parser.add_argument("--skip-start", type=float, default=3600,
                       help="Seconds to skip from start (default: 3600)")
    parser.add_argument("--no-detect-breaks", action="store_true",
                       help="Disable ACRCloud break detection")
    parser.add_argument("--left-track", type=int, default=17,
                       help="Left channel track number (default: 17)")
    parser.add_argument("--right-track", type=int, default=18,
                       help="Right channel track number (default: 18)")
    parser.add_argument("--output", "-o", type=str,
                       help="Output base directory")
    parser.add_argument("--force", "-f", action="store_true",
                       help="Process even if session was already processed")
    parser.add_argument("--all", "-a", action="store_true",
                       help="Process all unprocessed sessions (not just newest)")
    parser.add_argument("--show-history", action="store_true",
                       help="Show processing history and exit")
    parser.add_argument("--clear-history", action="store_true",
                       help="Clear processing history")
    
    args = parser.parse_args()
    
    # Handle history commands first (before pipeline init)
    if args.show_history or args.clear_history:
        from usb_watcher import ProcessingHistory
        history = ProcessingHistory()
        
        if args.clear_history:
            history.clear()
            print("Processing history cleared.")
            return 0
        
        if args.show_history:
            if not history.processed:
                print("No sessions have been processed yet.")
            else:
                print(f"Processing History ({len(history.processed)} sessions):\n")
                for fp, info in sorted(history.processed.items(), 
                                       key=lambda x: x[1].get('processed_at', ''), 
                                       reverse=True):
                    print(f"  {info.get('show_name', 'Unknown')} ({info.get('recording_date', '?')})")
                    print(f"    Folder: {info.get('folder_name')}")
                    print(f"    Processed: {info.get('processed_at', '?')}")
                    print(f"    Output: {info.get('output_dir')}")
                    print(f"    Fingerprint: {fp[:8]}...")
                    print()
            return 0
    
    # Initialize pipeline
    pipeline = AutoRecap(
        output_base=Path(args.output) if args.output else None,
        detect_breaks=not args.no_detect_breaks,
        skip_start=args.skip_start,
        left_track=args.left_track,
        right_track=args.right_track,
    )
    
    if args.volume:
        volume = Path(args.volume)
        if not volume.exists():
            print(f"Error: Volume not found: {volume}")
            return 1
        
        results = pipeline.process_volume(
            volume, 
            show_name=args.show_name,
            force=args.force,
            process_all=args.all,
        )
        for result in results:
            pipeline._print_summary(result)
        return 0
    
    if args.scan_now:
        results_by_volume = pipeline.watcher.scan_all_volumes()
        if not results_by_volume:
            print("No Qu-16 recordings found on any mounted drive")
            return 0
        
        for volume, sessions in results_by_volume.items():
            print(f"\n{volume.name}:")
            for s in sessions:
                is_processed = pipeline.history.is_processed(s)
                status = " [PROCESSED]" if is_processed else " [NEW]"
                print(f"  - {s}{status}")
        return 0
    
    # Default: watch for USB drives
    pipeline.watch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
