#!/usr/bin/env python3
"""
AI-powered title mapping system for 100% accuracy
Uses multiple AI models and ML techniques to map unfound titles
"""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
from openai import OpenAI
import difflib

class AITitleMapper:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.catalog = []
        self.load_catalog()
    
    def load_catalog(self):
        """Load the user's song catalog"""
        try:
            # Load from user's backup
            backup_path = "uploads/SongbookPro Backup.sbpbackup"
            if os.path.exists(backup_path):
                import zipfile
                with zipfile.ZipFile(backup_path, 'r') as zip_file:
                    with zip_file.open('dataFile.txt') as f:
                        content = f.read().decode('utf-8')
                
                # Parse the JSON
                lines = content.strip().split('\n')
                if len(lines) > 1 and lines[0].strip().replace('.', '').isdigit():
                    json_content = '\n'.join(lines[1:])
                else:
                    json_content = content
                
                data = json.loads(json_content)
                songs = data.get('songs', [])
                
                # Extract song titles
                for song in songs:
                    if isinstance(song, dict):
                        title = song.get('title') or song.get('name')
                        if isinstance(title, str) and title.strip():
                            self.catalog.append(title.strip())
                
                print(f"Loaded {len(self.catalog)} songs from catalog")
        except Exception as e:
            print(f"Error loading catalog: {e}")
    
    def ai_map_title(self, unfound_title: str) -> Dict:
        """Use AI to map an unfound title to the catalog"""
        try:
            # Create a prompt with the unfound title and catalog
            catalog_sample = self.catalog[:50]  # Use first 50 songs as context
            
            prompt = f"""
You are an expert at mapping song titles. I have an unfound title that needs to be mapped to a song in my catalog.

UNFOUND TITLE: "{unfound_title}"

CATALOG SAMPLE (first 50 songs):
{', '.join(catalog_sample)}

TASK: Find the best match for "{unfound_title}" in the catalog.

RULES:
1. Look for exact matches first
2. Then look for similar titles (abbreviations, variations, etc.)
3. Consider common song title variations
4. If no good match exists, return "NO_MATCH"

Provide your response in this exact format:
MATCHED_TITLE: [exact title from catalog or NO_MATCH]
CONFIDENCE: [0.0-1.0]
REASONING: [brief explanation]
"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content
            
            # Parse the response
            matched_title = None
            confidence = 0.0
            reasoning = ""
            
            for line in result_text.split('\n'):
                if line.startswith('MATCHED_TITLE:'):
                    matched_title = line.split(':', 1)[1].strip()
                elif line.startswith('CONFIDENCE:'):
                    try:
                        confidence = float(line.split(':', 1)[1].strip())
                    except:
                        pass
                elif line.startswith('REASONING:'):
                    reasoning = line.split(':', 1)[1].strip()
            
            return {
                'unfound_title': unfound_title,
                'matched_title': matched_title,
                'confidence': confidence,
                'reasoning': reasoning
            }
            
        except Exception as e:
            return {
                'unfound_title': unfound_title,
                'matched_title': 'NO_MATCH',
                'confidence': 0.0,
                'reasoning': f"Error: {e}"
            }
    
    def ml_fuzzy_match(self, unfound_title: str, threshold: float = 0.6) -> List[Tuple[str, float]]:
        """Use ML-based fuzzy matching to find similar titles"""
        matches = []
        
        for catalog_title in self.catalog:
            # Use difflib for fuzzy matching
            similarity = difflib.SequenceMatcher(None, unfound_title.lower(), catalog_title.lower()).ratio()
            
            if similarity >= threshold:
                matches.append((catalog_title, similarity))
        
        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:5]  # Return top 5 matches
    
    def batch_map_titles(self, unfound_titles: List[str]) -> Dict[str, Dict]:
        """Map multiple unfound titles using AI and ML"""
        results = {}
        
        for title in unfound_titles:
            print(f"Mapping: {title}")
            
            # Try AI mapping first
            ai_result = self.ai_map_title(title)
            
            # Try ML fuzzy matching as backup
            ml_matches = self.ml_fuzzy_match(title)
            
            # Combine results
            result = {
                'ai_result': ai_result,
                'ml_matches': ml_matches,
                'final_mapping': None
            }
            
            # Decide on final mapping
            if ai_result['matched_title'] != 'NO_MATCH' and ai_result['confidence'] > 0.7:
                result['final_mapping'] = ai_result['matched_title']
                result['method'] = 'AI'
            elif ml_matches and ml_matches[0][1] > 0.8:
                result['final_mapping'] = ml_matches[0][0]
                result['method'] = 'ML'
            else:
                result['final_mapping'] = None
                result['method'] = 'NONE'
            
            results[title] = result
            print(f"  → {result['final_mapping']} ({result['method']})")
        
        return results

def main():
    """Test the AI title mapper"""
    mapper = AITitleMapper()
    
    # Test with some unfound titles
    unfound_titles = [
        "Wake Me Sep",
        "Seen Rain", 
        "Marlenas",
        "Steps",
        "Mojo",
        "Brown Eyed",
        "Baby, Fire, Brown Eye"
    ]
    
    print("🤖 AI Title Mapping Test")
    print("=" * 40)
    
    results = mapper.batch_map_titles(unfound_titles)
    
    print("\n📊 Results:")
    for title, result in results.items():
        print(f"{title}: {result['final_mapping']} ({result['method']})")

if __name__ == "__main__":
    main()



