#!/usr/bin/env python3
"""
Test removing the Refuge mapping and then testing the quick pick flow.
"""

import requests
import json
import sqlite3

def remove_refuge_mapping():
    """Remove any existing mapping for 'Refuge'."""
    
    print("🗑️ Removing existing Refuge mapping...")
    
    # Connect to database
    conn = sqlite3.connect('setloader.db')
    cursor = conn.cursor()
    
    # Check if mapping exists
    cursor.execute("""
        SELECT pdf_title, catalog_title 
        FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
        AND pdf_title = 'Refuge'
    """)
    
    existing = cursor.fetchall()
    print(f"   Found {len(existing)} existing mappings for 'Refuge'")
    for mapping in existing:
        print(f"   - '{mapping[0]}' -> '{mapping[1]}'")
    
    # Remove the mapping
    cursor.execute("""
        DELETE FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
        AND pdf_title = 'Refuge'
    """)
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"   ✅ Removed {deleted_count} mappings for 'Refuge'")
    return deleted_count > 0

def test_refuge_validation():
    """Test validation of 'Refuge' without mapping."""
    
    print("\n🔍 Testing Refuge validation without mapping...")
    
    # Create test data with 'Refuge'
    test_data = {
        "sets": [
            {
                "name": "Test Set",
                "songs": [
                    {"title": "Refuge", "key": "Gm"}
                ]
            }
        ],
        "extras": [],
        "counts": {"total": 1}
    }
    
    with open("test_refuge_no_mapping.json", "w") as f:
        json.dump(test_data, f)
    
    with open("test_refuge_no_mapping.json", "rb") as f:
        files = {"json_file": f}
        data = {"secret": "change-me"}
        
        response = requests.post("http://localhost:8002/standalone/title-validation", 
                               files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Validation completed")
        
        # Check the result for "Refuge"
        for set_data in result['data']['sets']:
            for song in set_data['songs']:
                if song['title'] == "Refuge":
                    print(f"\n📋 Refuge Result (should show as NOT validated):")
                    print(f"   Title: {song['title']}")
                    print(f"   Validated: {song['validated']}")
                    print(f"   Status: {song['status']}")
                    print(f"   Song ID: {song['song_id']}")
                    print(f"   Validated Title: {song['validated_title']}")
                    
                    if not song['validated'] and song['status'] == "Not found in backup or mappings":
                        print("   ✅ Correct: No mapping found, shows as not validated")
                        return True
                    else:
                        print("   ❌ Unexpected: Should show as not validated")
                        return False
    else:
        print(f"❌ Validation failed: {response.status_code}")
        return False

def test_refuge_mapping_save():
    """Test saving a mapping for 'Refuge'."""
    
    print("\n💾 Testing Refuge mapping save...")
    
    # Save mapping
    mapping_data = {
        "pdf_title": "Refuge",
        "catalog_title": "Refugee"
    }
    
    response = requests.post("http://localhost:8002/standalone/save-mapping", 
                           headers={"X-Secret": "change-me"},
                           json=mapping_data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Mapping saved: {result['message']}")
        return True
    else:
        print(f"❌ Mapping save failed: {response.status_code}")
        return False

def test_refuge_validation_with_mapping():
    """Test validation of 'Refuge' with mapping."""
    
    print("\n🔍 Testing Refuge validation WITH mapping...")
    
    # Create test data with 'Refuge'
    test_data = {
        "sets": [
            {
                "name": "Test Set",
                "songs": [
                    {"title": "Refuge", "key": "Gm"}
                ]
            }
        ],
        "extras": [],
        "counts": {"total": 1}
    }
    
    with open("test_refuge_with_mapping.json", "w") as f:
        json.dump(test_data, f)
    
    with open("test_refuge_with_mapping.json", "rb") as f:
        files = {"json_file": f}
        data = {"secret": "change-me"}
        
        response = requests.post("http://localhost:8002/standalone/title-validation", 
                               files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Validation completed")
        
        # Check the result for "Refuge"
        for set_data in result['data']['sets']:
            for song in set_data['songs']:
                if song['title'] == "Refuge":
                    print(f"\n📋 Refuge Result (should show as validated):")
                    print(f"   Title: {song['title']}")
                    print(f"   Validated: {song['validated']}")
                    print(f"   Status: {song['status']}")
                    print(f"   Song ID: {song['song_id']}")
                    print(f"   Validated Title: {song['validated_title']}")
                    
                    if (song['validated'] and 
                        song['status'] == "Found through mapping" and 
                        song['song_id'] is not None and 
                        song['validated_title'] != song['title']):
                        print("   ✅ Correct: Mapping found and working")
                        return True
                    else:
                        print("   ❌ Unexpected: Should show as validated with mapping")
                        return False
    else:
        print(f"❌ Validation failed: {response.status_code}")
        return False

def main():
    """Run the complete test."""
    
    print("🧪 Testing Refuge Mapping Flow")
    print("=" * 50)
    
    # Step 1: Remove existing mapping
    removed = remove_refuge_mapping()
    
    # Step 2: Test without mapping (should show as not validated)
    print("\n" + "="*50)
    no_mapping_result = test_refuge_validation()
    
    # Step 3: Save mapping
    print("\n" + "="*50)
    mapping_saved = test_refuge_mapping_save()
    
    # Step 4: Test with mapping (should show as validated)
    print("\n" + "="*50)
    with_mapping_result = test_refuge_validation_with_mapping()
    
    # Summary
    print("\n" + "="*50)
    print("📊 Test Summary:")
    print(f"   Removed existing mapping: {removed}")
    print(f"   Without mapping (should be invalid): {no_mapping_result}")
    print(f"   Mapping saved successfully: {mapping_saved}")
    print(f"   With mapping (should be valid): {with_mapping_result}")
    
    if no_mapping_result and mapping_saved and with_mapping_result:
        print("\n🎉 All tests passed! The Refuge mapping flow is working correctly.")
    else:
        print("\n❌ Some tests failed. Check the output above.")

if __name__ == "__main__":
    main()
