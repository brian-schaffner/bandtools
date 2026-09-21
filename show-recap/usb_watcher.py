#!/usr/bin/env python3
"""
USB Watcher - Detect A&H Qu-16 multitrack recordings on USB drives.

Watches for new USB drive mounts and looks for:
- /Volumes/<DRIVE>/AHQU/USBMTK/ folder structure
- Large WAV files (1-4GB) indicating full show recordings

Usage:
    python usb_watcher.py              # Watch for USB drives
    python usb_watcher.py --scan-now   # Scan currently mounted drives
"""

import os
import sys
import time
import json
import hashlib
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

# Platform-specific volume paths
if sys.platform == "darwin":  # macOS
    VOLUMES_PATH = Path("/Volumes")
elif sys.platform == "linux":
    VOLUMES_PATH = Path("/media") / os.environ.get("USER", "ubuntu")
else:
    VOLUMES_PATH = Path("/mnt")

# A&H Qu-16 folder structure
AHQU_FOLDER = "AHQU"
USBMTK_FOLDER = "USBMTK"

# File size thresholds (in bytes)
MIN_SESSION_FILE_SIZE = 500 * 1024 * 1024   # 500 MB minimum
MIN_SHOW_TOTAL_SIZE = 1 * 1024 * 1024 * 1024  # 1 GB minimum total

# Default history file location
DEFAULT_HISTORY_FILE = Path.home() / ".show-recap-history.json"


class ProcessingHistory:
    """Track which sessions have been processed to avoid duplicates."""
    
    def __init__(self, history_file: Path = None):
        self.history_file = history_file or DEFAULT_HISTORY_FILE
        self.processed: Dict[str, dict] = {}  # fingerprint -> info
        self._load()
    
    def _load(self):
        """Load processing history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    self.processed = data.get("processed", {})
                print(f"[HISTORY] Loaded {len(self.processed)} processed sessions")
            except Exception as e:
                print(f"[HISTORY] Failed to load history: {e}")
                self.processed = {}
    
    def _save(self):
        """Save processing history to file."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump({"processed": self.processed}, f, indent=2)
        except Exception as e:
            print(f"[HISTORY] Failed to save history: {e}")
    
    def is_processed(self, session: 'QuSession') -> bool:
        """Check if a session has already been processed."""
        return session.fingerprint in self.processed
    
    def mark_processed(self, session: 'QuSession', show_name: str, output_dir: str):
        """Mark a session as processed."""
        self.processed[session.fingerprint] = {
            "folder_name": session.name,
            "show_name": show_name,
            "duration_estimate": session.duration_estimate,
            "processed_at": datetime.now().isoformat(),
            "output_dir": str(output_dir),
            "total_size_gb": round(session.total_size / (1024**3), 2),
            "track_count": len(session.wav_files),
        }
        self._save()
        print(f"[HISTORY] Marked as processed: {session.name} [{session.fingerprint[:8]}]")
    
    def get_info(self, session: 'QuSession') -> Optional[dict]:
        """Get processing info for a session if it was processed."""
        return self.processed.get(session.fingerprint)
    
    def clear(self):
        """Clear all processing history."""
        self.processed = {}
        self._save()
        print("[HISTORY] Cleared all processing history")


