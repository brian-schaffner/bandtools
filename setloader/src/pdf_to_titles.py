#!/usr/bin/env python3
# pdf_to_titles.py
# Read a TXT (preferred) or PDF, sanitize lines into likely song titles, write one-per-line.

from __future__ import annotations
import argparse
from pathlib import Path
import re
import unicodedata
import sys
import subprocess
import shutil   # ← add this line

# ---------- Args ----------
parser = argparse.ArgumentParser(
    description="Extract clean song titles from a text file (or PDF)."
)
parser.add_argument("--in", dest="input_file", required=True,
                    help="Input path: plain text (preferred). If PDF, requires pdftotext.")
parser.add_argument("--out", dest="output_file", required=True,
                    help="Where to write titles (one per line).")
parser.add_argument("--psm", type=int, default=6,
                    help="Tesseract page segmentation mode (only used if we ever OCR).")
parser.add_argument("--lang", default="eng",
                    help="OCR language if needed (default: eng).")
parser.add_argument("--debug", action="store_true",
                    help="Print extra info while parsing.")
args = parser.parse_args()

IN  = Path(args.input_file)
OUT = Path(args.output_file)

# ---------- Helpers ----------
BUL_LEAD = re.compile(r"^\s*([:;,_|.•·»«\-–—]+|\bi[.\)]|\bu[.\)]|\)\.|[0-9]+\.)\s*")
KEY_TAIL = re.compile(r"\s*[~\-–—]?\s*[A-G](?:#|b)?m?(?:\s*(?:maj|min|dim|aug|sus|add)?\d{0,2})?\s*(?:snap|capo\s*\d+)?\s*$",
                      re.IGNORECASE)
HEADER   = re.compile(r"\b(set|mins?|minutes?|break|start|end|time|min\s*break)\b", re.IGNORECASE)
ALL_CHORDS = re.compile(r"(?:\b[A-G](?:#|b)?m?\b[\s/|]*){3,}")  # 3+ chord tokens likely a chord line

def normalize_nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s).replace("\u00A0"," ")

def looks_like_title(line: str) -> str | None:
    s = normalize_nfkc(line).strip()
    if not s:
        return None
    # obvious headers/timing junk
    if HEADER.search(s):
        return None
    
    # Look for numbered song titles (e.g., "1. Believe – F" or "1. I Will Survive– Gm")
    # Handle both "3. Marlenas" and "3 Marlenas" formats
    numbered_match = re.match(r'^\s*(\d+)\.?\s*(.+?)(?:\s*[–-]\s*[A-G].*)?$', s)
    if numbered_match:
        number = numbered_match.group(1)
        title_part = numbered_match.group(2).strip()
        
        # Clean up the title - remove any leading dots or extra spaces
        title_part = re.sub(r'^\s*\.+\s*', '', title_part)  # Remove leading dots
        title_part = re.sub(r'^\s+', '', title_part)  # Remove leading spaces
        title_part = title_part.strip()
        
        # Check if the original line had a period after the number (like "1. Believe")
        # vs no period (like "3 Marlenas")
        # Look for the pattern "number ." (with space) or "number." in the original line
        if re.search(r'^\s*' + re.escape(number) + r'\s*\.\s+', s):
            # This is a regular list item (like "1. Believe"), just use the title part
            song_title = title_part
        else:
            # This is a song title that starts with a number (like "3 Marlenas")
            # Reconstruct the full title with the number
            song_title = f"{number} {title_part}"
        
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
            
            # Also check if the second part looks like a timing break
            second_part = parts[1].strip()
            if (re.search(r'\d+:\d+', second_part) or  # Contains time patterns
                re.search(r'\b(break|mins?|minutes?|time)\b', second_part, re.IGNORECASE)):  # Contains timing words
                return None  # Don't process timing breaks
            
            # If the first part is empty and the second part looks like a timing break, don't process it
            if not song_title and second_part:
                if (re.search(r'\d+:\d+', second_part) or  # Contains time patterns
                    re.search(r'\b(break|mins?|minutes?|time)\b', second_part, re.IGNORECASE)):  # Contains timing words
                    return None  # Don't process timing breaks
    
    # Look for unnumbered song titles that might be missed
    # This catches songs that don't follow the numbered pattern  
    if len(s) >= 3 and len(s) <= 50:  # Reasonable song title length
        # Check if it looks like a song title (not a header, not chords, not timing, not instructions)
        if (not ALL_CHORDS.search(s) and 
            not HEADER.search(s) and 
            not re.search(r'\d+:\d+', s) and  # No time patterns like "9:50-10"
            not re.search(r'^\s*SET\s*\d+', s, re.IGNORECASE) and  # No "SET 1"
            not re.search(r'break', s, re.IGNORECASE) and  # No "break"
            not re.search(r'^\s*–', s) and  # No lines starting with "–"
            not re.search(r'\b(detune|tune|capo|transpose|key|tempo|bpm)\b', s, re.IGNORECASE) and  # No instructions
            s != "SET 1" and  # No "SET 1"
            not re.search(r'^\s*–\s*\d+:\d+', s) and  # No timing breaks like "– 9:50-10"
            not re.search(r'^\s*\d+\s*–\s*\d+:\d+', s) and  # No "2 – 9:50-10" patterns
            not re.search(r'^\s*SET\s*\d+\s*–', s, re.IGNORECASE) and  # No "SET 1 –" patterns
            not re.search(r'^\s*\d+\s*–\s*\d+:\d+\s+\d+\s+min', s)):  # No "2 – 9:50-10 15 min" patterns
            # Clean up the title
            clean_title = s.strip(" -–—~|•·.,_")
            if clean_title and len(clean_title) >= 3:
                return clean_title
    
    # Fallback to original logic for other cases
    # strip leading bullets/markers
    s = BUL_LEAD.sub("", s)
    # discard pure chord lines
    if ALL_CHORDS.search(s):
        return None
    # remove trailing key/chord annotations
    s = KEY_TAIL.sub("", s)
    s = s.strip(" -–—~|•·.,_")
    # filter short/noisy lines
    letters = sum(c.isalpha() for c in s)
    if letters < 3 or letters / max(1, len(s)) < 0.6:
        return None
    return s

