#!/usr/local/bin/python3
"""
CLI tool to extract songs from validated titles and create SBP files.
"""

import argparse
import json
import sys
from pathlib import Path
from song_extraction_library import SongExtractor, SongExtractionError

def main():
    parser = argparse.ArgumentParser(description='Extract songs from validated titles and create SBP file')
    parser.add_argument('--input', '-i', required=True, help='Input JSON file with validated songs')
    parser.add_argument('--output', '-o', required=True, help='Output SBP file path')
    parser.add_argument('--user-id', required=True, help='User ID (email address)')
    parser.add_argument('--backup', help='Path to user backup file (auto-detected if not provided)')
    parser.add_argument('--set-name', default='Extracted Set', help='Name for the new set (default: "Extracted Set")')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    # Auto-detect backup file if not provided
    backup_path = None
    if args.backup:
        backup_path = Path(args.backup)
        if not backup_path.exists():
            print(f"Error: Backup file {backup_path} does not exist", file=sys.stderr)
            sys.exit(1)
    else:
        # Auto-detect user's latest backup
        user_data_dir = Path("user_data")
        if not user_data_dir.exists():
            print("Error: user_data directory not found", file=sys.stderr)
            sys.exit(1)
        
        # Look for user directory (check for Google OAuth directories first)
        user_dir = None
        
        # First, try to find Google OAuth directories
        google_dirs = [d for d in user_data_dir.iterdir() if d.is_dir() and d.name.startswith('google_')]
        if google_dirs:
            # Use the first Google directory (most likely the correct one)
            user_dir = google_dirs[0]
        else:
            # Fallback: look for any directory that might contain this user's data
            for dir_name in user_data_dir.iterdir():
                if dir_name.is_dir() and args.user_id in dir_name.name:
                    user_dir = dir_name
                    break
        
        if not user_dir:
            print(f"Error: User directory for {args.user_id} not found", file=sys.stderr)
            sys.exit(1)
        
        # Find latest backup file
        backup_files = list(user_dir.glob("backup_*.sbpbackup"))
        if not backup_files:
            print(f"Error: No backup files found for user {args.user_id}", file=sys.stderr)
            sys.exit(1)
        
        backup_path = max(backup_files, key=lambda x: x.stat().st_mtime)
        if args.verbose:
            print(f"Auto-detected backup: {backup_path}")
    
    try:
        if args.verbose:
            print(f"Loading input from: {input_path}")
            print(f"User ID: {args.user_id}")
            print(f"Backup file: {backup_path}")
            print(f"Output file: {output_path}")
            print(f"Set name: {args.set_name}")
        
        # Load input JSON
        with open(input_path, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        if args.verbose:
            sets_count = len(input_data.get('sets', []))
            extras_count = len(input_data.get('extras', []))
            print(f"Loaded input with {sets_count} sets and {extras_count} extras")
        
        # Initialize extractor
        extractor = SongExtractor(args.user_id, backup_path)
        
        # Extract songs and create SBP file
        result = extractor.extract_and_save(input_data, output_path, args.set_name)
        
        if args.verbose:
            print(f"Results written to: {output_path}")
        
        # Print summary
        summary = extractor.get_summary(result)
        print("Song extraction complete:")
        print(summary)
        
    except SongExtractionError as e:
        print(f"Extraction error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
