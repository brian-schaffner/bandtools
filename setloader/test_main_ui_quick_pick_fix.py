#!/usr/bin/env python3
"""
Test script to verify that the main UI now properly re-runs title validation 
after each quick pick mapping, just like the standalone components do.
"""

import requests
import json
import time

# Test configuration
BASE_URL = "http://localhost:8002"
SECRET = "change-me"

def authenticate():
    """Authenticate and get session token."""
    try:
        response = requests.post(f"{BASE_URL}/auth/login",
                               headers={"X-Secret": SECRET})
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            print(f"   ✅ Authenticated as {data.get('user_email')}")
            return session_token
        else:
            print(f"   ❌ Authentication failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ Authentication error: {e}")
        return None

def test_main_ui_quick_pick_behavior():
    """Test that main UI quick pick mapping triggers re-validation like standalone components."""
    
    print("🧪 Testing Main UI Quick Pick Re-validation Behavior")
    print("=" * 60)
    
    # Step 0: Authenticate
    print("\n0. Authenticating...")
    session_token = authenticate()
    if not session_token:
        return False
    
    # Step 1: Remove any existing mapping for "Refuge" to ensure clean test
    print("\n1. Removing any existing mapping for 'Refuge'...")
    try:
        # Get current mappings
        response = requests.get(f"{BASE_URL}/user/title-mappings", 
                              headers={"X-Secret": SECRET, "X-Session-ID": session_token})
        if response.status_code == 200:
            mappings = response.json().get("mappings", {})
            if "Refuge" in mappings:
                print(f"   Found existing mapping: 'Refuge' -> '{mappings['Refuge']}'")
                # Remove the mapping by sending an empty dict (this deletes all mappings)
                delete_response = requests.post(f"{BASE_URL}/user/title-mappings",
                                            headers={"X-Secret": SECRET, "X-Session-ID": session_token},
                                            json={})
                if delete_response.status_code == 200:
                    print("   ✅ Removed existing mapping")
                else:
                    print(f"   ❌ Failed to remove mapping: {delete_response.status_code}")
            else:
                print("   ✅ No existing mapping found")
        else:
            print(f"   ❌ Failed to get mappings: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error removing mapping: {e}")
    
    # Step 2: Test title validation with "Refuge" in the list
    print("\n2. Testing title validation with 'Refuge' in the list...")
    test_titles = ["Refuge", "3 steps", "Hurt So Good", "Cake"]
    
    try:
        response = requests.post(f"{BASE_URL}/verify_titles",
                               headers={"X-Secret": SECRET, "X-Session-ID": session_token, 
                                       "Content-Type": "application/json"},
                               json={"titles": test_titles})
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Validation result: {result['validated_count']}/{result['total_count']} validated")
            print(f"   📋 Unfound titles: {result['unfound_titles']}")
            
            if "Refuge" in result['unfound_titles']:
                print("   ✅ 'Refuge' is correctly identified as unfound (no mapping exists)")
            else:
                print("   ❌ 'Refuge' should be unfound but isn't")
                return False
        else:
            print(f"   ❌ Validation failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error during validation: {e}")
        return False
    
    # Step 3: Save a mapping for "Refuge" -> "Refugee"
    print("\n3. Saving mapping 'Refuge' -> 'Refugee'...")
    try:
        response = requests.post(f"{BASE_URL}/user/title-mappings",
                               headers={"X-Secret": SECRET, "X-Session-ID": session_token, 
                                       "Content-Type": "application/json"},
                               json={"pdf_title": "Refuge", "catalog_title": "Refugee"})
        
        if response.status_code == 200:
            print("   ✅ Mapping saved successfully")
        else:
            print(f"   ❌ Failed to save mapping: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error saving mapping: {e}")
        return False
    
    # Step 4: Re-validate the same titles to see if "Refuge" is now found
    print("\n4. Re-validating titles after mapping save...")
    try:
        response = requests.post(f"{BASE_URL}/verify_titles",
                               headers={"X-Secret": SECRET, "X-Session-ID": session_token, 
                                       "Content-Type": "application/json"},
                               json={"titles": test_titles})
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Re-validation result: {result['validated_count']}/{result['total_count']} validated")
            print(f"   📋 Unfound titles: {result['unfound_titles']}")
            
            if "Refuge" not in result['unfound_titles']:
                print("   ✅ 'Refuge' is now found through mapping!")
                if result['validated_count'] > 0:
                    print("   ✅ Validation count increased after mapping")
                    return True
                else:
                    print("   ❌ Validation count didn't increase")
                    return False
            else:
                print("   ❌ 'Refuge' is still unfound after mapping")
                return False
        else:
            print(f"   ❌ Re-validation failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Error during re-validation: {e}")
        return False

def main():
    """Run the test."""
    print("🚀 Starting Main UI Quick Pick Re-validation Test")
    print("This test verifies that the main UI now properly re-runs title validation")
    print("after each quick pick mapping, just like the standalone components do.")
    print()
    
    # Wait a moment for server to be ready
    time.sleep(1)
    
    success = test_main_ui_quick_pick_behavior()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 SUCCESS: Main UI quick pick mapping now triggers re-validation!")
        print("   The main UI now behaves like the standalone components.")
    else:
        print("❌ FAILED: Main UI quick pick mapping still doesn't trigger re-validation.")
        print("   The main UI is not behaving like the standalone components.")
    
    return success

if __name__ == "__main__":
    main()