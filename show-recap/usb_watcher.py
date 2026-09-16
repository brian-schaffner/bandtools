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


class QuSession:
    """Represents an A&H Qu-16 recording session."""
    
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.wav_files: List[Path] = []
        self.total_size = 0
        self.created_date: Optional[datetime] = None
        self._scan()
    
    def _scan(self):
        """Scan the session folder for WAV files."""
        for f in self.path.glob("*.WAV"):
            if f.is_file():
                size = f.stat().st_size
                self.wav_files.append(f)
                self.total_size += size
        
        # Also check lowercase
        for f in self.path.glob("*.wav"):
            if f.is_file() and f not in self.wav_files:
                size = f.stat().st_size
                self.wav_files.append(f)
                self.total_size += size
        
        # Sort by name for consistent channel ordering
        self.wav_files.sort(key=lambda x: x.name)
        
        # Get creation date from folder
        try:
            stat = self.path.stat()
            self.created_date = datetime.fromtimestamp(stat.st_mtime)
        except:
            pass
    
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
        date_str = self.created_date.strftime("%Y-%m-%d") if self.created_date else "Unknown"
        return f"{self.name} ({len(self.wav_files)} tracks, {size_gb:.1f} GB, {date_str})"


class USBWatcher:
    """Watch for USB drives with A&H Qu-16 recordings."""
    
    def __init__(self, volumes_path: Path = VOLUMES_PATH):
        self.volumes_path = volumes_path
        self.known_volumes: set = set()
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
    
    def find_qu_recordings(self, volume: Path) -> List[QuSession]:
        """
        Find A&H Qu-16 recording sessions on a volume.
        
        Looks for: <volume>/AHQU/USBMTK/<session_folders>/
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
        
        # Sort by date, newest first
        sessions.sort(key=lambda s: s.created_date or datetime.min, reverse=True)
        
        return sessions
    
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
    
    args = parser.parse_args()
    
    watcher = USBWatcher()
    
    if args.volume:
        volume = Path(args.volume)
        if not volume.exists():
            print(f"Error: Volume not found: {volume}")
            return 1
        
        sessions = watcher.find_qu_recordings(volume)
        if sessions:
            print(f"Found {len(sessions)} recording session(s) on {volume.name}:")
            for s in sessions:
                print(f"\n  {s}")
                pair = s.get_stereo_pair()
                if pair:
                    print(f"    Stereo pair: {pair[0].name} (L), {pair[1].name} (R)")
        else:
            print(f"No Qu-16 recordings found on {volume.name}")
        return 0
    
    if args.scan_now:
        results = watcher.scan_all_volumes()
        if results:
            for volume, sessions in results.items():
                print(f"\n{volume.name}:")
                for s in sessions:
                    print(f"  - {s}")
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
