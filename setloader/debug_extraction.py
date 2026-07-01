#!/usr/bin/env python3
import sys
import re
import unicodedata

def normalize_nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s).replace("\u00A0"," ")

def looks_like_title(line: str) -> str | None:
    s = normalize_nfkc(line).strip()
    if not s:
        return None
    
    # Look for numbered song titles (e.g., "1. Believe – F" or "1. I Will Survive– Gm")
    numbered_match = re.match(r'^\s*(\d+)\.?\s*(.+?)(?:\s*[–-]\s*[A-G].*)?$', s)
    if numbered_match:
        song_title = numbered_match.group(2).strip()
        print(f"DEBUG: numbered_match found, group(2) = '{song_title}'")
        # Clean up the title - remove any leading dots or extra spaces
        song_title = re.sub(r'^\s*\.+\s*', '', song_title)  # Remove leading dots
        song_title = re.sub(r'^\s+', '', song_title)  # Remove leading spaces
        song_title = song_title.strip()
        print(f"DEBUG: after cleanup = '{song_title}'")
        
        # Filter out timing breaks and instructions
        if (song_title and len(song_title) >= 3 and
            not re.search(r'\d+:\d+', song_title) and  # No time patterns
            not re.search(r'\b(break|mins?|minutes?|time)\b', song_title, re.IGNORECASE) and  # No timing words
            not re.search(r'^\s*–', song_title)):  # No lines starting with "–"
            print(f"DEBUG: returning '{song_title}'")
            return song_title
    
    # Look for song titles with musical keys (improved logic)
    if '–' in s or '-' in s:
        print(f"DEBUG: found dash in '{s}'")
        # Extract the song title part (before the key)
        parts = re.split(r'[–-]', s, 1)
        if len(parts) >= 2:
            song_title = parts[0].strip()
            print(f"DEBUG: before dash cleanup = '{song_title}'")
            # Clean up the title - only remove list numbers (like "1. ", "2. ") not song title numbers
            song_title = re.sub(r'^\s*\d+\.\s*', '', song_title)  # Remove list numbers with periods
            song_title = re.sub(r'^\s*\.\s*', '', song_title)  # Remove leading dots
            song_title = song_title.strip()
            print(f"DEBUG: after dash cleanup = '{song_title}'")
            
            # Filter out headers and instructions
            if (song_title and len(song_title) >= 3 and
                not re.search(r'^\s*SET\s*\d+', song_title, re.IGNORECASE) and  # No "SET 1"
                not re.search(r'\b(break|mins?|minutes?|time)\b', song_title, re.IGNORECASE) and  # No timing words
                not re.search(r'\d+:\d+', song_title) and  # No time patterns
                not re.search(r'^\s*–', song_title) and  # No lines starting with "–"
                not re.search(r'^\s*–\s*\d+:\d+', song_title)):  # No timing breaks like "– 9:50-10"
                print(f"DEBUG: returning from dash logic = '{song_title}'")
                return song_title
    
    return None

# Test the specific problematic lines
test_lines = [
    '4. 3 Marlenas – D',
    '5. 3 Steps – D', 
    'Brown Eyed'
]

for line in test_lines:
    print(f"\nTesting: '{line}'")
    result = looks_like_title(line)
    print(f'Result: "{result}"')
