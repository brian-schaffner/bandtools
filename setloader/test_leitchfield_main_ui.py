#!/usr/bin/env python3
"""
Test the main UI with Leitchfield setlist to identify issues
"""

import json
import requests
import time

def test_main_ui_with_leitchfield():
    """Test the main UI workflow with Leitchfield setlist"""
    
    print("🧪 Testing main UI with Leitchfield setlist...")
    
    # Load the validation result from the work directory
    validation_file = "work/35e76f8b-65f7-48c1-9920-932122e98219_1761023991/validation_result.json"
    
    try:
        with open(validation_file, 'r') as f:
            validation_data = json.load(f)
        
        print(f"✅ Loaded validation data from {validation_file}")
        print(f"📊 Total songs: {validation_data.get('counts', {}).get('total', 0)}")
        print(f"📊 Validated: {validation_data.get('counts', {}).get('validated_total', 0)}")
        print(f"📊 Missing: {validation_data.get('counts', {}).get('missing_total', 0)}")
        
        # Find unvalidated songs
        unvalidated_songs = []
        for set_data in validation_data.get('sets', []):
            for song in set_data.get('songs', []):
                if not song.get('validated', False):
                    unvalidated_songs.append(song.get('title', 'Unknown'))
        
        print(f"🔍 Found {len(unvalidated_songs)} unvalidated songs:")
        for song in unvalidated_songs[:5]:  # Show first 5
            print(f"   - {song}")
        
        if len(unvalidated_songs) > 5:
            print(f"   ... and {len(unvalidated_songs) - 5} more")
        
        return validation_data
        
    except Exception as e:
        print(f"❌ Error loading validation data: {e}")
        return None

def test_standalone_title_validation():
    """Test the standalone title validation endpoint"""
    
    print("\n🧪 Testing standalone title validation endpoint...")
    
    # Create a test validation request
    test_data = {
        "sets": [
            {
                "name": "Set 1",
                "songs": [
                    {"title": "Refuge", "validated": False},
                    {"title": "Party Started", "validated": False}
                ]
            }
        ],
        "extras": [],
        "counts": {
            "total": 2,
            "validated_total": 0,
            "missing_total": 2
        }
    }
    
    # Create JSON file
    json_blob = json.dumps(test_data)
    form_data = {
        'json_file': ('test.json', json_blob, 'application/json'),
        'secret': 'change-me'
    }
    
    try:
        response = requests.post('http://localhost:8002/standalone/title-validation', files=form_data)
        if response.ok:
            result = response.json()
            print(f"   ✅ Standalone validation successful")
            print(f"   📊 Response structure: {list(result.keys())}")
            
            if 'data' in result:
                data = result['data']
                print(f"   📊 Data structure: {list(data.keys())}")
                print(f"   📊 Counts: {data.get('counts', {})}")
                
                # Check for quick picks
                if 'sets' in data:
                    for set_data in data['sets']:
                        for song in set_data.get('songs', []):
                            if not song.get('validated', False):
                                print(f"   🔍 Unvalidated song: {song.get('title', 'Unknown')}")
            
            return result
        else:
            print(f"   ❌ Standalone validation failed: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return None
    except Exception as e:
        print(f"   ❌ Error testing standalone validation: {e}")
        return None

if __name__ == "__main__":
    # Test 1: Load Leitchfield validation data
    validation_data = test_main_ui_with_leitchfield()
    
    # Test 2: Test standalone endpoint
    standalone_result = test_standalone_title_validation()
    
    print("\n📋 Summary:")
    if validation_data:
        print("✅ Leitchfield validation data loaded successfully")
    else:
        print("❌ Failed to load Leitchfield validation data")
    
    if standalone_result:
        print("✅ Standalone title validation endpoint working")
    else:
        print("❌ Standalone title validation endpoint failed")
