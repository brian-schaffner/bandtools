#!/usr/bin/env python3
"""
Show Recap CLI - Process multitrack recordings locally.

Usage:
    python cli.py process /path/to/recording.wav --name "Friday Night Show"
    python cli.py process /path/to/*.wav --name "Saturday Gig" --date 2026-09-14
    python cli.py process /Volumes/QU-16/AHQU/*.wav --name "Live Recording"
"""

import argparse
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from audio_analyzer import AudioAnalyzer
from audio_processor import AudioProcessor
from music_recognizer import MusicRecognizer
from dropbox_uploader import DropboxUploader


def process_recording(
    file_paths: list,
    show_name: str,
    show_date: str = None,
    output_dir: str = None,
    silence_threshold_db: float = -40.0,
    min_silence_duration: float = 10.0,
    min_set_duration: float = 300.0,
    skip_start: float = 0.0,
    pad_start: float = 5.0,
    pad_end: float = 3.0,
    fade_in: float = 0.5,
    fade_out: float = 2.0,
    trim_set_starts: str = None,
    extend_set_ends: str = None,
    detect_breaks: bool = False,
    acrcloud_key: str = None,
    acrcloud_secret: str = None,
    upload: bool = False,
    dropbox_folder: str = "/Show Recap",
):
    """Process multitrack recording and split into sets."""
    
    # Validate files
    files = []
    for path in file_paths:
        p = Path(path)
        if p.is_file():
            files.append(p)
        elif '*' in str(path):
            # Glob pattern
            parent = p.parent
            pattern = p.name
            files.extend(parent.glob(pattern))
    
    if not files:
        print("Error: No audio files found")
        return 1
    
    # Sort files by name for consistent L/R assignment
    files = sorted(files, key=lambda x: x.name)
    
    print(f"\n{'='*60}")
    print(f"  SHOW RECAP - {show_name}")
    print(f"{'='*60}")
    print(f"  Files: {len(files)}")
    for f in files:
        size_mb = f.stat().st_size / (1024*1024)
        print(f"    - {f.name} ({size_mb:.1f} MB)")
    
    # Check for stereo mixing (2 mono files)
    stereo_mix = len(files) == 2
    if stereo_mix:
        print(f"  Stereo mode: {files[0].name} (L) + {files[1].name} (R)")
    
    print(f"  Silence threshold: {silence_threshold_db} dB")
    print(f"  Min break duration: {min_silence_duration}s")
    print(f"  Min set duration: {min_set_duration}s")
    if skip_start > 0:
        print(f"  Skip start: {skip_start}s ({skip_start/60:.1f} min)")
    print(f"  Padding: +{pad_start}s before, +{pad_end}s after each set")
    print(f"  Fades: {fade_in}s in, {fade_out}s out")
    
    # Parse per-set adjustments
    set_start_trims = []
    if trim_set_starts:
        set_start_trims = [float(x.strip()) for x in trim_set_starts.split(',')]
        print(f"  Trim from set starts: {set_start_trims}")
    
    set_end_extends = []
    if extend_set_ends:
        set_end_extends = [float(x.strip()) for x in extend_set_ends.split(',')]
        print(f"  Extend set ends: {set_end_extends}")
    
    print(f"{'='*60}\n")
    
    # Use first file for analysis (timing should match both tracks)
    analysis_file = str(files[0])
    
    # Setup output directory
    if output_dir:
        out_path = Path(output_dir)
    else:
        out_path = Path.cwd() / "show-recap-output" / show_name.replace(' ', '_')
    out_path.mkdir(parents=True, exist_ok=True)
    
    show_date = show_date or datetime.now().strftime("%Y-%m-%d")
    
    # Step 1: Analyze
    print("[1/3] Analyzing audio for set boundaries...")
    analyzer = AudioAnalyzer(
        silence_threshold_db=silence_threshold_db,
        min_silence_duration=min_silence_duration,
        min_set_duration=min_set_duration,
        skip_start=skip_start,
    )
    
    analysis = analyzer.analyze(analysis_file)
    
    # Save analysis
    analysis_file = out_path / "analysis.json"
    with open(analysis_file, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"  Saved analysis to: {analysis_file}")
    
    sets = analysis.get("sets", [])
    if not sets:
        print("\n  Warning: No sets detected! The recording might be:")
        print("    - Too short")
        print("    - Missing clear breaks between sets")
        print("    - Try adjusting --silence-threshold or --min-break")
        return 1
    
    total_duration = analysis.get("total_duration", float('inf'))
    
    print(f"\n  Found {len(sets)} sets:")
    for s in sets:
        start = s['start_time']
        end = s['end_time']
        duration = s['duration']
        print(f"    Set {s['set_number']}: {_format_time(start)} - {_format_time(end)} ({duration/60:.1f} min)")
    
    # Optional: Use ACRCloud to detect commercial break music
    if detect_breaks:
        print(f"\n[1.5/3] Detecting commercial break music with ACRCloud...")
        recognizer = MusicRecognizer(
            access_key=acrcloud_key,
            access_secret=acrcloud_secret,
        )
        
        if recognizer.available:
            for s in sets:
                set_num = s['set_number']
                original_start = s['start_time']
                
                print(f"\n  Checking Set {set_num} start ({_format_time(original_start)})...")
                live_start, had_commercial = recognizer.find_live_music_start(
                    str(files[0]),
                    original_start,
                    max_search_duration=1800,  # Search up to 30 min
                    step_size=30,  # Check every 30 seconds
                )
                
                if had_commercial:
                    skip_duration = live_start - original_start
                    print(f"    -> Live music starts at {_format_time(live_start)} (skip {_format_time(skip_duration)} of break music)")
                    s['start_time'] = live_start
                    s['duration'] = s['end_time'] - live_start
                else:
                    print(f"    -> No commercial music detected, keeping original start")
            
            # Print updated set times
            print(f"\n  Adjusted sets:")
            for s in sets:
                start = s['start_time']
                end = s['end_time']
                duration = s['duration']
                print(f"    Set {s['set_number']}: {_format_time(start)} - {_format_time(end)} ({duration/60:.1f} min)")
        else:
            print("  Warning: ACRCloud not available. Set ACRCLOUD_KEY and ACRCLOUD_SECRET.")
            print("  Continuing without break detection...")
    
    # Step 2: Export sets (with background upload if enabled)
    print(f"\n[2/3] Exporting sets as MP3...")
    processor = AudioProcessor()
    
    # For stereo mixing, use first file as L and second as R
    left_channel = str(files[0])
    right_channel = str(files[1]) if stereo_mix else None
    
    # Setup Dropbox uploader if --upload enabled
    uploader = None
    upload_futures = []
    upload_results = {}
    print_lock = Lock()
    
    if upload:
        uploader = DropboxUploader(folder=dropbox_folder)
        if uploader.available:
            print(f"  Dropbox upload enabled -> {dropbox_folder}/{show_date} - {show_name}/")
            executor = ThreadPoolExecutor(max_workers=2)
        else:
            print("  Warning: Dropbox not configured, skipping uploads")
            uploader = None
    
    def upload_in_background(file_path, set_num, subfolder):
        """Upload a file to Dropbox in the background."""
        try:
            remote_path = uploader.upload_file(file_path, subfolder=subfolder)
            if remote_path:
                link = uploader.get_share_link(remote_path)
                with print_lock:
                    print(f"  [UPLOAD] Set {set_num} uploaded! {link}")
                return {"set": set_num, "path": remote_path, "link": link}
        except Exception as e:
            with print_lock:
                print(f"  [UPLOAD] Set {set_num} failed: {e}")
        return {"set": set_num, "error": str(e) if 'e' in dir() else "Unknown error"}
    
    output_files = []
    subfolder = f"{show_date} - {show_name}"
    
    for i, s in enumerate(sets):
        set_num = s['set_number']
        start_time = s['start_time']
        end_time = s['end_time']
        
        # Apply per-set trim (skip break music at start of set)
        set_trim = set_start_trims[i] if i < len(set_start_trims) else 0
        trimmed_start = start_time + set_trim
        
        # Apply per-set end extension
        set_extend = set_end_extends[i] if i < len(set_end_extends) else 0
        extended_end = end_time + set_extend
        
        # Apply padding (but don't go before 0 or past end of file)
        padded_start = max(0, trimmed_start - pad_start)
        padded_end = min(total_duration, extended_end + pad_end)
        
        output_name = f"{show_date}_{show_name.replace(' ', '_')}_Set{set_num}.mp3"
        output_path = out_path / output_name
        
        print(f"  Exporting Set {set_num}{'(stereo L+R)' if stereo_mix else ''}...")
        print(f"    Detected: {_format_time(start_time)} - {_format_time(end_time)}")
        if set_trim > 0:
            print(f"    Trim start: +{_format_time(set_trim)} -> {_format_time(trimmed_start)}")
        if set_extend > 0:
            print(f"    Extend end: +{set_extend}s -> {_format_time(extended_end)}")
        print(f"    Final: {_format_time(padded_start)} - {_format_time(padded_end)} (with padding)")
        processor.export_segment(
            left_channel,
            str(output_path),
            padded_start,
            padded_end,
            metadata={
                "title": f"{show_name} - Set {set_num}",
                "artist": show_name,
                "album": f"{show_name} - {show_date}",
                "track": str(set_num),
            },
            right_channel_path=right_channel,
            fade_in=fade_in,
            fade_out=fade_out,
        )
        output_files.append(output_path)
        print(f"    -> {output_path}")
        
        # Start background upload immediately after extraction
        if uploader:
            future = executor.submit(upload_in_background, output_path, set_num, subfolder)
            upload_futures.append(future)
    
    # Wait for any remaining uploads to complete
    if upload_futures:
        print(f"\n  Waiting for uploads to complete...")
        for future in as_completed(upload_futures):
            result = future.result()
            upload_results[result.get("set")] = result
        executor.shutdown(wait=True)
    
    # Step 3: Summary
    print(f"\n[3/3] Complete!")
    print(f"\n{'='*60}")
    print(f"  OUTPUT FILES")
    print(f"{'='*60}")
    for f in output_files:
        size_mb = f.stat().st_size / (1024*1024)
        print(f"  {f.name} ({size_mb:.1f} MB)")
    print(f"\n  Location: {out_path}")
    
    if upload_results:
        print(f"\n  DROPBOX LINKS")
        print(f"  {'-'*50}")
        for set_num in sorted(upload_results.keys()):
            result = upload_results[set_num]
            if result.get("link"):
                print(f"  Set {set_num}: {result['link']}")
            else:
                print(f"  Set {set_num}: Upload failed - {result.get('error', 'Unknown')}")
    
    print(f"{'='*60}\n")
    
    return 0


