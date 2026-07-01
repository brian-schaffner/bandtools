#!/usr/local/bin/python3
"""
Debug the song extraction process to see why "Get The Party Started" is missing.
"""

import requests
import json
import time
import sqlite3
from pathlib import Path

def test_song_extraction_with_party_started():
    """Test song extraction with Party Started mapped to Get The Party Started."""
    print("\n=== Testing Song Extraction with Party Started ===")
    
    # Create validation data with Party Started mapped
    validation_data = {
        "sets": [{
            "name": "Test Set",
            "songs": [
                {"title": "Hurts So Good", "validated": True, "song_id": 5, "validated_title": "Hurts So Good"},
                {"title": "Party Started", "validated": True, "song_id": 178, "validated_title": "Get The Party Started", "status": "Found through mapping"}
            ]
        }],
        "extras": [],
        "counts": {"total": 2, "validated_total": 2, "missing_total": 0}
    }
    
    print(f"Validation data: {validation_data}")
    
    # Run song extraction
    print("\n1. Running song extraction...")
    
    json_blob = json.dumps(validation_data).encode('utf-8')
    files = {"json_file": ("validated_input.json", json_blob, "application/json")}
    data = {"secret": "change-me", "set_name": "Test Set"}
    
    response = requests.post(
        "http://localhost:8002/standalone/song-extraction",
        files=files,
        data=data
    )
    
    if response.status_code != 200:
        raise Exception(f"Song extraction failed: {response.status_code} {response.text}")
    
    extraction_result = response.json()
    print(f"Song extraction result: {extraction_result.get('data', {}).get('statistics', {})}")
    
    # Check the SBP file
    sbp_path = extraction_result.get('data', {}).get('output_path')
    if not sbp_path:
        print("❌ No output path in extraction result")
        return False
    
    print(f"SBP file path: {sbp_path}")
    
    # Parse and verify the SBP file
    try:
        from sbp_library import SBPLibrary
        
        sbp_lib = SBPLibrary()
        sbp_file = sbp_lib.load_sbp_file(sbp_path)
        
        print(f"SBP file loaded successfully")
        print(f"Number of songs: {len(sbp_file.songs)}")
        print(f"Number of sets: {len(sbp_file.sets)}")
        
        # List all songs
        song_titles = [song.name for song in sbp_file.songs]
        print(f"All songs in SBP file: {song_titles}")
        
        # Check if "Get The Party Started" is in the songs
        if "Get The Party Started" in song_titles:
            print("✅ SUCCESS: 'Get The Party Started' found in SBP file!")
            
            # Find the song and check its details
            party_song = next((song for song in sbp_file.songs if song.name == "Get The Party Started"), None)
            if party_song:
                print(f"✅ Song details: ID={party_song.id}, Name='{party_song.name}'")
            
            return True
        else:
            print("❌ FAILURE: 'Get The Party Started' NOT found in SBP file")
            return False
            
    except Exception as e:
        print(f"❌ Error parsing SBP file: {e}")
        return False

def main():
    """Run the test."""
    print("=== Testing Song Extraction Debug ===")
    
    try:
        success = test_song_extraction_with_party_started()
        
        if success:
            print("\n🎉 SONG EXTRACTION DEBUG TEST PASSED!")
        else:
            print("\n❌ SONG EXTRACTION DEBUG TEST FAILED!")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
