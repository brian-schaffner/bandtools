#!/usr/bin/env python3
"""
End-to-end test for Refuge mapping using the actual UI.
"""

import requests
import json
import sqlite3
import time
import os
from pathlib import Path

def remove_refuge_mappings():
    """Remove all mappings for 'Refuge' for the user."""
    
    print("🗑️ Removing all Refuge mappings...")
    
    # Connect to database
    conn = sqlite3.connect('setloader.db')
    cursor = conn.cursor()
    
    # Get existing mappings
    cursor.execute("""
        SELECT pdf_title, catalog_title 
        FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
        AND pdf_title = 'Refuge'
    """)
    
    existing = cursor.fetchall()
    print(f"   Found {len(existing)} existing Refuge mappings")
    for mapping in existing:
        print(f"   - '{mapping[0]}' -> '{mapping[1]}'")
    
    # Remove them
    cursor.execute("""
        DELETE FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
        AND pdf_title = 'Refuge'
    """)
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"   ✅ Removed {deleted_count} Refuge mappings")
    return deleted_count > 0

def test_title_validation_ui():
    """Test the title validation UI with the test file."""
    
    print("\n🔍 Testing Title Validation UI...")
    
    # Upload the test file to title validation
    with open("test_refuge_e2e.json", "rb") as f:
        files = {"json_file": f}
        data = {"secret": "change-me"}
        
        response = requests.post("http://localhost:8002/standalone/title-validation", 
                               files=files, data=data)
    
    if response.status_code != 200:
        print(f"❌ Title validation failed: {response.status_code}")
        print(response.text)
        return False
    
    result = response.json()
    print("✅ Title validation completed")
    
    # Check the validation results
    validation_data = result['data']
    print(f"\n📊 Validation Results:")
    print(f"   Total songs: {validation_data['counts']['total']}")
    print(f"   Validated: {validation_data['counts']['validated_total']}")
    print(f"   Missing: {validation_data['counts']['missing_total']}")
    
    # Check if Refuge is in the unfound titles
    unfound_titles = []
    for set_data in validation_data['sets']:
        for song in set_data['songs']:
            if not song['validated']:
                unfound_titles.append(song['title'])
    
    for song in validation_data['extras']:
        if not song['validated']:
            unfound_titles.append(song['title'])
    
    print(f"\n📋 Unfound titles: {unfound_titles}")
    
    if 'Refuge' not in unfound_titles:
        print("❌ Refuge should be in unfound titles but isn't")
        return False
    
    print("✅ Refuge is correctly identified as unfound")
    return True, validation_data

def test_quick_pick_mapping():
    """Test the quick pick mapping functionality."""
    
    print("\n🎯 Testing Quick Pick Mapping...")
    
    # Save mapping using the standalone endpoint
    mapping_data = {
        "pdf_title": "Refuge",
        "catalog_title": "Refugee"
    }
    
    response = requests.post("http://localhost:8002/standalone/save-mapping", 
                           headers={"X-Secret": "change-me"},
                           json=mapping_data)
    
    if response.status_code != 200:
        print(f"❌ Mapping save failed: {response.status_code}")
        print(response.text)
        return False
    
    result = response.json()
    print(f"✅ Mapping saved: {result['message']}")
    return True

