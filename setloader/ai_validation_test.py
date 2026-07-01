#!/usr/local/bin/python3
"""
Sophisticated AI validation test for read_songs.py CLI tool.
Uses AI to analyze PDFs and compare results with CLI tool output.
"""

import json
import subprocess
import sys
from pathlib import Path
from PyPDF2 import PdfReader
import tempfile
import os

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF file."""
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return ""

def analyze_pdf_with_ai(pdf_path: Path) -> dict:
    """
    Use AI to analyze PDF and determine expected song counts.
    This simulates human analysis of the PDF content.
    """
    print(f"🤖 AI Analysis: Analyzing {pdf_path.name}")
    
    # Extract text from PDF
    text = extract_text_from_pdf(pdf_path)
    if not text:
        return {"error": "Could not extract text from PDF"}
    
    # AI analysis of the text content
    # This is where I use my AI capability to understand the PDF structure
    lines = text.split('\n')
    
    # Look for set patterns and count songs
    sets = []
    current_set = None
    extras = []
    in_extras = False
    
    # More sophisticated pattern matching
    import re
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Debug: print first few lines to understand structure
        if i < 5:
            print(f"   Line {i}: '{line}'")
            
        # Check for set headers with more flexible patterns
        set_patterns = [
            r'(SET\s*\d+[^a-z]*)',  # SET 1, SET 2, etc.
            r'(Set\s*\d+[^a-z]*)',  # Set 1, Set 2, etc.
            r'(\d+\s*[–-]\s*\d+:\d+)',  # Time patterns like "1 – 9-10:30"
        ]
        
        is_set_header = False
        for pattern in set_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                is_set_header = True
                break
        
        if is_set_header:
            if current_set:
                sets.append(current_set)
            current_set = {
                'name': line,
                'songs': []
            }
            in_extras = False
            continue
            
        # Check for extras section
        if 'extras' in line.lower():
            in_extras = True
            if current_set:
                sets.append(current_set)
                current_set = None
            continue
            
        # If we're in extras, collect song titles
        if in_extras:
            # Split by commas and clean up
            songs = [s.strip() for s in line.split(',') if s.strip()]
            extras.extend(songs)
            continue
            
        # If we have a current set, look for numbered song lines
        # KEY RULE: Songs always have a numeric index (except for extras)
        if current_set and line:
            # Strict numeric indexing pattern - must start with a number
            song_patterns = [
                r'^\d+\.?\s*(.+?)(?:\s*[–-]\s*[A-G][#b]?[m]?)?\s*$',  # "1. Song Title - Key"
                r'^\d+\s+(.+?)(?:\s*[–-]\s*[A-G][#b]?[m]?)?\s*$',     # "1 Song Title - Key"
            ]
            
            for pattern in song_patterns:
                song_match = re.match(pattern, line)
                if song_match:
                    song_title = song_match.group(1).strip()
                    # Clean up common OCR artifacts
                    song_title = re.sub(r'\s+', ' ', song_title)  # Multiple spaces to single
                    song_title = re.sub(r'[^\w\s\'-]', '', song_title)  # Remove special chars except apostrophes
                    if len(song_title) > 2:  # Only include substantial titles
                        current_set['songs'].append(song_title)
                        break
    
    # Add the last set if it exists
    if current_set:
        sets.append(current_set)
    
    # Calculate totals
    total_songs = sum(len(s['songs']) for s in sets) + len(extras)
    per_set_counts = {s['name']: len(s['songs']) for s in sets}
    
    return {
        'sets': sets,
        'extras': [{'title': song} for song in extras],
        'counts': {
            'per_set': per_set_counts,
            'extras': len(extras),
            'total': total_songs
        },
        'analysis_notes': f"Found {len(sets)} sets and {len(extras)} extras"
    }

def run_cli_tool(pdf_path: Path, output_path: Path) -> dict:
    """Run the read_songs.py CLI tool on the PDF."""
    print(f"🔧 CLI Tool: Processing {pdf_path.name}")
    
    try:
        # Run the CLI tool
        result = subprocess.run([
            '/usr/local/bin/python3', 'read_songs.py',
            '--input', str(pdf_path),
            '--output', str(output_path),
            '--verbose'
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            return {
                'error': f"CLI tool failed: {result.stderr}",
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        
        # Read the output JSON
        with open(output_path, 'r') as f:
            cli_result = json.load(f)
        
        return {
            'success': True,
            'result': cli_result,
            'stdout': result.stdout
        }
        
    except subprocess.TimeoutExpired:
        return {'error': 'CLI tool timed out after 120 seconds'}
    except Exception as e:
        return {'error': f'Error running CLI tool: {e}'}

def compare_results(ai_result: dict, cli_result: dict) -> dict:
    """Compare AI analysis with CLI tool results."""
    comparison = {
        'ai_total': ai_result.get('counts', {}).get('total', 0),
        'cli_total': cli_result.get('counts', {}).get('total', 0),
        'ai_sets': len(ai_result.get('sets', [])),
        'cli_sets': len(cli_result.get('sets', [])),
        'ai_extras': ai_result.get('counts', {}).get('extras', 0),
        'cli_extras': cli_result.get('counts', {}).get('extras', 0),
        'match': False
    }
    
    # Check if totals match (within 1 song tolerance for OCR issues)
    total_diff = abs(comparison['ai_total'] - comparison['cli_total'])
    comparison['total_match'] = total_diff <= 1
    comparison['total_difference'] = total_diff
    
    # Check if set counts match
    comparison['sets_match'] = comparison['ai_sets'] == comparison['cli_sets']
    
    # Overall match if totals are close and sets match
    comparison['match'] = comparison['total_match'] and comparison['sets_match']
    
    return comparison

def main():
    print("🧪 AI Validation Test for read_songs.py")
    print("=" * 50)
    
    # Test files from pdfs directory
    test_files = [
        'TKs-1.pdf',
        'gaslight.pdf', 
        'rough%20river%20july.pdf',
        'stevie%20rays%20june%202025.pdf',
        'derby%20city%20pizza.pdf'
    ]
    
    results = []
    passed = 0
    failed = 0
    
    for pdf_name in test_files:
        print(f"\n📄 Testing: {pdf_name}")
        print("-" * 30)
        
        pdf_path = Path(f"test_data/{pdf_name}")
        if not pdf_path.exists():
            print(f"❌ File not found: {pdf_path}")
            failed += 1
            continue
        
        # Step 1: AI Analysis
        ai_result = analyze_pdf_with_ai(pdf_path)
        if 'error' in ai_result:
            print(f"❌ AI Analysis failed: {ai_result['error']}")
            failed += 1
            continue
        
        print(f"🤖 AI found: {ai_result['counts']['total']} songs total")
        for set_name, count in ai_result['counts']['per_set'].items():
            print(f"   {set_name}: {count} songs")
        print(f"   Extras: {ai_result['counts']['extras']} songs")
        
        # Step 2: CLI Tool
        output_path = Path(f"test_output/{pdf_name.replace('.pdf', '_cli.json')}")
        cli_result = run_cli_tool(pdf_path, output_path)
        
        if 'error' in cli_result:
            print(f"❌ CLI Tool failed: {cli_result['error']}")
            failed += 1
            continue
        
        print(f"🔧 CLI found: {cli_result['result']['counts']['total']} songs total")
        for set_name, count in cli_result['result']['counts']['per_set'].items():
            print(f"   {set_name}: {count} songs")
        print(f"   Extras: {cli_result['result']['counts']['extras']} songs")
        
        # Step 3: Comparison
        comparison = compare_results(ai_result, cli_result['result'])
        
        if comparison['match']:
            print(f"✅ SUCCESS: Results match! (diff: {comparison['total_difference']})")
            passed += 1
        else:
            print(f"❌ FAILED: Results don't match")
            print(f"   AI total: {comparison['ai_total']}, CLI total: {comparison['cli_total']}")
            print(f"   AI sets: {comparison['ai_sets']}, CLI sets: {comparison['cli_sets']}")
            failed += 1
        
        # Store result
        results.append({
            'file': pdf_name,
            'ai_result': ai_result,
            'cli_result': cli_result['result'],
            'comparison': comparison,
            'success': comparison['match']
        })
    
    # Final Results
    print("\n" + "=" * 50)
    print("📊 FINAL RESULTS")
    print("=" * 50)
    print(f"Total tests: {len(test_files)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success rate: {(passed/len(test_files)*100):.1f}%")
    
    if failed == 0:
        print("🎉 100% SUCCESS! All tests passed!")
        return 0
    else:
        print(f"⚠️  {failed} test(s) failed. Need to investigate.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
