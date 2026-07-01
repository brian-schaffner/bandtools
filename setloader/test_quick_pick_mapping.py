#!/usr/local/bin/python3
"""
Test the quick pick mapping functionality to verify it sets the correct song_id.
"""

import requests
import json
import time
import sqlite3
from pathlib import Path

def remove_party_started_mapping():
    """Remove the mapping for 'Get The Party Started' from the database."""
    conn = sqlite3.connect("setloader.db")
    cursor = conn.cursor()
    
    cursor.execute(
        "DELETE FROM title_mappings WHERE pdf_title LIKE ? OR catalog_title LIKE ?",
        ("%Party Started%", "%Get The Party Started%")
    )
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"Removed {deleted_count} existing mappings for 'Get The Party Started'")

def test_quick_pick_mapping():
    """Test the quick pick mapping functionality."""
    print("\n=== Testing Quick Pick Mapping ===")
    
    # Step 1: Create validation data with "Party Started" as missing
    print("\n1. Creating validation data...")
    
    validation_data = {
        "sets": [{
            "name": "Test Set",
            "songs": [
                {"title": "Hurts So Good", "validated": True, "song_id": 5, "validated_title": "Hurts So Good"},
                {"title": "Party Started", "validated": False, "song_id": None, "validated_title": "Party Started"}
            ]
        }],
        "extras": [],
        "counts": {"total": 2, "validated_total": 1, "missing_total": 1}
    }
    
    print(f"Initial validation data: {validation_data['counts']}")
    
    # Step 2: Run initial validation
    print("\n2. Running initial validation...")
    
    json_blob = json.dumps(validation_data).encode('utf-8')
    files = {"json_file": ("validation_input.json", json_blob, "application/json")}
    data = {"secret": "change-me"}
    
    response = requests.post(
        "http://localhost:8002/standalone/title-validation",
        files=files,
        data=data
    )
    
    if response.status_code != 200:
        raise Exception(f"Title validation failed: {response.status_code} {response.text}")
    
    validation_result = response.json()
    print(f"Initial validation result: {validation_result.get('data', {}).get('counts', {})}")
    
    # Step 3: Map "Party Started" to "Get The Party Started"
    print("\n3. Mapping 'Party Started' to 'Get The Party Started'...")
    
    mapping_data = {
        "pdf_title": "Party Started",
        "catalog_title": "Get The Party Started"
    }
    
    response = requests.post(
        "http://localhost:8002/standalone/save-mapping",
        json=mapping_data,
        headers={"X-Secret": "change-me"}
    )
    
    if response.status_code != 200:
        raise Exception(f"Save mapping failed: {response.status_code} {response.text}")
    
    mapping_result = response.json()
    print(f"Mapping saved: {mapping_result}")
    
    # Step 4: Re-run validation to get updated results
    print("\n4. Re-running validation after mapping...")
    
    response = requests.post(
        "http://localhost:8002/standalone/title-validation",
        files=files,
        data=data
    )
    
    if response.status_code != 200:
        raise Exception(f"Re-validation failed: {response.status_code} {response.text}")
    
    revalidation_result = response.json()
    print(f"Re-validation result: {revalidation_result.get('data', {}).get('counts', {})}")
    
    # Step 5: Check if the mapped song has the correct song_id
    print("\n5. Checking mapped song details...")
    
    validation_data = revalidation_result.get('data', {})
    for set_data in validation_data.get('sets', []):
        for song in set_data.get('songs', []):
            if song.get('title') == 'Party Started':
                print(f"Party Started song details:")
                print(f"  - validated: {song.get('validated')}")
                print(f"  - validated_title: {song.get('validated_title')}")
                print(f"  - song_id: {song.get('song_id')}")
                print(f"  - status: {song.get('status')}")
                
                if song.get('song_id') == 178:
                    print("✅ SUCCESS: song_id is correctly set to 178")
                    return True
                else:
                    print(f"❌ FAILURE: song_id is {song.get('song_id')}, expected 178")
                    return False
    
    print("❌ FAILURE: Could not find 'Party Started' in validation result")
    return False

def main():
    """Run the test."""
    print("=== Testing Quick Pick Mapping ===")
    
    try:
        # Step 1: Remove existing mapping
        print("\n1. Removing existing mapping...")
        remove_party_started_mapping()
        
        # Step 2: Test the quick pick mapping
        success = test_quick_pick_mapping()
        
        if success:
            print("\n🎉 QUICK PICK MAPPING TEST PASSED!")
        else:
            print("\n❌ QUICK PICK MAPPING TEST FAILED!")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