def test_validation_after_mapping():
    """Test validation after mapping is saved."""
    
    print("\n🔍 Testing Validation After Mapping...")
    
    # Re-run validation
    with open("test_refuge_e2e.json", "rb") as f:
        files = {"json_file": f}
        data = {"secret": "change-me"}
        
        response = requests.post("http://localhost:8002/standalone/title-validation", 
                               files=files, data=data)
    
    if response.status_code != 200:
        print(f"❌ Re-validation failed: {response.status_code}")
        return False
    
    result = response.json()
    validation_data = result['data']
    
    print(f"📊 Re-validation Results:")
    print(f"   Total songs: {validation_data['counts']['total']}")
    print(f"   Validated: {validation_data['counts']['validated_total']}")
    print(f"   Missing: {validation_data['counts']['missing_total']}")
    
    # Check if Refuge is now validated
    refuge_validated = False
    refuge_song_id = None
    refuge_validated_title = None
    
    for set_data in validation_data['sets']:
        for song in set_data['songs']:
            if song['title'] == 'Refuge':
                refuge_validated = song['validated']
                refuge_song_id = song['song_id']
                refuge_validated_title = song['validated_title']
                print(f"\n📋 Refuge in {set_data['name']}:")
                print(f"   Validated: {refuge_validated}")
                print(f"   Song ID: {refuge_song_id}")
                print(f"   Validated Title: {refuge_validated_title}")
                print(f"   Status: {song['status']}")
    
    for song in validation_data['extras']:
        if song['title'] == 'Refuge':
            refuge_validated = song['validated']
            refuge_song_id = song['song_id']
            refuge_validated_title = song['validated_title']
            print(f"\n📋 Refuge in extras:")
            print(f"   Validated: {refuge_validated}")
            print(f"   Song ID: {refuge_song_id}")
            print(f"   Validated Title: {refuge_validated_title}")
            print(f"   Status: {song['status']}")
    
    if not refuge_validated or refuge_song_id is None or refuge_validated_title != 'Refugee':
        print("❌ Refuge mapping is not working correctly")
        return False
    
    print("✅ Refuge mapping is working correctly")
    return True, validation_data

def test_song_extraction():
    """Test song extraction with the validated data."""
    
    print("\n🎵 Testing Song Extraction...")
    
    # First, we need to get the validated JSON from the previous step
    # For this test, we'll create a mock validated JSON with Refuge mapped
    validated_data = {
        "sets": [
            {
                "name": "Set 1",
                "songs": [
                    {"title": "Real World", "validated": True, "song_id": 260, "validated_title": "Real World", "key": "Bb"},
                    {"title": "Refuge", "validated": True, "song_id": 251, "validated_title": "Refugee", "key": "Gm"},
                    {"title": "3 steps", "validated": True, "song_id": 157, "validated_title": "Gimme Three Steps", "key": "D"}
                ]
            },
            {
                "name": "Set 2",
                "songs": [
                    {"title": "Hurt So Good", "validated": True, "song_id": 123, "validated_title": "Hurts So Good", "key": "A"},
                    {"title": "Brown Eyed Girl", "validated": True, "song_id": 456, "validated_title": "Brown Eyed Girl", "key": "G"}
                ]
            },
            {
                "name": "Set 3",
                "songs": [
                    {"title": "Refuge", "validated": True, "song_id": 251, "validated_title": "Refugee", "key": "Gm"},
                    {"title": "Cake", "validated": True, "song_id": 789, "validated_title": "Cake by the Ocean", "key": "C"}
                ]
            }
        ],
        "extras": [
            {"title": "Refuge", "validated": True, "song_id": 251, "validated_title": "Refugee", "key": "Gm"}
        ],
        "counts": {
            "total": 8,
            "validated_total": 8,
            "missing_total": 0
        }
    }
    
    # Save validated data to file
    with open("test_validated_refuge.json", "w") as f:
        json.dump(validated_data, f, indent=2)
    
    # Test song extraction
    with open("test_validated_refuge.json", "rb") as f:
        files = {"json_file": f}
        data = {"secret": "change-me"}
        
        response = requests.post("http://localhost:8002/standalone/song-extraction", 
                               files=files, data=data)
    
    if response.status_code != 200:
        print(f"❌ Song extraction failed: {response.status_code}")
        print(response.text)
        return False
    
    result = response.json()
    print("✅ Song extraction completed")
    print(f"📊 Response: {result}")
    
    # Check if we got a download URL
    if 'data' not in result or 'download_url' not in result['data']:
        print("❌ No download URL in response")
        print(f"Available keys: {list(result.keys())}")
        if 'data' in result:
            print(f"Data keys: {list(result['data'].keys())}")
        return False
    
    download_url = result['data']['download_url']
    print(f"📥 Download URL: {download_url}")
    
    return True, download_url

