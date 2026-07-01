#!/usr/bin/env python3
"""
AI-enhanced PDF text extraction for 100% accuracy
Uses AI to improve song title extraction from complex PDF layouts
"""

import os
import re
from pathlib import Path
from typing import List
from openai import OpenAI
import subprocess

class AIPDFExtractor:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def extract_with_ai(self, pdf_path: Path) -> List[str]:
        """Use AI to extract song titles from PDF with high accuracy"""
        try:
            with open(pdf_path, "rb") as f:
                up = self.client.files.create(file=f, purpose="user_data")
            
            prompt = """
You are an expert at extracting song titles from setlist PDFs. Extract ALL song titles from this PDF.

CRITICAL RULES:
1. Extract EVERY song title, including from multiple sets
2. Ignore headers like "SET 1", "SET 2", timing info, breaks
3. Ignore musical keys like "– F", "– G", etc.
4. Ignore "Detune" or other non-song items
5. Clean up titles (remove extra spaces, normalize)
6. Output one title per line, no numbering

Be extremely thorough - this is for a production system that needs 100% accuracy.
"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user", 
                    "content": [
                        {"type": "input_file", "file_id": up.id},
                        {"type": "input_text", "text": prompt}
                    ]
                }],
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content
            titles = [line.strip() for line in result_text.split('\n') if line.strip()]
            
            # Clean up the titles
            cleaned_titles = []
            for title in titles:
                # Remove common artifacts
                title = re.sub(r'^\d+\.?\s*', '', title)  # Remove numbering
                title = re.sub(r'\s*[–-]\s*[A-G].*$', '', title)  # Remove keys
                title = re.sub(r'\s*\(.*\)$', '', title)  # Remove parentheticals
                title = title.strip()
                
                if title and len(title) >= 3:
                    cleaned_titles.append(title)
            
            return cleaned_titles
            
        except Exception as e:
            print(f"AI extraction error: {e}")
            return []
    
    def hybrid_extract(self, pdf_path: Path) -> List[str]:
        """Combine traditional extraction with AI for maximum accuracy"""
        # First, try traditional extraction
        traditional_titles = self.traditional_extract(pdf_path)
        
        # Then, use AI to fill in gaps
        ai_titles = self.extract_with_ai(pdf_path)
        
        # Combine and deduplicate
        all_titles = list(set(traditional_titles + ai_titles))
        
        # Sort for consistency
        all_titles.sort()
        
        return all_titles
    
    def traditional_extract(self, pdf_path: Path) -> List[str]:
        """Traditional PDF text extraction as fallback"""
        try:
            # Use pdftotext
            result = subprocess.run(
                ['pdftotext', '-layout', '-nopgbrk', str(pdf_path), '-'],
                capture_output=True, text=True, check=True
            )
            
            text = result.stdout
            lines = text.split('\n')
            
            titles = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Look for numbered song titles
                numbered_match = re.match(r'^\s*(\d+)\.?\s*(.+?)(?:\s*[–-]\s*[A-G].*)?$', line)
                if numbered_match:
                    song_title = numbered_match.group(2).strip()
                    song_title = re.sub(r'^\s*\.+\s*', '', song_title)
                    song_title = song_title.strip()
                    
                    if song_title and len(song_title) >= 3:
                        titles.append(song_title)
                
                # Look for unnumbered song titles
                elif len(line) >= 3 and len(line) <= 50:
                    if not re.search(r'\b(set|mins?|minutes?|break|start|end|time|min\s*break)\b', line, re.IGNORECASE):
                        if not re.search(r'\d+:\d+', line):  # No time patterns
                            if not re.search(r'^\s*SET\s*\d+', line, re.IGNORECASE):  # No "SET 1"
                                if not re.search(r'break', line, re.IGNORECASE):  # No "break"
                                    clean_title = line.strip(" -–—~|•·.,_")
                                    if clean_title and len(clean_title) >= 3:
                                        titles.append(clean_title)
            
            return titles
            
        except Exception as e:
            print(f"Traditional extraction error: {e}")
            return []

def main():
    """Test the AI PDF extractor"""
    extractor = AIPDFExtractor()
    
    # Test with gaslight.pdf
    pdf_path = Path("pdfs/gaslight.pdf")
    if pdf_path.exists():
        print("🤖 AI PDF Extraction Test")
        print("=" * 40)
        
        # Test AI extraction
        ai_titles = extractor.extract_with_ai(pdf_path)
        print(f"AI extracted {len(ai_titles)} titles:")
        for i, title in enumerate(ai_titles, 1):
            print(f"  {i:2d}. {title}")
        
        print()
        
        # Test hybrid extraction
        hybrid_titles = extractor.hybrid_extract(pdf_path)
        print(f"Hybrid extracted {len(hybrid_titles)} titles:")
        for i, title in enumerate(hybrid_titles, 1):
            print(f"  {i:2d}. {title}")

if __name__ == "__main__":
    main()
