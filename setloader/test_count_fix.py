#!/usr/bin/env python3
"""
Test the count fix by simulating the mapping process.
"""

import requests
import json

def test_count_fix():
    """Test that the count fix works correctly."""
    
    print("🧪 Testing Count Fix")
    print("=" * 40)
    
    # Step 1: Upload test file with missing songs
    print("1️⃣ Uploading test file...")
    with open("test_unfound_titles.json", "rb") as f:
        files = {"json_file": f}
        data = {"secret": "change-me"}
        
        response = requests.post("http://localhost:8002/standalone/title-validation", 
                               files=files, data=data)
    
    if response.status_code != 200:
        print(f"❌ Upload failed: {response.status_code}")
        return
        
    result = response.json()
    print(f"✅ Initial validation: {result['data']['counts']['validated_total']} validated, {result['data']['counts']['missing_total']} missing")
    
    # Step 2: Save a mapping
    print("\n2️⃣ Saving a mapping...")
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
    
    # Step 3: Re-validate to see updated counts
    print("\n3️⃣ Re-validating with updated mappings...")
    with open("test_unfound_titles.json", "rb") as f:
        files = {"json_file": f}
        data = {"secret": "change-me"}
        
        response = requests.post("http://localhost:8002/standalone/title-validation", 
                               files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        counts = result['data']['counts']
        sets = result['data']['sets']
        
        print(f"✅ Updated validation: {counts['validated_total']} validated, {counts['missing_total']} missing")
        
        print("\n📋 Per Set Breakdown:")
        for set_data in sets:
            print(f"   {set_data['name']}: {set_data['validated_count']}/{set_data['validated_count'] + set_data['missing_count']} validated ({set_data['missing_count']} missing)")
        
        # Check for consistency
        total_validated = sum(set_data['validated_count'] for set_data in sets)
        total_missing = sum(set_data['missing_count'] for set_data in sets)
        
        print(f"\n🧮 Consistency Check:")
        print(f"   Per-set validated: {total_validated}")
        print(f"   Per-set missing: {total_missing}")
        print(f"   Overall validated: {counts['validated_total']}")
        print(f"   Overall missing: {counts['missing_total']}")
        
        if total_validated == counts['validated_total'] and total_missing == counts['missing_total']:
            print("✅ Counts are consistent!")
        else:
            print("❌ Counts are inconsistent!")
            
    else:
        print(f"❌ Re-validation failed: {response.status_code}")

if __name__ == "__main__":
    test_count_fix()