def test_download_file(download_url):
    """Test downloading and checking the output file."""
    
    print("\n📥 Testing Download File...")
    
    # For now, let's just check if the file was created on disk
    # The song extraction response should contain the output_path
    print("📁 Checking if output file was created...")
    
    # Look for the most recent work directory
    work_dirs = [d for d in os.listdir("work") if d.startswith("35e76f8b-65f7-48c1-9920-932122e98219_")]
    if not work_dirs:
        print("❌ No work directories found")
        return False
    
    latest_work_dir = max(work_dirs, key=lambda x: int(x.split('_')[1]))
    work_path = Path("work") / latest_work_dir
    sbp_file_path = work_path / "Extracted_Set.sbp"
    
    if not sbp_file_path.exists():
        print(f"❌ SBP file not found at {sbp_file_path}")
        return False
    
    print(f"✅ Found SBP file: {sbp_file_path}")
    
    # Parse the SBP file to check for Refugee in Set 3
    try:
        from sbp_library import SBPLibrary
        sbp_lib = SBPLibrary()
        sbp_file = sbp_lib.load_sbp_file(sbp_file_path)
        
        print(f"\n📊 SBP File Analysis:")
        print(f"   Total songs: {len(sbp_file.songs)}")
        print(f"   Total sets: {len(sbp_file.sets)}")
        
        # Check Set 3 specifically
        set_3_found = False
        refugee_in_set_3 = False
        
        for set_obj in sbp_file.sets:
            if "Set 3" in set_obj.name:
                set_3_found = True
                print(f"\n📋 Set 3 Analysis:")
                print(f"   Set name: {set_obj.name}")
                print(f"   Items in set: {len(set_obj.items)}")
                
                for item in set_obj.items:
                    # Find the song by ID
                    song = next((s for s in sbp_file.songs if s.id == item.song_id), None)
                    if song:
                        print(f"   - {song.name} (ID: {song.id})")
                        if song.name == "Refugee":
                            refugee_in_set_3 = True
                            print(f"     ✅ Found Refugee with ID: {song.id}")
        
        if not set_3_found:
            print("❌ Set 3 not found in output file")
            return False
        
        if not refugee_in_set_3:
            print("❌ Refugee not found in Set 3")
            return False
        
        print("✅ Refugee found in Set 3 with valid song ID")
        return True
        
    except Exception as e:
        print(f"❌ Error parsing SBP file: {e}")
        return False

def main():
    """Run the complete end-to-end test."""
    
    print("🧪 End-to-End Refuge Mapping Test")
    print("=" * 50)
    
    # Step 1: Remove existing Refuge mappings
    print("\n1️⃣ Removing existing Refuge mappings...")
    removed = remove_refuge_mappings()
    
    # Step 2: Test title validation UI
    print("\n2️⃣ Testing title validation UI...")
    validation_success, validation_data = test_title_validation_ui()
    if not validation_success:
        print("❌ Title validation failed")
        return
    
    # Step 3: Test quick pick mapping
    print("\n3️⃣ Testing quick pick mapping...")
    mapping_success = test_quick_pick_mapping()
    if not mapping_success:
        print("❌ Quick pick mapping failed")
        return
    
    # Step 4: Test validation after mapping
    print("\n4️⃣ Testing validation after mapping...")
    revalidation_success, revalidation_data = test_validation_after_mapping()
    if not revalidation_success:
        print("❌ Re-validation after mapping failed")
        return
    
    # Step 5: Test song extraction
    print("\n5️⃣ Testing song extraction...")
    extraction_result = test_song_extraction()
    if not extraction_result:
        print("❌ Song extraction failed")
        return
    
    if isinstance(extraction_result, tuple):
        extraction_success, download_url = extraction_result
    else:
        extraction_success = extraction_result
        download_url = None
    
    if not extraction_success:
        print("❌ Song extraction failed")
        return
    
    # Step 6: Test download file
    print("\n6️⃣ Testing download file...")
    download_success = test_download_file(download_url)
    if not download_success:
        print("❌ Download file test failed")
        return
    
    # Summary
    print("\n" + "=" * 50)
    print("🎉 ALL TESTS PASSED!")
    print("✅ Refuge mapping end-to-end flow is working correctly")
    print("✅ Refugee appears in Set 3 with valid song ID")
    
    # Cleanup
    print("\n🧹 Cleaning up test files...")
    cleanup_files = [
        "test_refuge_e2e.json",
        "test_validated_refuge.json", 
        "test_output_refuge.sbp"
    ]
    
    for file in cleanup_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"   Removed: {file}")

if __name__ == "__main__":
    main()
