#!/usr/bin/env python3
"""
Test the complete quick pick mapping flow for standalone title validation.
"""

import requests
import json
import time

def test_quick_pick_flow():
    """Test the complete quick pick mapping flow."""
    
    base_url = "http://localhost:8002"
    headers = {"X-Secret": "change-me"}
    
    print("🧪 Testing Quick Pick Mapping Flow")
    print("=" * 50)
    
    # Step 1: Test title validation with unfound titles
    print("\n1️⃣ Testing title validation with unfound titles...")
    
    with open("test_unfound_titles.json", "rb") as f:
        files = {"json_file": f}
        data = {"secret": "change-me"}
        
        response = requests.post(f"{base_url}/standalone/title-validation", 
                               files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        counts = result["data"]["counts"]
        print(f"✅ Title validation successful")
        print(f"   Total songs: {counts['total']}")
        print(f"   Validated: {counts['validated_total']}")
        print(f"   Missing: {counts['missing_total']}")
        
        # Check if we have unfound titles
        if counts['missing_total'] > 0:
            print(f"   🎯 Found {counts['missing_total']} songs that need mapping")
            
            # Step 2: Test saving a mapping
            print("\n2️⃣ Testing mapping save...")
            
            mapping_data = {
                "pdf_title": "Unknown Song 1",
                "catalog_title": "Hurt So Good"  # Map to a known song
            }
            
            response = requests.post(f"{base_url}/standalone/save-mapping",
                                  headers=headers,
                                  json=mapping_data)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Mapping saved successfully: {result['message']}")
                
                # Step 3: Test catalog loading
                print("\n3️⃣ Testing catalog loading...")
                
                response = requests.get(f"{base_url}/standalone/user-catalog", headers=headers)
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Catalog loaded: {result['total']} songs available")
                    
                    # Show some sample songs for quick picks
                    if result['songs']:
                        print("   Sample songs for quick picks:")
                        for song in result['songs'][:5]:
                            print(f"   - {song['name']}")
                    
                    print("\n🎉 All tests passed! Quick pick flow is working correctly.")
                    print("\n📋 Summary:")
                    print("   ✅ Title validation with unfound titles")
                    print("   ✅ Mapping save functionality")
                    print("   ✅ Catalog loading for quick picks")
                    print("   ✅ Frontend should now show quick pick suggestions")
                    
                else:
                    print(f"❌ Catalog loading failed: {response.status_code}")
                    print(response.text)
            else:
                print(f"❌ Mapping save failed: {response.status_code}")
                print(response.text)
        else:
            print("   ⚠️  No missing songs found - all songs are validated")
    else:
        print(f"❌ Title validation failed: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_quick_pick_flow()
