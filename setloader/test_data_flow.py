#!/usr/bin/env python3
"""
Test the data flow from validation result to shared component
"""

import json

def test_data_flow():
    """Test the data flow structure"""
    
    print("🧪 Testing data flow structure...")
    
    # Load the validation result
    with open("work/35e76f8b-65f7-48c1-9920-932122e98219_1761023991/validation_result.json", 'r') as f:
        validation_data = json.load(f)
    
    print("📊 Validation data structure:")
    print(f"   - Keys: {list(validation_data.keys())}")
    print(f"   - Counts: {validation_data.get('counts', {})}")
    print(f"   - Sets: {len(validation_data.get('sets', []))}")
    
    # Simulate what runTitleValidation should return
    simulated_result = {
        "success": True,
        "validatedSongs": validation_data.get('counts', {}).get('validated_total', 0),
        "unfoundTitles": [],
        "extractedSongs": validation_data.get('counts', {}).get('total', 0),
        "message": f"Validated {validation_data.get('counts', {}).get('validated_total', 0)} out of {validation_data.get('counts', {}).get('total', 0)} songs",
        "validationData": validation_data
    }
    
    print("\n📊 Simulated runTitleValidation result:")
    print(f"   - Keys: {list(simulated_result.keys())}")
    print(f"   - validationData keys: {list(simulated_result.get('validationData', {}).keys())}")
    print(f"   - validationData counts: {simulated_result.get('validationData', {}).get('counts', {})}")
    
    # Check what the shared component should receive
    stage_result = simulated_result
    preloaded_data = stage_result.get('validationData') or stage_result
    
    print("\n📊 What shared component receives:")
    print(f"   - Type: {type(preloaded_data)}")
    print(f"   - Keys: {list(preloaded_data.keys())}")
    print(f"   - Has counts: {'counts' in preloaded_data}")
    print(f"   - Has sets: {'sets' in preloaded_data}")
    
    # Check for unvalidated songs
    unvalidated_count = 0
    for set_data in preloaded_data.get('sets', []):
        for song in set_data.get('songs', []):
            if not song.get('validated', False):
                unvalidated_count += 1
                print(f"   🔍 Unvalidated song: {song.get('title', 'Unknown')}")
    
    print(f"\n📊 Total unvalidated songs: {unvalidated_count}")
    
    return preloaded_data

if __name__ == "__main__":
    test_data_flow()
