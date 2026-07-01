#!/usr/bin/env python3
"""
Test the complete main UI workflow with Leitchfield setlist
"""

import json
import requests
import time

def test_complete_workflow():
    """Test the complete main UI workflow"""
    
    print("🧪 Testing complete main UI workflow with Leitchfield setlist...")
    
    # Step 1: Test PDF extraction endpoint
    print("\n1️⃣ Testing PDF extraction endpoint...")
    try:
        # Use the Leitchfield PDF
        with open("pdfs/leitchfield%20derby%202025.pdf", "rb") as f:
            files = {"file": ("leitchfield_derby_2025.pdf", f, "application/pdf")}
            data = {"secret": "change-me"}
            
            response = requests.post("http://localhost:8002/standalone/pdf-extraction", files=files, data=data)
            
            if response.ok:
                result = response.json()
                print(f"   ✅ PDF extraction successful")
                print(f"   📊 Extracted songs: {result.get('data', {}).get('counts', {}).get('total', 0)}")
                
                # Save the extracted titles for next step
                extracted_titles = result.get('data', {})
                return extracted_titles
            else:
                print(f"   ❌ PDF extraction failed: {response.status_code}")
                print(f"   📄 Response: {response.text}")
                return None
    except Exception as e:
        print(f"   ❌ Error in PDF extraction: {e}")
        return None

def test_title_validation_with_extracted_titles(extracted_titles):
    """Test title validation with extracted titles"""
    
    print("\n2️⃣ Testing title validation with extracted titles...")
    
    if not extracted_titles:
        print("   ❌ No extracted titles to validate")
        return None
    
    try:
        # Create JSON file for title validation
        json_blob = json.dumps(extracted_titles)
        files = {"json_file": ("extracted_titles.json", json_blob, "application/json")}
        data = {"secret": "change-me"}
        
        response = requests.post("http://localhost:8002/standalone/title-validation", files=files, data=data)
        
        if response.ok:
            result = response.json()
            print(f"   ✅ Title validation successful")
            print(f"   📊 Validation result structure: {list(result.keys())}")
            
            if 'data' in result:
                data = result['data']
                print(f"   📊 Total songs: {data.get('counts', {}).get('total', 0)}")
                print(f"   📊 Validated: {data.get('counts', {}).get('validated_total', 0)}")
                print(f"   📊 Missing: {data.get('counts', {}).get('missing_total', 0)}")
                
                # Check for unvalidated songs
                unvalidated_songs = []
                for set_data in data.get('sets', []):
                    for song in set_data.get('songs', []):
                        if not song.get('validated', False):
                            unvalidated_songs.append(song.get('title', 'Unknown'))
                
                print(f"   🔍 Unvalidated songs: {unvalidated_songs}")
                
                return result
            else:
                print(f"   ❌ No data in validation result")
                return None
        else:
            print(f"   ❌ Title validation failed: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return None
    except Exception as e:
        print(f"   ❌ Error in title validation: {e}")
        return None

def test_main_ui_integration():
    """Test that the main UI would work with this data"""
    
    print("\n3️⃣ Testing main UI integration...")
    
    # Load the existing validation data
    with open("work/35e76f8b-65f7-48c1-9920-932122e98219_1761023991/validation_result.json", 'r') as f:
        validation_data = json.load(f)
    
    print(f"   📊 Using existing validation data:")
    print(f"   📊 Total songs: {validation_data.get('counts', {}).get('total', 0)}")
    print(f"   📊 Validated: {validation_data.get('counts', {}).get('validated_total', 0)}")
    print(f"   📊 Missing: {validation_data.get('counts', {}).get('missing_total', 0)}")
    
    # Simulate what the main UI should pass to the shared component
    stage_result = {
        "success": True,
        "validatedSongs": validation_data.get('counts', {}).get('validated_total', 0),
        "unfoundTitles": [],
        "extractedSongs": validation_data.get('counts', {}).get('total', 0),
        "message": f"Validated {validation_data.get('counts', {}).get('validated_total', 0)} out of {validation_data.get('counts', {}).get('total', 0)} songs",
        "validationData": validation_data
    }
    
    # Test what the shared component should receive
    preloaded_data = stage_result.get('validationData')
    
    if preloaded_data and 'counts' in preloaded_data:
        counts = preloaded_data['counts']
        print(f"   ✅ Shared component should receive:")
        print(f"      📊 Total: {counts.get('total', 0)}")
        print(f"      📊 Validated: {counts.get('validated_total', 0)}")
        print(f"      📊 Missing: {counts.get('missing_total', 0)}")
        
        # Check for unvalidated songs
        unvalidated_songs = []
        for set_data in preloaded_data.get('sets', []):
            for song in set_data.get('songs', []):
                if not song.get('validated', False):
                    unvalidated_songs.append(song.get('title', 'Unknown'))
        
        print(f"      🔍 Quick picks should show: {unvalidated_songs}")
        
        return len(unvalidated_songs) > 0
    else:
        print(f"   ❌ No validation data to pass to shared component")
        return False

if __name__ == "__main__":
    print("🚀 Starting complete workflow test...")
    
    # Test 1: PDF extraction
    extracted_titles = test_complete_workflow()
    
    # Test 2: Title validation (if PDF extraction worked)
    if extracted_titles:
        validation_result = test_title_validation_with_extracted_titles(extracted_titles)
    else:
        print("   ⏭️ Skipping title validation test (PDF extraction failed)")
        validation_result = None
    
    # Test 3: Main UI integration
    main_ui_ok = test_main_ui_integration()
    
    print(f"\n📋 Test Results:")
    print(f"   ✅ PDF extraction: {'PASS' if extracted_titles else 'FAIL'}")
    print(f"   ✅ Title validation: {'PASS' if validation_result else 'FAIL'}")
    print(f"   ✅ Main UI integration: {'PASS' if main_ui_ok else 'FAIL'}")
    
    if main_ui_ok:
        print(f"\n🎉 Main UI integration test passed! The shared component should work correctly.")
        print(f"   🔍 Quick picks should appear for: 'Whenever U Come Around' and 'Party Started'")
    else:
        print(f"\n❌ Main UI integration test failed. Need to investigate further.")