def _format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def main():
    parser = argparse.ArgumentParser(
        description="Show Recap - Split multitrack recordings into sets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s process recording.wav --name "Friday Night"
  %(prog)s process /Volumes/QU-16/*.wav --name "Saturday Gig" --date 2026-09-14
  %(prog)s process track1.wav track2.wav --name "Live Show" --output ./output
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Process command
    proc = subparsers.add_parser("process", help="Process audio files")
    proc.add_argument("files", nargs="+", help="Audio file paths (supports glob patterns)")
    proc.add_argument("--name", "-n", required=True, help="Show name")
    proc.add_argument("--date", "-d", help="Show date (YYYY-MM-DD)")
    proc.add_argument("--output", "-o", help="Output directory")
    proc.add_argument("--silence-threshold", type=float, default=-40.0,
                      help="Silence threshold in dB (default: -40)")
    proc.add_argument("--min-break", type=float, default=10.0,
                      help="Minimum break duration in seconds (default: 10)")
    proc.add_argument("--min-set", type=float, default=300.0,
                      help="Minimum set duration in seconds (default: 300)")
    proc.add_argument("--skip-start", type=float, default=0.0,
                      help="Skip this many seconds from the start (default: 0)")
    proc.add_argument("--pad-start", type=float, default=5.0,
                      help="Extra seconds to include BEFORE each set starts (default: 5)")
    proc.add_argument("--pad-end", type=float, default=3.0,
                      help="Extra seconds to include AFTER each set ends (default: 3)")
    proc.add_argument("--fade-in", type=float, default=0.5,
                      help="Fade in duration in seconds (default: 0.5)")
    proc.add_argument("--fade-out", type=float, default=2.0,
                      help="Fade out duration in seconds (default: 2.0)")
    proc.add_argument("--trim-set-starts", type=str, default=None,
                      help="Comma-separated seconds to trim from START of each set (e.g., '0,1136,0' trims 18:56 from Set 2)")
    proc.add_argument("--extend-set-ends", type=str, default=None,
                      help="Comma-separated extra seconds to add to END of each set (e.g., '0,3,0' adds 3s to Set 2)")
    proc.add_argument("--detect-breaks", action="store_true",
                      help="Use ACRCloud to detect commercial break music and auto-adjust set starts")
    proc.add_argument("--acrcloud-key", type=str, default=None,
                      help="ACRCloud access key (or set ACRCLOUD_KEY env var)")
    proc.add_argument("--acrcloud-secret", type=str, default=None,
                      help="ACRCloud access secret (or set ACRCLOUD_SECRET env var)")
    proc.add_argument("--upload", action="store_true",
                      help="Upload to Dropbox as each set is extracted")
    proc.add_argument("--dropbox-folder", type=str, default="/Show Recap",
                      help="Dropbox folder to upload to (default: /Show Recap)")
    
    args = parser.parse_args()
    
    if args.command == "process":
        return process_recording(
            file_paths=args.files,
            show_name=args.name,
            show_date=args.date,
            output_dir=args.output,
            silence_threshold_db=args.silence_threshold,
            min_silence_duration=args.min_break,
            min_set_duration=args.min_set,
            skip_start=args.skip_start,
            pad_start=args.pad_start,
            pad_end=args.pad_end,
            fade_in=args.fade_in,
            fade_out=args.fade_out,
            trim_set_starts=args.trim_set_starts,
            extend_set_ends=args.extend_set_ends,
            detect_breaks=args.detect_breaks,
            acrcloud_key=args.acrcloud_key,
            acrcloud_secret=args.acrcloud_secret,
            upload=args.upload,
            dropbox_folder=args.dropbox_folder,
        )
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
