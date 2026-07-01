#!/usr/bin/env python3
"""
Analyze PDF structure to identify sections (Set 1, Set 2, Extras)
"""
import sys
import re
from pathlib import Path

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using subprocess and pdftotext"""
    import subprocess
    import tempfile
    
    # Use pdftotext to extract text
    result = subprocess.run(['pdftotext', pdf_path, '-'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"pdftotext failed: {result.stderr}")
    return result.stdout

def analyze_pdf_structure(pdf_path):
    """Analyze PDF to identify sections and song groupings"""
    text = extract_text_from_pdf(pdf_path)
    
    print("Raw PDF text:")
    print("=" * 60)
    print(text)
    print("=" * 60)
    
    # Look for section markers
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
            print(f"Found {current_section} at line {i+1}: {line}")
        elif re.search(r'^SET\s*2', line, re.IGNORECASE):
            current_section = 'SET 2'
            sections[current_section] = []
            print(f"Found {current_section} at line {i+1}: {line}")
        elif re.search(r'^EXTRAS?', line, re.IGNORECASE):
            current_section = 'EXTRAS'
            sections[current_section] = []
            print(f"Found {current_section} at line {i+1}: {line}")
        elif current_section and line and not re.search(r'^(SET|EXTRAS)', line, re.IGNORECASE):
            # This looks like a song title
            sections[current_section].append(line)
    
    print(f"\nSection analysis:")
    for section, songs in sections.items():
        print(f"\n{section} ({len(songs)} songs):")
        for song in songs[:10]:  # Show first 10 songs
            print(f"  - {song}")
        if len(songs) > 10:
            print(f"  ... and {len(songs) - 10} more")
    
    return sections

if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "pdfs/stevie%20rays%20sep.pdf"
    analyze_pdf_structure(pdf_path)

