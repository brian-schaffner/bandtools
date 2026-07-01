#!/usr/bin/env python3
"""
Test validation counts to verify they make sense.
"""

import requests
import json

def test_validation_counts():
    """Test that validation counts are accurate and consistent."""
    
    print("🔍 Testing Validation Counts")
    print("=" * 40)
    
    # Test with unfound titles
    with open("test_unfound_titles.json", "rb") as f:
        files = {"json_file": f}
        data = {"secret": "change-me"}
        
        response = requests.post("http://localhost:8002/standalone/title-validation", 
                               files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        counts = result["data"]["counts"]
        sets = result["data"]["sets"]
        
        print("📊 Validation Results:")
        print(f"   Total songs: {counts['total']}")
        print(f"   Validated: {counts['validated_total']}")
        print(f"   Missing: {counts['missing_total']}")
        
        print("\n📋 Per Set Breakdown:")
        for set_name, set_counts in counts["per_set"].items():
            print(f"   {set_name}: {set_counts['validated']}/{set_counts['total']} validated ({set_counts['missing']} missing)")
        
        print("\n🎵 Individual Song Status:")
        for set_data in sets:
            print(f"   Set: {set_data['name']}")
            for song in set_data['songs']:
                status = "✅" if song['validated'] else "❌"
                print(f"     {status} {song['title']} - {song['status']}")
        
        # Verify counts add up correctly
        total_validated = sum(set_counts['validated'] for set_counts in counts["per_set"].values())
        total_validated += counts["extras"]["validated"]
        
        total_missing = sum(set_counts['missing'] for set_counts in counts["per_set"].values())
        total_missing += counts["extras"]["missing"]
        
        print(f"\n🧮 Count Verification:")
        print(f"   Calculated validated: {total_validated} (should match {counts['validated_total']})")
        print(f"   Calculated missing: {total_missing} (should match {counts['missing_total']})")
        
        if total_validated == counts['validated_total'] and total_missing == counts['missing_total']:
            print("   ✅ Counts are consistent!")
        else:
            print("   ❌ Count mismatch detected!")
        
        # Check if mapping interface should appear
        if counts['missing_total'] > 0:
            print(f"\n🎯 Mapping Interface Should Appear:")
            print(f"   {counts['missing_total']} songs need mapping")
            print("   Quick picks should be available for unfound titles")
        else:
            print(f"\n🎉 All Songs Validated:")
            print("   No mapping interface needed")
            print("   Download button should be ready")
            
    else:
        print(f"❌ Validation failed: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_validation_counts()
