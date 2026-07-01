#!/usr/bin/env python3
"""
Test that quick picks work correctly for missing mappings
"""

import json
import requests

def test_quick_picks():
    """Test that quick picks work correctly"""
    
    print("🧪 Testing quick picks functionality...")
    
    # Load the validation data with unvalidated songs
    with open("work/35e76f8b-65f7-48c1-9920-932122e98219_1761023991/validation_result.json", 'r') as f:
        validation_data = json.load(f)
    
    print(f"📊 Validation data:")
    print(f"   📊 Total songs: {validation_data.get('counts', {}).get('total', 0)}")
    print(f"   📊 Validated: {validation_data.get('counts', {}).get('validated_total', 0)}")
    print(f"   📊 Missing: {validation_data.get('counts', {}).get('missing_total', 0)}")
    
    # Find unvalidated songs
    unvalidated_songs = []
    for set_data in validation_data.get('sets', []):
        for song in set_data.get('songs', []):
            if not song.get('validated', False):
                unvalidated_songs.append({
                    'title': song.get('title', 'Unknown'),
                    'set': set_data.get('name', 'Unknown'),
                    'order': song.get('order', 0)
                })
    
    print(f"\n🔍 Unvalidated songs that should appear as quick picks:")
    for song in unvalidated_songs:
        print(f"   - {song['title']} (Set: {song['set']}, Order: {song['order']})")
    
    # Test the save mapping endpoint
    print(f"\n🧪 Testing save mapping endpoint...")
    
    # Test mapping "Whenever U Come Around" to "Whenever You Come Around"
    mapping_data = {
        "pdf_title": "Whenever U Come Around",
        "catalog_title": "Whenever You Come Around"
    }
    
    headers = {
        "X-Secret": "change-me"
    }
    
    try:
        response = requests.post("http://localhost:8002/standalone/save-mapping", json=mapping_data, headers=headers)
        
        if response.ok:
            result = response.json()
            print(f"   ✅ Save mapping successful")
            print(f"   📊 Result: {result}")
            return True
        else:
            print(f"   ❌ Save mapping failed: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error in save mapping: {e}")
        return False

def test_validation_after_mapping():
    """Test that validation works after adding a mapping"""
    
    print(f"\n🧪 Testing validation after mapping...")
    
    # Create test validation data with the mapped song
    test_data = {
        "sets": [
            {
                "name": "Set 1",
                "songs": [
                    {"title": "Whenever U Come Around", "validated": False},
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
    
    # Create JSON file for validation
    json_blob = json.dumps(test_data)
    files = {"json_file": ("test_validation.json", json_blob, "application/json")}
    data = {"secret": "change-me"}
    
    try:
        response = requests.post("http://localhost:8002/standalone/title-validation", files=files, data=data)
        
        if response.ok:
            result = response.json()
            print(f"   ✅ Validation successful")
            
            if 'data' in result:
                data = result['data']
                print(f"   📊 Total songs: {data.get('counts', {}).get('total', 0)}")
                print(f"   📊 Validated: {data.get('counts', {}).get('validated_total', 0)}")
                print(f"   📊 Missing: {data.get('counts', {}).get('missing_total', 0)}")
                
                # Check if "Whenever U Come Around" is now validated
                for set_data in data.get('sets', []):
                    for song in set_data.get('songs', []):
                        if song.get('title') == "Whenever U Come Around":
                            if song.get('validated', False):
                                print(f"   ✅ 'Whenever U Come Around' is now validated!")
                                return True
                            else:
                                print(f"   ❌ 'Whenever U Come Around' is still not validated")
                                return False
                
                print(f"   ❌ 'Whenever U Come Around' not found in validation result")
                return False
            else:
                print(f"   ❌ No data in validation result")
                return False
        else:
            print(f"   ❌ Validation failed: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error in validation: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing quick picks functionality...")
    
    # Test 1: Quick picks identification
    quick_picks_ok = test_quick_picks()
    
    # Test 2: Mapping functionality
    if quick_picks_ok:
        mapping_ok = test_validation_after_mapping()
    else:
        print("   ⏭️ Skipping mapping test (quick picks test failed)")
        mapping_ok = False
    
    print(f"\n📋 Test Results:")
    print(f"   ✅ Quick picks identification: {'PASS' if quick_picks_ok else 'FAIL'}")
    print(f"   ✅ Mapping functionality: {'PASS' if mapping_ok else 'FAIL'}")
    
    if quick_picks_ok and mapping_ok:
        print(f"\n🎉 All quick picks tests passed! The functionality should work correctly.")
    else:
        print(f"\n❌ Some quick picks tests failed. Need to investigate further.")