class QuSession:
    """Represents an A&H Qu-16 recording session."""
    
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.wav_files: List[Path] = []
        self.total_size = 0
        self.file_sizes: List[int] = []  # For fingerprinting
        self.fingerprint: str = ""  # Unique identifier for this session's content
        self._scan()
    
    def _scan(self):
        """Scan the session folder for WAV files."""
        for f in self.path.glob("*.WAV"):
            if f.is_file():
                size = f.stat().st_size
                self.wav_files.append(f)
                self.total_size += size
                self.file_sizes.append(size)
        
        # Also check lowercase
        for f in self.path.glob("*.wav"):
            if f.is_file() and f not in self.wav_files:
                size = f.stat().st_size
                self.wav_files.append(f)
                self.total_size += size
                self.file_sizes.append(size)
        
        # Sort by name for consistent channel ordering
        self.wav_files.sort(key=lambda x: x.name)
        self.file_sizes.sort()  # Sort for consistent fingerprint
        
        # Create fingerprint from file count + sizes (unique per actual recording)
        # Note: Qu-16 has no RTC so we can't use timestamps
        self._create_fingerprint()
    
    def _create_fingerprint(self):
        """Create a unique fingerprint for this session based on content."""
        # Combine: number of files + total size + individual file sizes
        # This uniquely identifies the recording even if folder name is reused
        fp_data = f"{len(self.wav_files)}:{self.total_size}:{','.join(map(str, self.file_sizes))}"
        self.fingerprint = hashlib.sha256(fp_data.encode()).hexdigest()[:16]
    
    @property
    def is_valid_show(self) -> bool:
        """Check if this looks like a full show recording."""
        # Need at least some WAV files
        if len(self.wav_files) < 2:
            return False
        
        # Total size should be substantial
        if self.total_size < MIN_SHOW_TOTAL_SIZE:
            return False
        
        # At least some files should be large (main mix tracks)
        large_files = [f for f in self.wav_files 
                       if f.stat().st_size >= MIN_SESSION_FILE_SIZE]
        if len(large_files) < 2:
            return False
        
        return True
    
    @property
    def duration_estimate(self) -> str:
        """Estimate recording duration from file sizes (rough: ~10MB/min for WAV)."""
        # Rough estimate: stereo 48kHz 24-bit WAV is about 17MB/min per track
        # Main mix tracks (17+18) together ~34MB/min
        largest_file = max(self.file_sizes) if self.file_sizes else 0
        minutes = largest_file / (17 * 1024 * 1024)  # Rough estimate
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        if hours > 0:
            return f"~{hours}h {mins}m"
        return f"~{mins}m"
    
    def get_stereo_pair(self, left_track: int = 17, right_track: int = 18) -> Optional[tuple]:
        """
        Get the stereo pair tracks (typically TRK17 and TRK18 for main mix).
        
        Returns:
            Tuple of (left_path, right_path) or None if not found
        """
        left_file = None
        right_file = None
        
        for f in self.wav_files:
            name = f.stem.upper()
            if f"TRK{left_track}" in name or f"TRACK{left_track}" in name:
                left_file = f
            elif f"TRK{right_track}" in name or f"TRACK{right_track}" in name:
                right_file = f
        
        if left_file and right_file:
            return (left_file, right_file)
        
        # Fallback: try to find the two largest files
        if len(self.wav_files) >= 2:
            sorted_by_size = sorted(self.wav_files, 
                                   key=lambda x: x.stat().st_size, 
                                   reverse=True)
            # Return the two largest, sorted by name for L/R consistency
            pair = sorted(sorted_by_size[:2], key=lambda x: x.name)
            return (pair[0], pair[1])
        
        return None
    
    def __str__(self):
        size_gb = self.total_size / (1024**3)
        return f"{self.name} ({len(self.wav_files)} tracks, {size_gb:.1f} GB, {self.duration_estimate}) [fp:{self.fingerprint[:8]}]"


class USBWatcher:
    """Watch for USB drives with A&H Qu-16 recordings."""
    
    def __init__(self, volumes_path: Path = VOLUMES_PATH, history: ProcessingHistory = None):
        self.volumes_path = volumes_path
        self.known_volumes: set = set()
        self.history = history or ProcessingHistory()
        self._update_known_volumes()
    
    def _update_known_volumes(self):
        """Update the set of currently known volumes."""
        if self.volumes_path.exists():
            self.known_volumes = set(self.volumes_path.iterdir())
    
    def _get_current_volumes(self) -> set:
        """Get currently mounted volumes."""
        if not self.volumes_path.exists():
            return set()
        return set(self.volumes_path.iterdir())
    
    def check_for_new_volumes(self) -> List[Path]:
        """Check for newly mounted volumes."""
        current = self._get_current_volumes()
        new_volumes = current - self.known_volumes
        self.known_volumes = current
        return list(new_volumes)
    
    def find_qu_recordings(self, volume: Path, include_processed: bool = True) -> List[QuSession]:
        """
        Find A&H Qu-16 recording sessions on a volume.
        
        Looks for: <volume>/AHQU/USBMTK/<session_folders>/
        
        Args:
            volume: Path to the mounted volume
            include_processed: If False, filter out already-processed sessions
        """
        sessions = []
        
        # Check for AHQU/USBMTK structure
        usbmtk_path = volume / AHQU_FOLDER / USBMTK_FOLDER
        
        if not usbmtk_path.exists():
            # Also try case variations
            for ahqu in volume.glob("[Aa][Hh][Qq][Uu]"):
                for usbmtk in ahqu.glob("[Uu][Ss][Bb][Mm][Tt][Kk]"):
                    usbmtk_path = usbmtk
                    break
        
        if not usbmtk_path.exists():
            return sessions
        
        # Scan session folders
        for item in usbmtk_path.iterdir():
            if item.is_dir():
                session = QuSession(item)
                if session.is_valid_show:
                    sessions.append(session)
        
        # Sort by folder name (Qu-16 has no RTC, so timestamps are unreliable)
        # QU-MT001, QU-MT002, etc. - higher number = more recent (usually)
        sessions.sort(key=lambda s: s.name)
        
        # Optionally filter out already-processed sessions
        if not include_processed:
            sessions = [s for s in sessions if not self.history.is_processed(s)]
        
        return sessions
    
    def get_unprocessed_sessions(self, volume: Path) -> List[QuSession]:
        """Get only sessions that haven't been processed yet."""
        return self.find_qu_recordings(volume, include_processed=False)
    
    def scan_all_volumes(self) -> Dict[Path, List[QuSession]]:
        """Scan all mounted volumes for Qu recordings."""
        results = {}
        
        for volume in self._get_current_volumes():
            if volume.name.startswith('.'):
                continue
            
            sessions = self.find_qu_recordings(volume)
            if sessions:
                results[volume] = sessions
        
        return results
    
    def watch(self, callback, poll_interval: float = 2.0):
        """
        Watch for new USB drives and call callback when found.
        
        Args:
            callback: Function called with (volume_path, sessions) when recordings found
            poll_interval: How often to check for new volumes (seconds)
        """
        print(f"[WATCHER] Watching {self.volumes_path} for new USB drives...")
        print(f"[WATCHER] Looking for A&H Qu-16 recordings in /{AHQU_FOLDER}/{USBMTK_FOLDER}/")
        print(f"[WATCHER] Press Ctrl+C to stop\n")
        
        try:
            while True:
                new_volumes = self.check_for_new_volumes()
                
                for volume in new_volumes:
                    if volume.name.startswith('.'):
                        continue
                    
                    print(f"[WATCHER] New volume detected: {volume.name}")
                    
                    # Wait a moment for the volume to fully mount
                    time.sleep(1)
                    
                    sessions = self.find_qu_recordings(volume)
                    
                    if sessions:
                        print(f"[WATCHER] Found {len(sessions)} recording session(s)!")
                        for s in sessions:
                            print(f"  - {s}")
                        
                        callback(volume, sessions)
                    else:
                        print(f"[WATCHER] No Qu-16 recordings found on {volume.name}")
                
                time.sleep(poll_interval)
        
        except KeyboardInterrupt:
            print("\n[WATCHER] Stopped")


