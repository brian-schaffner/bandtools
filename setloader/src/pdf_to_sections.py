#!/usr/bin/env python3
"""
Extract song sections from PDF, preserving section structure.
"""
import argparse
import re
import subprocess
import json
from pathlib import Path

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using pdftotext"""
    result = subprocess.run(['pdftotext', pdf_path, '-'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"pdftotext failed: {result.stderr}")
    return result.stdout

def looks_like_song_title(line):
    """Check if a line looks like a song title"""
    line = line.strip()
    if not line or len(line) < 3:
        return None
    
    # Remove common prefixes and suffixes
    line = re.sub(r'^\d+\.\s*', '', line)  # Remove numbered list items (1., 2., etc.) but not song titles that start with numbers
    line = re.sub(r'\s*[–-]\s*[A-G][#b]?[m]?.*$', '', line)  # Remove key signatures
    line = re.sub(r'\s*\([^)]*\)\s*$', '', line)  # Remove parenthetical notes
    line = re.sub(r'\s*(snap|ballad|short|starts\s+\w+).*$', '', line, flags=re.IGNORECASE)
    
    # Clean up the title
    line = line.strip()
    
    # Filter out non-song items
    if any(keyword in line.lower() for keyword in [
        'set', 'break', 'detune', 'tune', 'capo', 'transpose', 'key', 'tempo', 'bpm',
        'min', 'minute', 'hour', ':', '–', 'break'
    ]):
        return None
    
    if len(line) < 3:
        return None
        
    return line

def parse_pdf_sections(text):
    """Parse PDF text into sections with songs"""
    lines = text.split('\n')
    sections = {}
    current_section = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Check for section headers
        if re.search(r'^SET\s*1', line, re.IGNORECASE):
            current_section = 'SET 1'
            sections[current_section] = []
        elif re.search(r'^SET\s*2', line, re.IGNORECASE) or re.search(r'^2\s*[–-]', line):
            current_section = 'SET 2'
            sections[current_section] = []
        elif re.search(r'^SET\s*3', line, re.IGNORECASE):
            current_section = 'SET 3'
            sections[current_section] = []
        elif re.search(r'^EXTRAS?', line, re.IGNORECASE):
            current_section = 'EXTRAS'
            sections[current_section] = []
            # For EXTRAS, we need to collect the entire multi-line content
            extras_content = line
            # Continue reading until we hit a blank line, end of file, or section headers
            j = i + 1
            while j < len(lines) and lines[j].strip():
                next_line = lines[j].strip()
                # Stop if we hit section headers (SET, EXTRAS) but NOT numbered items
                if re.search(r'^(SET|EXTRAS)', next_line, re.IGNORECASE):
                    break
                extras_content += " " + next_line
                j += 1
            # Process the extras content as a single comma-separated list
            extras_songs = process_extras_section([extras_content])
            sections[current_section] = extras_songs
            # Skip the lines we already processed and reset current_section
            i = j - 1
            current_section = None  # Reset to prevent adding more songs to EXTRAS
        elif current_section and line:
            # Check if this looks like a song title
            song_title = looks_like_song_title(line)
            if song_title:
                sections[current_section].append(song_title)
    
    return sections

def process_extras_section(extras_songs):
    """Process the extras section which may contain comma-separated lists"""
    processed = []
    for song in extras_songs:
        # Strip "Extras:" prefix if present
        if song.lower().startswith('extras:'):
            song = song[7:].strip()
        
        if ',' in song:
            # Split comma-separated items
            items = [item.strip() for item in song.split(',')]
            for item in items:
                # Clean up any trailing numbers or periods
                item = re.sub(r'\s+\d+\.?\s*$', '', item).strip()
                if item and len(item) >= 3:
                    processed.append(item)
        else:
            # Clean up any trailing numbers or periods
            song = re.sub(r'\s+\d+\.?\s*$', '', song).strip()
            if song and len(song) >= 3:
                processed.append(song)
    
    return processed

def main():
    parser = argparse.ArgumentParser(description="Extract song sections from PDF")
    parser.add_argument("--in", required=True, help="Input PDF file")
    parser.add_argument("--out", required=True, help="Output JSON file")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    
    args = parser.parse_args()
    
    # Extract text from PDF
    text = extract_text_from_pdf(getattr(args, 'in'))
    
    if args.debug:
        print("Raw PDF text:")
        print("=" * 60)
        print(text)
        print("=" * 60)
    
    # Parse sections
    sections = parse_pdf_sections(text)
    
    # Process extras section specially
    if 'EXTRAS' in sections:
        sections['EXTRAS'] = process_extras_section(sections['EXTRAS'])
    
    # Output results
    output = {
        "sections": sections,
        "total_songs": sum(len(songs) for songs in sections.values()),
        "section_counts": {section: len(songs) for section, songs in sections.items()}
    }
    
    with open(args.out, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Extracted {output['total_songs']} songs from {len(sections)} sections:")
    for section, count in output['section_counts'].items():
        print(f"  {section}: {count} songs")

if __name__ == "__main__":
    main()
