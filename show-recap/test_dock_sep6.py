#!/usr/bin/env python3
"""
Test script for Show Recap - The Dock Sep 6 2026
Processes tracks 17 and 18 from the Qu-16 recording.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from cli import process_recording

# Configuration
RECORDING_DIR = Path("/Volumes/Projects 25/Projects/llb/the dock sep 6 2026")
SHOW_NAME = "The Dock Sep 6 2026"
SHOW_DATE = "2026-09-06"
OUTPUT_DIR = Path.home() / "Desktop" / "ShowRecap" / SHOW_NAME.replace(" ", "_")

def find_tracks():
    """Find track 17 and 18 files in the recording directory."""
    if not RECORDING_DIR.exists():
        print(f"Error: Directory not found: {RECORDING_DIR}")
        print("Make sure the drive is mounted.")
        return None, None
    
    print(f"Scanning: {RECORDING_DIR}")
    print("")
    
    # List all WAV files
    wav_files = list(RECORDING_DIR.glob("*.wav")) + list(RECORDING_DIR.glob("*.WAV"))
    
    if not wav_files:
        print("No WAV files found in directory.")
        return None, None
    
    print(f"Found {len(wav_files)} WAV files:")
    for f in sorted(wav_files):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name} ({size_mb:.1f} MB)")
    print("")
    
    # Find tracks 17 and 18
    track17 = None
    track18 = None
    
    for f in wav_files:
        name_lower = f.name.lower()
        # Check various naming patterns
        if any(x in name_lower for x in ['track 17', 'track17', 'tr17', 'ch17', '_17.', '-17.']):
            track17 = f
        elif any(x in name_lower for x in ['track 18', 'track18', 'tr18', 'ch18', '_18.', '-18.']):
            track18 = f
        # Also check for just "17" or "18" at specific positions
        elif '17' in name_lower and track17 is None:
            track17 = f
        elif '18' in name_lower and track18 is None:
            track18 = f
    
    return track17, track18


def main():
    print("=" * 60)
    print("  SHOW RECAP TEST - The Dock Sep 6 2026")
    print("=" * 60)
    print("")
    
    track17, track18 = find_tracks()
    
    if track17:
        print(f"Track 17: {track17.name}")
    else:
        print("Track 17: NOT FOUND")
    
    if track18:
        print(f"Track 18: {track18.name}")
    else:
        print("Track 18: NOT FOUND")
    
    print("")
    
    # Determine which file(s) to process
    files_to_process = []
    if track17:
        files_to_process.append(str(track17))
    if track18:
        files_to_process.append(str(track18))
    
    if not files_to_process:
        print("Error: Could not find Track 17 or Track 18")
        print("")
        print("Please check the file names in the directory and update this script.")
        print("Or run manually:")
        print(f'  python cli.py process "<path-to-file>" --name "{SHOW_NAME}" --date {SHOW_DATE}')
        return 1
    
    # Use track 17 as main (left channel of stereo pair typically)
    main_file = files_to_process[0]
    
    print(f"Processing: {main_file}")
    print(f"Output to: {OUTPUT_DIR}")
    print("")
    
    # Process the recording
    return process_recording(
        file_paths=[main_file],
        show_name=SHOW_NAME,
        show_date=SHOW_DATE,
        output_dir=str(OUTPUT_DIR),
        silence_threshold_db=-40.0,
        min_silence_duration=10.0,
        min_set_duration=300.0,
    )


if __name__ == "__main__":
    sys.exit(main())
