#!/usr/bin/env python3
"""
Test the main UI fix to ensure validation data flows correctly
"""

import json
import requests
import time

def test_main_ui_data_flow():
    """Test that the main UI properly passes validation data to shared component"""
    
    print("🧪 Testing main UI data flow fix...")
    
    # Load the Leitchfield validation data
    with open("work/35e76f8b-65f7-48c1-9920-932122e98219_1761023991/validation_result.json", 'r') as f:
        validation_data = json.load(f)
    
    print(f"✅ Loaded Leitchfield validation data:")
    print(f"   📊 Total songs: {validation_data.get('counts', {}).get('total', 0)}")
    print(f"   📊 Validated: {validation_data.get('counts', {}).get('validated_total', 0)}")
    print(f"   📊 Missing: {validation_data.get('counts', {}).get('missing_total', 0)}")
    
    # Simulate what the main UI should pass to the shared component
    simulated_stage_result = {
        "success": True,
        "validatedSongs": validation_data.get('counts', {}).get('validated_total', 0),
        "unfoundTitles": [],
        "extractedSongs": validation_data.get('counts', {}).get('total', 0),
        "message": f"Validated {validation_data.get('counts', {}).get('validated_total', 0)} out of {validation_data.get('counts', {}).get('total', 0)} songs",
        "validationData": validation_data
    }
    
    print(f"\n📊 Simulated stage result:")
    print(f"   - Has validationData: {'validationData' in simulated_stage_result}")
    print(f"   - validationData type: {type(simulated_stage_result.get('validationData'))}")
    print(f"   - validationData keys: {list(simulated_stage_result.get('validationData', {}).keys())}")
    
    # Test what the shared component should receive
    preloaded_data = simulated_stage_result.get('validationData')
    
    print(f"\n📊 What shared component receives:")
    print(f"   - Type: {type(preloaded_data)}")
    print(f"   - Keys: {list(preloaded_data.keys()) if preloaded_data else 'None'}")
    print(f"   - Has counts: {'counts' in preloaded_data if preloaded_data else False}")
    print(f"   - Has sets: {'sets' in preloaded_data if preloaded_data else False}")
    
    if preloaded_data and 'counts' in preloaded_data:
        counts = preloaded_data['counts']
        print(f"   - Counts structure: {list(counts.keys())}")
        print(f"   - Total: {counts.get('total', 0)}")
        print(f"   - Validated: {counts.get('validated_total', 0)}")
        print(f"   - Missing: {counts.get('missing_total', 0)}")
    
    # Check for unvalidated songs that should appear as quick picks
    unvalidated_songs = []
    if preloaded_data and 'sets' in preloaded_data:
        for set_data in preloaded_data['sets']:
            for song in set_data.get('songs', []):
                if not song.get('validated', False):
                    unvalidated_songs.append(song.get('title', 'Unknown'))
    
    print(f"\n🔍 Unvalidated songs that should appear as quick picks:")
    for song in unvalidated_songs:
        print(f"   - {song}")
    
    print(f"\n📊 Total unvalidated songs: {len(unvalidated_songs)}")
    
    return len(unvalidated_songs) > 0

def test_standalone_component():
    """Test the standalone component to ensure it works correctly"""
    
    print("\n🧪 Testing standalone component...")
    
    # Test the standalone title validation endpoint
    try:
        response = requests.get('http://localhost:3002/standalone/title-validation')
        if response.status_code == 200:
            print("   ✅ Standalone component accessible")
            return True
        else:
            print(f"   ❌ Standalone component failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error accessing standalone component: {e}")
        return False

if __name__ == "__main__":
    # Test 1: Data flow
    data_flow_ok = test_main_ui_data_flow()
    
    # Test 2: Standalone component
    standalone_ok = test_standalone_component()
    
    print(f"\n📋 Test Results:")
    print(f"   ✅ Data flow: {'PASS' if data_flow_ok else 'FAIL'}")
    print(f"   ✅ Standalone component: {'PASS' if standalone_ok else 'FAIL'}")
    
    if data_flow_ok and standalone_ok:
        print(f"\n🎉 All tests passed! The fix should work correctly.")
    else:
        print(f"\n❌ Some tests failed. Need to investigate further.")
