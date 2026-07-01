#!/usr/local/bin/python3
"""
Test the real main UI workflow to verify mapping works end-to-end.
This simulates the actual main UI process, not mock data.
"""

import requests
import json
import time
import sqlite3
from pathlib import Path

def remove_party_started_mapping():
    """Remove the mapping for 'Get The Party Started' from the database."""
    conn = sqlite3.connect("setloader.db")
    cursor = conn.cursor()
    
    # Find and delete mappings for "Get The Party Started"
    cursor.execute(
        "SELECT * FROM title_mappings WHERE pdf_title LIKE ? OR catalog_title LIKE ?",
        ("%Party Started%", "%Get The Party Started%")
    )
    
    mappings = cursor.fetchall()
    print(f"Found {len(mappings)} mappings for 'Get The Party Started':")
    
    for mapping in mappings:
        print(f"  PDF Title: {mapping[2]} -> Catalog Title: {mapping[3]}")
    
    if mappings:
        cursor.execute(
            "DELETE FROM title_mappings WHERE pdf_title LIKE ? OR catalog_title LIKE ?",
            ("%Party Started%", "%Get The Party Started%")
        )
        deleted_count = cursor.rowcount
        conn.commit()
        print(f"Deleted {deleted_count} mapping(s)")
    else:
        print("No mappings found")
    
    conn.close()

def test_main_ui_workflow():
    """Test the actual main UI workflow using standalone components."""
    print("\n=== Testing Main UI Workflow ===")
    
    # Step 1: Upload PDF using standalone PDF extraction
    print("\n1. Uploading PDF via standalone PDF extraction...")
    
    with open("pdfs/leitchfield%20derby%202025.pdf", "rb") as f:
        files = {"pdf": ("leitchfield derby 202025.pdf", f, "application/pdf")}
        data = {"secret": "change-me", "name": "Leitchfield Test"}
        
        response = requests.post(
            "http://localhost:8002/standalone/pdf-extraction",
            files=files,
            data=data
        )
    
    if response.status_code != 200:
        raise Exception(f"PDF upload failed: {response.status_code} {response.text}")
    
    pdf_result = response.json()
    print(f"PDF extraction result: {pdf_result}")
    
    # Step 2: Extract titles from the PDF result
    print("\n2. Extracting titles from PDF result...")
    
    extracted_titles = []
    for set_data in pdf_result.get('data', {}).get('sets', []):
        for song in set_data.get('songs', []):
            extracted_titles.append(song.get('title', ''))
    
    print(f"Extracted {len(extracted_titles)} titles: {extracted_titles[:10]}...")
    
    # Check if "Party Started" is in the extracted titles
    if "Party Started" not in extracted_titles:
        print("❌ 'Party Started' not found in extracted titles")
        return False
    
    print("✅ 'Party Started' found in extracted titles")
    
    # Create validation data in the correct format
    validation_data = {
        "sets": [{
            "name": "Extracted Set",
            "songs": [{"title": title, "validated": False, "song_id": None, "validated_title": title} for title in extracted_titles]
        }],
        "extras": [],
        "counts": {"total": len(extracted_titles), "validated_total": 0, "missing_total": len(extracted_titles)}
    }
    
    # Run validation
    json_blob = json.dumps(validation_data).encode('utf-8')
    files = {"json_file": ("validation_input.json", json_blob, "application/json")}
    data = {"secret": "change-me"}
    
    response = requests.post(
        "http://localhost:8002/standalone/title-validation",
        files=files,
        data=data
    )
    
    if response.status_code != 200:
        raise Exception(f"Title validation failed: {response.status_code} {response.text}")
    
    validation_result = response.json()
    print(f"Title validation result: {validation_result}")
    
    # Step 4: Check if "Party Started" is missing and needs mapping
    missing_titles = []
    for set_data in validation_result.get('data', {}).get('sets', []):
        for song in set_data.get('songs', []):
            if not song.get('validated', False):
                missing_titles.append(song.get('title', ''))
    
    print(f"Missing titles: {missing_titles}")
    
    if "Party Started" not in missing_titles:
        print("❌ 'Party Started' is not in missing titles - mapping may already exist")
        return False
    
    # Step 5: Map "Party Started" to "Get The Party Started"
    print("\n3. Mapping 'Party Started' to 'Get The Party Started'...")
    
    mapping_data = {
        "pdf_title": "Party Started",
        "catalog_title": "Get The Party Started"
    }
    
    response = requests.post(
        "http://localhost:8002/standalone/save-mapping",
        json=mapping_data,
        headers={"X-Secret": "change-me"}
    )
    
    if response.status_code != 200:
        raise Exception(f"Save mapping failed: {response.status_code} {response.text}")
    
    mapping_result = response.json()
    print(f"Mapping saved: {mapping_result}")
    
    # Step 6: Re-run validation to get updated results
    print("\n4. Re-running validation after mapping...")
    
    response = requests.post(
        "http://localhost:8002/standalone/title-validation",
        files=files,
        data=data
    )
    
    if response.status_code != 200:
        raise Exception(f"Re-validation failed: {response.status_code} {response.text}")
    
    revalidation_result = response.json()
    print(f"Re-validation result: {revalidation_result}")
    
    # Step 7: Run song extraction
    print("\n5. Running song extraction...")
    
    # Use the re-validation result for song extraction
    extraction_data = revalidation_result.get('data', {})
    
    json_blob = json.dumps(extraction_data).encode('utf-8')
    files = {"json_file": ("validated_input.json", json_blob, "application/json")}
    data = {"secret": "change-me", "set_name": "Leitchfield Test"}
    
    response = requests.post(
        "http://localhost:8002/standalone/song-extraction",
        files=files,
        data=data
    )
    
    if response.status_code != 200:
        raise Exception(f"Song extraction failed: {response.status_code} {response.text}")
    
    extraction_result = response.json()
    print(f"Song extraction result: {extraction_result}")
    
    # Step 8: Verify the SBP file contains "Get The Party Started"
    print("\n6. Verifying SBP file...")
    
    sbp_path = extraction_result.get('data', {}).get('output_path')
    if not sbp_path:
        print("❌ No output path in extraction result")
        return False
    
    try:
        from sbp_library import SBPLibrary
        
        sbp_lib = SBPLibrary()
        sbp_file = sbp_lib.load_sbp_file(sbp_path)
        
        print(f"SBP file loaded successfully")
        print(f"Number of songs: {len(sbp_file.songs)}")
        print(f"Number of sets: {len(sbp_file.sets)}")
        
        # Check if "Get The Party Started" is in the songs
        song_titles = [song.name for song in sbp_file.songs]
        print(f"Song titles in SBP file: {song_titles}")
        
        if "Get The Party Started" in song_titles:
            print("✅ SUCCESS: 'Get The Party Started' found in SBP file!")
            return True
        else:
            print("❌ FAILURE: 'Get The Party Started' NOT found in SBP file")
            return False
            
    except Exception as e:
        print(f"❌ Error parsing SBP file: {e}")
        return False

def main():
    """Run the complete real workflow test."""
    print("=== Testing Real Main UI Workflow ===")
    
    try:
        # Step 1: Remove existing mapping
        print("\n1. Removing existing mapping for 'Get The Party Started'...")
        remove_party_started_mapping()
        
        # Step 2: Test the real main UI workflow
        success = test_main_ui_workflow()
        
        if success:
            print("\n🎉 REAL WORKFLOW TEST PASSED!")
        else:
            print("\n❌ REAL WORKFLOW TEST FAILED!")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