def read_text_from_file(path: Path) -> str:
    """
    Preferred path: text file produced by your run.sh pipeline.
    If a PDF is supplied, we fall back to pdftotext if available.
    """
    suffix = path.suffix.lower()
    if suffix in (".txt", ".text", ".log"):
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        # best-effort: use pdftotext if present
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
    # fallback: try to read as text anyway
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        # last resort: decode bytes
        return path.read_bytes().decode("utf-8", errors="replace")

# ---------- Main ----------
def main() -> int:
    if not IN.exists():
        print(f"Failed to extract any text: input not found: {IN}", file=sys.stderr)
        return 1

    try:
        text = read_text_from_file(IN)
    except Exception as e:
        print(f"Failed to extract any text: {e}", file=sys.stderr)
        return 1

    titles: list[str] = []
    seen: set[str] = set()
    
    # First pass: merge multi-line "Extras:" sections
    lines = text.splitlines()
    merged_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.lower().startswith('extras:'):
            # Found an "Extras:" line - collect all continuation lines
            extras_content = line[7:].strip()  # Remove "Extras:" prefix
            i += 1
            
            # Collect continuation lines (lines that don't look like new titles)
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue
                
                # Check if this line looks like a new title (not a continuation)
                # A continuation line typically:
                # 1. Doesn't start with a number followed by a period
                # 2. Doesn't look like a song title with key signature
                # 3. Contains commas (indicating it's part of a list)
                is_continuation = (
                    ',' in next_line or  # Contains commas (list continuation)
                    (not next_line[0].isdigit() and not re.match(r'^\d+\.', next_line)) or  # Doesn't start with number
                    not re.search(r'[A-G][#b]?[m]?$', next_line)  # Doesn't end with key signature
                )
                
                if not is_continuation and looks_like_title(next_line) and not next_line.lower().startswith('extras:'):
                    # This looks like a new title, stop collecting
                    break
                
                # This looks like a continuation of the extras list
                extras_content += " " + next_line
                i += 1
            
            # Add the merged extras line
            merged_lines.append(extras_content)
        else:
            # Regular line
            merged_lines.append(line)
            i += 1

    # Second pass: process merged lines
    for raw in merged_lines:
        t = looks_like_title(raw)
        if not t:
            continue
        
        # Handle comma-separated lists by splitting and processing each item
        if ',' in t:
            items = [item.strip() for item in t.split(',')]
            for item in items:
                if item and len(item) >= 3 and not item.lower().endswith(':'):
                    if item and len(item) >= 3:
                        # de-dupe on punctuation-insensitive key
                        k = re.sub(r"\W+", " ", item).strip().casefold()
                        if k not in seen:
                            seen.add(k)
                            titles.append(item)
        else:
            # Single title
            if t and len(t) >= 3:
                # de-dupe on punctuation-insensitive key
                k = re.sub(r"\W+", " ", t).strip().casefold()
                if k not in seen:
                    seen.add(k)
                    titles.append(t)
    
    # Post-process to handle "Oh Baby" + "Baby" -> "Oh Baby Baby"
    final_titles = []
    i = 0
    while i < len(titles):
        current = titles[i]
        # Check if this is "Oh Baby" and next is "Baby"
        if (current.lower() == 'oh baby' and 
            i + 1 < len(titles) and 
            titles[i + 1].lower() == 'baby'):
            final_titles.append("Oh Baby Baby")
            i += 2  # Skip both "Oh Baby" and "Baby"
        else:
            final_titles.append(current)
            i += 1
    
    # Filter out standalone numbers (like "10", "11", "12") - handle with/without spaces
    titles = [t for t in final_titles if not (t.strip().isdigit() and len(t.strip()) <= 3)]
    
    # Filter out instructions and non-song items
    instruction_words = ['detun', 'detune', 'tune', 'capo', 'transpose', 'key', 'tempo', 'bpm']
    titles = [t for t in titles if not any(word in t.lower() for word in instruction_words)]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for t in titles:
            f.write(t + "\n")

    if args.debug:
        print(f"[pdf_to_titles] input={IN}  -> wrote {len(titles)} titles to {OUT}")

    # mimic your previous success/exit semantics
    if len(titles) == 0:
        print("Failed to extract any text.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())