#!/usr/bin/env python3
"""
Debug script to test Ex's processing
"""
import sys
import re
sys.path.append('src')

def looks_like_title(raw: str) -> str | None:
    """Check if a line looks like a song title."""
    raw = raw.strip()
    if not raw or len(raw) < 3:
        return None
    
    # Filter out obvious non-song items
    if raw.lower() in ['set 1', 'set 2', 'set 3', 'set 4']:
        return None
    
    # Filter out timing information
    if re.search(r'\d+:\d+', raw) or re.search(r'\d+-\d+:\d+', raw):
        return None
    
    # Filter out break information
    if re.search(r'\d+\s*min\s*break', raw, re.I) or re.search(r'break', raw, re.I):
        return None
    
    # Filter out instructions
    if re.search(r'\b(detune|tune|capo|transpose|key|tempo|bpm)\b', raw, re.I):
        return None
    
    # Filter out lines starting with dashes or containing time patterns
    if raw.startswith('–') or raw.startswith('-') or re.search(r'\d+:\d+', raw):
        return None
    
    # Handle numbered lists
    numbered_match = re.match(r'^\s*(\d+)\.?\s*(.+?)(?:\s*[–-]\s*[A-G].*)?$', raw)
    if numbered_match:
        title = numbered_match.group(2).strip()
        # Additional filtering for numbered items
        if re.search(r'\d+:\d+', title) or re.search(r'break', title, re.I):
            return None
        return title
    
    # Handle lines with key signatures
    key_match = re.match(r'^(.+?)\s*[–-]\s*[A-G][#b]?[m]?$', raw)
    if key_match:
        return key_match.group(1).strip()
    
    # Regular title
    return raw

# Test different Ex's variants
test_cases = [
    "Ex's",
    "Ex's Ohs", 
    "Dreams, Ex's, Hot Child",
    "Ex's, Hot Child, Hate Myself"
]

print('Testing looks_like_title function:')
for test in test_cases:
    result = looks_like_title(test)
    print(f'  {repr(test)} -> {repr(result)}')

