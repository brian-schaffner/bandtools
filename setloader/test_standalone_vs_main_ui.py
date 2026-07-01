#!/usr/bin/env python3
"""
Test script to compare standalone component behavior vs main UI behavior
for quick pick mapping and re-validation.
"""

import requests
import json
import time

# Test configuration
BASE_URL = "http://localhost:8002"
SECRET = "change-me"

def test_standalone_behavior():
    """Test standalone component quick pick behavior."""
    
    print("🧪 Testing Standalone Component Quick Pick Behavior")
    print("=" * 60)
    
    # Step 1: Test standalone title validation with "Refuge"
    print("\n1. Testing standalone title validation with 'Refuge'...")
    test_data = {
        "sets": [
            {
                "name": "Set 1",
                "songs": [
                    {"title": "Refuge", "order": 1},
                    {"title": "3 steps", "order": 2},
                    {"title": "Hurt So Good", "order": 3}
                ]
            }
        ],
        "extras": []
    }
    
    try:
        # Create a temporary JSON file for testing
        with open("test_standalone_input.json", "w") as f:
            json.dump(test_data, f)
        
        # Test standalone title validation
        with open("test_standalone_input.json", "rb") as f:
            files = {"json_file": ("test_standalone_input.json", f, "application/json")}
            data = {"secret": SECRET}
            
            response = requests.post(f"{BASE_URL}/standalone/title-validation",
                                   files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Standalone validation successful")
            
            # Check if "Refuge" is in the unfound titles
            unfound_titles = []
            if "data" in result and "sets" in result["data"]:
                for set_data in result["data"]["sets"]:
                    if "songs" in set_data:
                        for song in set_data["songs"]:
                            if not song.get("validated", False):
                                unfound_titles.append(song.get("title", ""))
            
            print(f"   📋 Unfound titles: {unfound_titles}")
            
            if "Refuge" in unfound_titles:
                print("   ✅ 'Refuge' is correctly identified as unfound")
                return True
            else:
                print("   ❌ 'Refuge' should be unfound but isn't")
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
        if os.path.exists("test_standalone_input.json"):
            os.remove("test_standalone_input.json")

def test_standalone_mapping_and_revalidation():
    """Test standalone component mapping and re-validation behavior."""
    
    print("\n🧪 Testing Standalone Component Mapping + Re-validation")
    print("=" * 60)
    
    # Step 1: Save a mapping for "Refuge" -> "Refugee"
    print("\n1. Saving mapping 'Refuge' -> 'Refugee' via standalone endpoint...")
    try:
        response = requests.post(f"{BASE_URL}/standalone/save-mapping",
                               headers={"X-Secret": SECRET, "Content-Type": "application/json"},
                               json={"pdf_title": "Refuge", "catalog_title": "Refugee"})
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Mapping saved: {result.get('message', 'Success')}")
        else:
            print(f"   ❌ Failed to save mapping: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error saving mapping: {e}")
        return False
    
    # Step 2: Re-validate the same data to see if "Refuge" is now found
    print("\n2. Re-validating after mapping save...")
    test_data = {
        "sets": [
            {
                "name": "Set 1", 
                "songs": [
                    {"title": "Refuge", "order": 1},
                    {"title": "3 steps", "order": 2},
                    {"title": "Hurt So Good", "order": 3}
                ]
            }
        ],
        "extras": []
    }
    
    try:
        # Create a temporary JSON file for testing
        with open("test_standalone_input.json", "w") as f:
            json.dump(test_data, f)
        
        # Test standalone title validation again
        with open("test_standalone_input.json", "rb") as f:
            files = {"json_file": ("test_standalone_input.json", f, "application/json")}
            data = {"secret": SECRET}
            
            response = requests.post(f"{BASE_URL}/standalone/title-validation",
                                   files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Re-validation successful")
            
            # Check if "Refuge" is now validated
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
            
            if "Refuge" not in unfound_titles and validated_count > 0:
                print("   ✅ 'Refuge' is now found through mapping!")
                return True
            else:
                print("   ❌ 'Refuge' is still unfound after mapping")
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
        if os.path.exists("test_standalone_input.json"):
            os.remove("test_standalone_input.json")

def main():
    """Run the comparison test."""
    print("🚀 Starting Standalone vs Main UI Quick Pick Behavior Test")
    print("This test compares how standalone components handle quick pick mapping")
    print("vs how the main UI should handle it (after our fix).")
    print()
    
    # Wait a moment for server to be ready
    time.sleep(1)
    
    print("=" * 80)
    print("TESTING STANDALONE COMPONENT BEHAVIOR")
    print("=" * 80)
    
    # Test standalone behavior
    standalone_success = test_standalone_behavior()
    
    print("\n" + "=" * 80)
    print("TESTING STANDALONE MAPPING + RE-VALIDATION")
    print("=" * 80)
    
    # Test standalone mapping and re-validation
    mapping_success = test_standalone_mapping_and_revalidation()
    
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    if standalone_success and mapping_success:
        print("🎉 SUCCESS: Standalone components work correctly!")
        print("   - Initial validation correctly identifies unfound titles")
        print("   - Mapping save works correctly")
        print("   - Re-validation after mapping works correctly")
        print()
        print("✅ The main UI should now behave the same way after our fix.")
        print("   The main UI quick pick mapping now calls runTitleValidation()")
        print("   just like the standalone components do.")
    else:
        print("❌ FAILED: Standalone components have issues.")
        print("   This means there are problems with the backend validation logic.")
    
    return standalone_success and mapping_success

if __name__ == "__main__":
    main()
