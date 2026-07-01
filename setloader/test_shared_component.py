#!/usr/bin/env python3
"""
Test the shared component data flow
"""

import json
import requests

def test_shared_component_data_flow():
    """Test that the shared component receives the correct validation data"""
    
    print("🧪 Testing shared component data flow...")
    
    # Test the standalone title validation endpoint
    print("1. Testing standalone title validation endpoint...")
    
    # Create test validation data
    test_data = {
        "sets": [
            {
                "name": "Set 1",
                "songs": [
                    {"title": "Refuge", "validated": False},
                    {"title": "3 steps", "validated": True}
                ]
            }
        ],
        "extras": [],
        "counts": {
            "total": 2,
            "validated_total": 1,
            "missing_total": 1
        }
    }
    
    # Create JSON file
    json_blob = json.dumps(test_data)
    form_data = {
        'json_file': ('test.json', json_blob, 'application/json'),
        'secret': 'change-me'
    }
    
    try:
        response = requests.post('http://localhost:8002/standalone/title-validation', files=form_data)
        if response.ok:
            result = response.json()
            print(f"   ✅ Standalone validation successful")
            print(f"   📊 Validation data structure: {list(result.get('data', {}).keys())}")
            print(f"   📊 Counts: {result.get('data', {}).get('counts', {})}")
            
            # This is the data that should be passed to the shared component
            validation_data = result.get('data', {})
            print(f"   📊 Validation data for shared component: {validation_data}")
            
            return validation_data
        else:
            print(f"   ❌ Standalone validation failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ Error testing standalone validation: {e}")
        return None

if __name__ == "__main__":
    test_shared_component_data_flow()
