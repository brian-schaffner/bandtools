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

from audio_analyzer import AudioAnalyzer
from audio_processor import AudioProcessor


def process_recording(
    file_paths: list,
    show_name: str,
    show_date: str = None,
    output_dir: str = None,
    silence_threshold_db: float = -40.0,
    min_silence_duration: float = 10.0,
    min_set_duration: float = 300.0,
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
    
    print(f"\n{'='*60}")
    print(f"  SHOW RECAP - {show_name}")
    print(f"{'='*60}")
    print(f"  Files: {len(files)}")
    for f in files:
        size_mb = f.stat().st_size / (1024*1024)
        print(f"    - {f.name} ({size_mb:.1f} MB)")
    print(f"  Silence threshold: {silence_threshold_db} dB")
    print(f"  Min break duration: {min_silence_duration}s")
    print(f"  Min set duration: {min_set_duration}s")
    print(f"{'='*60}\n")
    
    # Use first file as the main mix (or stereo mix)
    main_file = str(files[0])
    
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
    )
    
    analysis = analyzer.analyze(main_file)
    
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
    
    print(f"\n  Found {len(sets)} sets:")
    for s in sets:
        start = s['start_time']
        end = s['end_time']
        duration = s['duration']
        print(f"    Set {s['set_number']}: {_format_time(start)} - {_format_time(end)} ({duration/60:.1f} min)")
    
    # Step 2: Export sets
    print(f"\n[2/3] Exporting sets as MP3...")
    processor = AudioProcessor()
    
    output_files = []
    for s in sets:
        set_num = s['set_number']
        start_time = s['start_time']
        end_time = s['end_time']
        
        output_name = f"{show_date}_{show_name.replace(' ', '_')}_Set{set_num}.mp3"
        output_path = out_path / output_name
        
        print(f"  Exporting Set {set_num}...")
        processor.export_segment(
            main_file,
            str(output_path),
            start_time,
            end_time,
            metadata={
                "title": f"{show_name} - Set {set_num}",
                "artist": show_name,
                "album": f"{show_name} - {show_date}",
                "track": str(set_num),
            }
        )
        output_files.append(output_path)
        print(f"    -> {output_path}")
    
    # Step 3: Summary
    print(f"\n[3/3] Complete!")
    print(f"\n{'='*60}")
    print(f"  OUTPUT FILES")
    print(f"{'='*60}")
    for f in output_files:
        size_mb = f.stat().st_size / (1024*1024)
        print(f"  {f.name} ({size_mb:.1f} MB)")
    print(f"\n  Location: {out_path}")
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
        )
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
