#!/usr/bin/env python3
import sys
import re
import unicodedata
from pathlib import Path
import subprocess
import shutil

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
        # Clean up the title - remove any leading dots or extra spaces
        song_title = re.sub(r'^\s*\.+\s*', '', song_title)  # Remove leading dots
        song_title = re.sub(r'^\s+', '', song_title)  # Remove leading spaces
        song_title = song_title.strip()
        
        # Filter out timing breaks and instructions
        if (song_title and len(song_title) >= 3 and
            not re.search(r'\d+:\d+', song_title) and  # No time patterns
            not re.search(r'\b(break|mins?|minutes?|time)\b', song_title, re.IGNORECASE) and  # No timing words
            not re.search(r'^\s*–', song_title)):  # No lines starting with "–"
            return song_title
    
    # Look for song titles with musical keys (improved logic)
    if '–' in s or '-' in s:
        # Extract the song title part (before the key)
        parts = re.split(r'[–-]', s, 1)
        if len(parts) >= 2:
            song_title = parts[0].strip()
            # Clean up the title - only remove list numbers (like "1. ", "2. ") not song title numbers
            song_title = re.sub(r'^\s*\d+\.\s*', '', song_title)  # Remove list numbers with periods
            song_title = re.sub(r'^\s*\.\s*', '', song_title)  # Remove leading dots
            song_title = song_title.strip()
            
            # Filter out headers and instructions
            if (song_title and len(song_title) >= 3 and
                not re.search(r'^\s*SET\s*\d+', song_title, re.IGNORECASE) and  # No "SET 1"
                not re.search(r'\b(break|mins?|minutes?|time)\b', song_title, re.IGNORECASE) and  # No timing words
                not re.search(r'\d+:\d+', song_title) and  # No time patterns
                not re.search(r'^\s*–', song_title) and  # No lines starting with "–"
                not re.search(r'^\s*–\s*\d+:\d+', song_title)):  # No timing breaks like "– 9:50-10"
                return song_title
    
    return None

def read_text_from_file(path: Path) -> str:
    """Extract text from PDF using pdftotext"""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        if not shutil.which("pdftotext"):
            raise RuntimeError("Input is PDF but pdftotext is not installed.")
        tmp_txt = path.with_suffix(".tmp.txt")
        cmd = ["pdftotext", "-layout", "-nopgbrk", "-q", str(path), str(tmp_txt)]
        subprocess.run(cmd, check=True)
        try:
            return tmp_txt.read_text(encoding="utf-8", errors="replace")
        finally:
            try:
                tmp_txt.unlink()
            except Exception:
                pass
    return path.read_text(encoding="utf-8", errors="replace")

# Test the full pipeline
pdf_path = Path("uploads/TKs-1.pdf")
text = read_text_from_file(pdf_path)

print("=== RAW PDF TEXT ===")
lines = text.splitlines()
for i, line in enumerate(lines):
    if 'marlenas' in line.lower() or 'steps' in line.lower() or 'brown' in line.lower():
        print(f"Line {i}: '{line}'")

print("\n=== PROCESSING EACH LINE ===")
titles = []
seen = set()

for i, raw in enumerate(lines):
    if 'marlenas' in raw.lower() or 'steps' in raw.lower() or 'brown' in raw.lower():
        print(f"\nProcessing line {i}: '{raw}'")
        t = looks_like_title(raw)
        print(f"  looks_like_title result: '{t}'")
        if t:
            # de-dupe on punctuation-insensitive key
            k = re.sub(r"\W+", " ", t).strip().casefold()
            print(f"  dedup key: '{k}'")
            if k not in seen:
                seen.add(k)
                titles.append(t)
                print(f"  ADDED: '{t}'")
            else:
                print(f"  DUPLICATE: '{t}' (key: '{k}')")
        else:
            print(f"  REJECTED: '{t}'")
