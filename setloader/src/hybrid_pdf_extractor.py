#!/usr/bin/env python3
"""
Hybrid PDF extraction combining AI and programmatic approaches
for maximum accuracy and reliability
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Set
import subprocess
from openai import OpenAI

class HybridPDFExtractor:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def extract_with_ai(self, pdf_path: Path) -> List[str]:
        """Use AI to extract song titles from PDF"""
        try:
            with open(pdf_path, "rb") as f:
                up = self.client.files.create(file=f, purpose="user_data")
            
            prompt = """
            Extract ONLY the song titles from ALL sets in this PDF. 
            Output plain text, one title per line. 
            No section headers, times, keys, or keysigs. No numbering.
            Be extremely thorough - this is for a production system.
            """
            
            response = self.client.responses.create(
                model="gpt-4o",
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_file", "file_id": up.id},
                        {"type": "input_text", "text": prompt},
                    ],
                }],
            )
            
            result_text = response.output_text.strip()
            lines = [line.strip() for line in result_text.split('\n') if line.strip()]
            
            # Clean up the titles
            cleaned_titles = []
            for title in lines:
                # Remove common artifacts
                title = re.sub(r'^\d+\.?\s*', '', title)  # Remove leading numbers
                title = re.sub(r'\s*[–-]\s*[A-G].*$', '', title)  # Remove keys
                title = re.sub(r'\s*\(.*\)$', '', title)  # Remove parentheticals
                title = title.strip()
                
                if title and len(title) >= 3:
                    cleaned_titles.append(title)
            
            return cleaned_titles
            
        except Exception as e:
            print(f"AI extraction error: {e}")
            return []
    
    def extract_programmatic(self, pdf_path: Path) -> List[str]:
        """Use programmatic extraction as fallback"""
        try:
            result = subprocess.run([
                "python3", "src/pdf_to_titles.py", 
                "--in", str(pdf_path), 
                "--out", "-"
            ], capture_output=True, text=True, check=True)
            
            titles = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            return titles
            
        except Exception as e:
            print(f"Programmatic extraction error: {e}")
            return []
    
    def filter_titles(self, titles: List[str]) -> List[str]:
        """Filter out non-song items"""
        filtered = []
        for title in titles:
            # Skip standalone numbers
            if title.isdigit() and len(title) <= 3:
                continue
            # Skip timing breaks
            if re.search(r'\d+:\d+', title):
                continue
            # Skip instructions
            if re.search(r'\b(detune|tune|capo|transpose|key|tempo|bpm)\b', title, re.IGNORECASE):
                continue
            # Skip headers
            if re.search(r'\b(set|mins?|minutes?|break|start|end|time|min\s*break)\b', title, re.IGNORECASE):
                continue
            
            if title and len(title) >= 3:
                filtered.append(title)
        
        return filtered
    
    def hybrid_extract(self, pdf_path: Path) -> List[str]:
        """Combine AI and programmatic extraction for maximum accuracy"""
        print("🤖 Starting hybrid PDF extraction...")
        
        # Step 1: AI extraction (primary)
        print("  Step 1: AI extraction...")
        ai_titles = self.extract_with_ai(pdf_path)
        print(f"    AI extracted: {len(ai_titles)} titles")
        
        # Step 2: Programmatic extraction (fallback)
        print("  Step 2: Programmatic extraction...")
        prog_titles = self.extract_programmatic(pdf_path)
        print(f"    Programmatic extracted: {len(prog_titles)} titles")
        
        # Step 3: Combine and deduplicate
        print("  Step 3: Combining results...")
        all_titles = list(set(ai_titles + prog_titles))
        print(f"    Combined unique titles: {len(all_titles)}")
        
        # Step 4: Filter out non-song items
        print("  Step 4: Filtering non-song items...")
        filtered_titles = self.filter_titles(all_titles)
        print(f"    Final filtered titles: {len(filtered_titles)}")
        
        return filtered_titles

def main():
    if len(sys.argv) < 3:
        print("Usage: python src/hybrid_pdf_extractor.py <pdf_file> <out_txt>")
        sys.exit(2)
    
    pdf_path = Path(sys.argv[1])
    out_txt = Path(sys.argv[2])
    
    extractor = HybridPDFExtractor()
    titles = extractor.hybrid_extract(pdf_path)
    
    # Write results
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    with open(out_txt, 'w', encoding='utf-8') as f:
        for title in titles:
            f.write(title + '\n')
    
    print(f"\n🎉 Hybrid extraction complete: {len(titles)} titles → {out_txt}")

if __name__ == "__main__":
    main()
