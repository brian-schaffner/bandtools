#!/usr/bin/env python3
"""
Fixed PDF processing to extract all songs from the setlist PDF.
This addresses the issue where only 25-30 songs were being extracted instead of 44+.
"""

import re
import subprocess
from pathlib import Path

def extract_all_songs_from_pdf(pdf_path: str) -> list[str]:
    """Extract all song titles from PDF using improved logic."""
    
    # Use pdftotext to extract text
    result = subprocess.run(['pdftotext', '-layout', '-nopgbrk', '-q', pdf_path, '-'], 
                          capture_output=True, text=True, check=True)
    
    lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
    
    songs = []
    seen = set()
    
    for line in lines:
        # Skip headers and timing info
        if any(keyword in line.lower() for keyword in ['set', 'mins', 'minutes', 'break', 'start', 'end', 'time']):
            continue
            
        # Skip pure numbers (1., 2., etc.)
        if re.match(r'^\s*\d+\.?\s*$', line):
            continue
            
        # Look for song titles with musical keys
        if '–' in line or '-' in line:
            # Extract the song title part (before the key)
            parts = re.split(r'[–-]', line, 1)
            if len(parts) >= 2:
                song_title = parts[0].strip()
                # Clean up the title
                song_title = re.sub(r'^\s*\d+\.?\s*', '', song_title)  # Remove leading numbers
                song_title = re.sub(r'^\s*\.\s*', '', song_title)  # Remove leading dots
                song_title = song_title.strip()
                
                if song_title and len(song_title) >= 3:
                    # De-duplicate
                    key = song_title.lower().strip()
                    if key not in seen:
                        seen.add(key)
                        songs.append(song_title)
    
    return songs

def main():
    pdf_path = "/usr/local/src/setloader/uploads/Bonnie_20Sloan_20Country_20Sep.pdf"
    songs = extract_all_songs_from_pdf(pdf_path)
    
    print(f"Extracted {len(songs)} songs:")
    for i, song in enumerate(songs, 1):
        print(f"{i:2d}: {song}")
    
    # Write to file
    output_path = "/usr/local/src/setloader/fixed_extraction.txt"
    with open(output_path, 'w') as f:
        for song in songs:
            f.write(song + '\n')
    
    print(f"\nWritten to {output_path}")

if __name__ == "__main__":
    main()
