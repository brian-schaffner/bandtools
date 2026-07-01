#!/usr/bin/env python3
"""
Debug script to examine Stevie Rays PDF text
"""
import sys
from pathlib import Path
sys.path.append('src')

# Import the function directly
def read_text_from_file(path):
    """Read text from PDF using the same logic as pdf_to_titles.py"""
    import subprocess
    import tempfile
    
    # Use pdftotext to extract text
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tmp_txt:
        try:
            subprocess.run(['pdftotext', str(path), tmp_txt.name], check=True, capture_output=True)
            with open(tmp_txt.name, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        finally:
            try:
                Path(tmp_txt.name).unlink()
            except Exception:
                pass
    # fallback: try to read as text anyway
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        # last resort: decode bytes
        return path.read_bytes().decode("utf-8", errors="replace")

# Read the raw text
pdf_path = Path('pdfs/stevie%20rays%20sep.pdf')
text = read_text_from_file(pdf_path)
lines = text.splitlines()

print('Looking for Extras section in raw text...')
for i, line in enumerate(lines):
    if 'extras' in line.lower() or 'dreams' in line.lower() or 'ex' in line.lower():
        print(f'Line {i}: {repr(line)}')
        # Show context
        for j in range(max(0, i-2), min(len(lines), i+3)):
            if j != i:
                print(f'  {j}: {repr(lines[j])}')
        print()
