#!/usr/bin/env python3
"""
Hybrid PDF Extractor - Combines AI and traditional extraction for reliability
Falls back to traditional extraction if AI extraction is incomplete
"""

import subprocess
import sys
from pathlib import Path

def extract_with_ai(pdf_path, output_path):
    """Extract using AI method"""
    try:
        result = subprocess.run([
            "python3", "src/ai_reader.py",
            str(pdf_path),
            str(output_path)
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            # Count extracted songs
            with open(output_path, 'r', encoding='utf-8') as f:
                songs = [line.strip() for line in f if line.strip()]
            return len(songs), songs
        else:
            print(f"AI extraction failed: {result.stderr}")
            return 0, []
    except Exception as e:
        print(f"AI extraction error: {e}")
        return 0, []

def extract_with_traditional(pdf_path, output_path):
    """Extract using traditional method"""
    try:
        result = subprocess.run([
            "python3", "src/pdf_to_titles.py",
            "--in", str(pdf_path),
            "--out", str(output_path)
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            # Count extracted songs
            with open(output_path, 'r', encoding='utf-8') as f:
                songs = [line.strip() for line in f if line.strip()]
            return len(songs), songs
        else:
            print(f"Traditional extraction failed: {result.stderr}")
            return 0, []
    except Exception as e:
        print(f"Traditional extraction error: {e}")
        return 0, []

def hybrid_extract(pdf_path, output_path, expected_count=59):
    """
    Hybrid extraction: Try AI first, fallback to traditional if incomplete
    """
    print(f"🔍 Starting hybrid extraction for {pdf_path}")
    print(f"Expected song count: {expected_count}")
    
    # Try AI extraction first
    print("🤖 Attempting AI extraction...")
    ai_count, ai_songs = extract_with_ai(pdf_path, output_path)
    print(f"AI extraction result: {ai_count} songs")
    
    if ai_count >= expected_count:
        print("✅ AI extraction successful!")
        return ai_count, ai_songs
    
    print(f"⚠️  AI extraction incomplete ({ai_count}/{expected_count} songs)")
    print("🔄 Falling back to traditional extraction...")
    
    # Try traditional extraction
    traditional_count, traditional_songs = extract_with_traditional(pdf_path, output_path)
    print(f"Traditional extraction result: {traditional_count} songs")
    
    if traditional_count >= expected_count:
        print("✅ Traditional extraction successful!")
        # Write traditional results to output
        with open(output_path, 'w', encoding='utf-8') as f:
            for song in traditional_songs:
                f.write(song + '\n')
        return traditional_count, traditional_songs
    
    # If both methods are incomplete, use the better one
    if ai_count > traditional_count:
        print(f"📊 Using AI results ({ai_count} songs) - better than traditional ({traditional_count})")
        with open(output_path, 'w', encoding='utf-8') as f:
            for song in ai_songs:
                f.write(song + '\n')
        return ai_count, ai_songs
    else:
        print(f"📊 Using traditional results ({traditional_count} songs) - better than AI ({ai_count})")
        with open(output_path, 'w', encoding='utf-8') as f:
            for song in traditional_songs:
                f.write(song + '\n')
        return traditional_count, traditional_songs

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 hybrid_extractor.py <pdf_path> <output_path>")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    
    count, songs = hybrid_extract(pdf_path, output_path)
    print(f"🎯 Final result: {count} songs extracted")
    
    if count >= 59:
        print("✅ Extraction meets requirements!")
        sys.exit(0)
    else:
        print(f"❌ Extraction incomplete: {count}/59 songs")
        sys.exit(1)
