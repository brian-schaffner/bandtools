#!/usr/bin/env python3
"""
Debug the TitleValidator to see if it's loading mappings correctly.
"""

import requests
import json
from pathlib import Path

def debug_title_validator():
    """Debug the TitleValidator mappings loading."""
    
    print("🔍 Debugging TitleValidator Mappings Loading")
    print("=" * 50)
    
    # Step 1: Save a mapping
    print("1️⃣ Saving a mapping...")
    mapping_data = {
        "pdf_title": "Unknown Song 1",
        "catalog_title": "Hurt So Good"
    }
    
    mapping_response = requests.post("http://localhost:8002/standalone/save-mapping", 
                                   json=mapping_data,
                                   headers={"X-Secret": "change-me"})
    
    if mapping_response.status_code == 200:
        print("✅ Mapping saved successfully")
    else:
        print(f"❌ Mapping save failed: {mapping_response.status_code}")
        return
    
    # Step 2: Test validation with a simple case
    print("\n2️⃣ Testing validation with simple case...")
    test_data = {
        "sets": [
            {
                "name": "Test Set",
                "songs": [
                    {"title": "Unknown Song 1", "key": "A"},
                    {"title": "Hurt So Good", "key": "B"}
                ]
            }
        ],
        "extras": [],
        "counts": {"total": 2}
    }
    
    # Save test data to file
    with open("test_debug_validator.json", "w") as f:
        json.dump(test_data, f)
    
    with open("test_debug_validator.json", "rb") as f:
        files = {"json_file": f}
        data = {"secret": "change-me"}
        
        response = requests.post("http://localhost:8002/standalone/title-validation", 
                               files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Validation completed")
        
        # Check the validation result
        sets = result['data']['sets']
        for set_data in sets:
            print(f"\n📋 {set_data['name']} songs:")
            for song in set_data['songs']:
                status_icon = "✅" if song['validated'] else "❌"
                print(f"   {status_icon} {song['title']} - {song['status']}")
        
        # Check if "Unknown Song 1" was validated
        unknown_song = None
        for set_data in sets:
            for song in set_data['songs']:
                if song['title'] == "Unknown Song 1":
                    unknown_song = song
                    break
        
        if unknown_song:
            if unknown_song['validated']:
                print("✅ Mapping is working! 'Unknown Song 1' was validated")
            else:
                print("❌ Mapping is NOT working! 'Unknown Song 1' was not validated")
                print(f"   Status: {unknown_song['status']}")
        else:
            print("❌ Could not find 'Unknown Song 1' in results")
            
    else:
        print(f"❌ Validation failed: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    debug_title_validator()