def main():
    parser = argparse.ArgumentParser(
        description="Watch for A&H Qu-16 recordings on USB drives"
    )
    parser.add_argument("--scan-now", action="store_true",
                       help="Scan currently mounted volumes and exit")
    parser.add_argument("--volume", type=str,
                       help="Scan a specific volume path")
    parser.add_argument("--clear-history", action="store_true",
                       help="Clear processing history")
    parser.add_argument("--show-history", action="store_true",
                       help="Show processing history")
    
    args = parser.parse_args()
    
    history = ProcessingHistory()
    watcher = USBWatcher(history=history)
    
    if args.clear_history:
        history.clear()
        return 0
    
    if args.show_history:
        if not history.processed:
            print("No sessions have been processed yet.")
        else:
            print(f"Processing History ({len(history.processed)} sessions):\n")
            for fp, info in sorted(history.processed.items(), 
                                   key=lambda x: x[1].get('processed_at', ''), 
                                   reverse=True):
                print(f"  {info.get('show_name', 'Unknown')} ({info.get('duration_estimate', '?')})")
                print(f"    Folder: {info.get('folder_name')}")
                print(f"    Processed: {info.get('processed_at', '?')}")
                print(f"    Fingerprint: {fp[:8]}...")
                print()
        return 0
    
    if args.volume:
        volume = Path(args.volume)
        if not volume.exists():
            print(f"Error: Volume not found: {volume}")
            return 1
        
        sessions = watcher.find_qu_recordings(volume)
        if sessions:
            print(f"Found {len(sessions)} recording session(s) on {volume.name}:\n")
            for s in sessions:
                is_processed = history.is_processed(s)
                status = " [ALREADY PROCESSED]" if is_processed else " [NEW]"
                print(f"  {s}{status}")
                pair = s.get_stereo_pair()
                if pair:
                    print(f"    Stereo pair: {pair[0].name} (L), {pair[1].name} (R)")
                if is_processed:
                    info = history.get_info(s)
                    if info:
                        print(f"    Previously processed as: {info.get('show_name')}")
                        print(f"    Output: {info.get('output_dir')}")
                print()
            
            # Summary
            unprocessed = [s for s in sessions if not history.is_processed(s)]
            if unprocessed:
                print(f"  {len(unprocessed)} session(s) ready to process")
            else:
                print(f"  All sessions already processed")
        else:
            print(f"No Qu-16 recordings found on {volume.name}")
        return 0
    
    if args.scan_now:
        results = watcher.scan_all_volumes()
        if results:
            for volume, sessions in results.items():
                print(f"\n{volume.name}:")
                for s in sessions:
                    is_processed = history.is_processed(s)
                    status = " [PROCESSED]" if is_processed else " [NEW]"
                    print(f"  - {s}{status}")
                    pair = s.get_stereo_pair()
                    if pair:
                        print(f"      Stereo: {pair[0].name} (L), {pair[1].name} (R)")
        else:
            print("No Qu-16 recordings found on any mounted volume")
        return 0
    
    # Default: watch for new volumes
    def on_recording_found(volume, sessions):
        print(f"\n*** Recording found on {volume.name}! ***")
        # This is where we'd trigger processing
    
    watcher.watch(on_recording_found)
    return 0


if __name__ == "__main__":
    sys.exit(main())
