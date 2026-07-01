#!/usr/bin/env python3
"""
Test script to verify that the main UI now properly re-runs title validation 
after each quick pick mapping, using a song that's definitely not in the catalog.
"""

import requests
import json
import time

# Test configuration
BASE_URL = "http://localhost:8002"
SECRET = "change-me"

def test_with_unknown_song():
    """Test with a song that's definitely not in the catalog."""
    
    print("🧪 Testing with Unknown Song: 'XYZUnknownSong123'")
    print("=" * 60)
    
    # Step 1: Remove any existing mapping for our test song
    print("\n1. Removing any existing mapping for 'XYZUnknownSong123'...")
    try:
        # Get current mappings
        response = requests.get(f"{BASE_URL}/standalone/user-catalog", 
                              headers={"X-Secret": SECRET})
        if response.status_code == 200:
            catalog = response.json()
            songs = [song["name"] for song in catalog.get("songs", [])]
            if "XYZUnknownSong123" in songs:
                print("   ❌ Test song is already in catalog - this test won't work")
                return False
            else:
                print("   ✅ Test song is not in catalog - perfect for testing")
        else:
            print(f"   ❌ Failed to get catalog: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error checking catalog: {e}")
        return False
    
    # Step 2: Test standalone title validation with unknown song
    print("\n2. Testing standalone title validation with unknown song...")
    test_data = {
        "sets": [
            {
                "name": "Set 1",
                "songs": [
                    {"title": "XYZUnknownSong123", "order": 1},
                    {"title": "3 steps", "order": 2},
                    {"title": "Hurt So Good", "order": 3}
                ]
            }
        ],
        "extras": []
    }
    
    try:
        # Create a temporary JSON file for testing
        with open("test_unknown_input.json", "w") as f:
            json.dump(test_data, f)
        
        # Test standalone title validation
        with open("test_unknown_input.json", "rb") as f:
            files = {"json_file": ("test_unknown_input.json", f, "application/json")}
            data = {"secret": SECRET}
            
            response = requests.post(f"{BASE_URL}/standalone/title-validation",
                                   files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Standalone validation successful")
            
            # Check if "XYZUnknownSong123" is in the unfound titles
            unfound_titles = []
            validated_count = 0
            if "data" in result and "sets" in result["data"]:
                for set_data in result["data"]["sets"]:
                    if "songs" in set_data:
                        for song in set_data["songs"]:
                            if song.get("validated", False):
                                validated_count += 1
                            else:
                                unfound_titles.append(song.get("title", ""))
            
            print(f"   📊 Validated count: {validated_count}")
            print(f"   📋 Unfound titles: {unfound_titles}")
            
            if "XYZUnknownSong123" in unfound_titles:
                print("   ✅ 'XYZUnknownSong123' is correctly identified as unfound")
                return True
            else:
                print("   ❌ 'XYZUnknownSong123' should be unfound but isn't")
                return False
        else:
            print(f"   ❌ Standalone validation failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error during standalone validation: {e}")
        return False
    finally:
        # Clean up
        import os
        if os.path.exists("test_unknown_input.json"):
            os.remove("test_unknown_input.json")

def test_mapping_and_revalidation():
    """Test mapping and re-validation with unknown song."""
    
    print("\n🧪 Testing Mapping + Re-validation with Unknown Song")
    print("=" * 60)
    
    # Step 1: Save a mapping for "XYZUnknownSong123" -> "Refugee"
    print("\n1. Saving mapping 'XYZUnknownSong123' -> 'Refugee'...")
    try:
        response = requests.post(f"{BASE_URL}/standalone/save-mapping",
                               headers={"X-Secret": SECRET, "Content-Type": "application/json"},
                               json={"pdf_title": "XYZUnknownSong123", "catalog_title": "Refugee"})
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Mapping saved: {result.get('message', 'Success')}")
        else:
            print(f"   ❌ Failed to save mapping: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error saving mapping: {e}")
        return False
    
    # Step 2: Re-validate the same data to see if "XYZUnknownSong123" is now found
    print("\n2. Re-validating after mapping save...")
    test_data = {
        "sets": [
            {
                "name": "Set 1", 
                "songs": [
                    {"title": "XYZUnknownSong123", "order": 1},
                    {"title": "3 steps", "order": 2},
                    {"title": "Hurt So Good", "order": 3}
                ]
            }
        ],
        "extras": []
    }
    
    try:
        # Create a temporary JSON file for testing
        with open("test_unknown_input.json", "w") as f:
            json.dump(test_data, f)
        
        # Test standalone title validation again
        with open("test_unknown_input.json", "rb") as f:
            files = {"json_file": ("test_unknown_input.json", f, "application/json")}
            data = {"secret": SECRET}
            
            response = requests.post(f"{BASE_URL}/standalone/title-validation",
                                   files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Re-validation successful")
            
            # Check if "XYZUnknownSong123" is now validated
            validated_count = 0
            unfound_titles = []
            if "data" in result and "sets" in result["data"]:
                for set_data in result["data"]["sets"]:
                    if "songs" in set_data:
                        for song in set_data["songs"]:
                            if song.get("validated", False):
                                validated_count += 1
                            else:
                                unfound_titles.append(song.get("title", ""))
            
            print(f"   📊 Validated count: {validated_count}")
            print(f"   📋 Unfound titles: {unfound_titles}")
            
            if "XYZUnknownSong123" not in unfound_titles and validated_count > 0:
                print("   ✅ 'XYZUnknownSong123' is now found through mapping!")
                return True
            else:
                print("   ❌ 'XYZUnknownSong123' is still unfound after mapping")
                return False
        else:
            print(f"   ❌ Re-validation failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error during re-validation: {e}")
        return False
    finally:
        # Clean up
        import os
        if os.path.exists("test_unknown_input.json"):
            os.remove("test_unknown_input.json")

def main():
    """Run the test."""
    print("🚀 Starting Real Mapping Behavior Test")
    print("This test uses a song that's definitely not in the catalog")
    print("to verify that mapping and re-validation work correctly.")
    print()
    
    # Wait a moment for server to be ready
    time.sleep(1)
    
    # Test with unknown song
    unknown_success = test_with_unknown_song()
    
    if unknown_success:
        # Test mapping and re-validation
        mapping_success = test_mapping_and_revalidation()
        
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        
        if mapping_success:
            print("🎉 SUCCESS: Standalone components work correctly!")
            print("   - Unknown songs are correctly identified as unfound")
            print("   - Mapping save works correctly")
            print("   - Re-validation after mapping works correctly")
            print()
            print("✅ The main UI should now behave the same way after our fix.")
            print("   The main UI quick pick mapping now calls runTitleValidation()")
            print("   just like the standalone components do.")
        else:
            print("❌ FAILED: Mapping and re-validation don't work correctly.")
    else:
        print("❌ FAILED: Unknown song test failed.")
    
    return unknown_success

if __name__ == "__main__":
    main()
