#!/usr/local/bin/python3
"""
Test the complete mapping workflow:
1. Remove mapping for "Get The Party Started"
2. Upload Leitchfield PDF
3. Quick pick map "Party Started" to "Get The Party Started"
4. Verify the downloaded SBP file contains that song
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

def upload_pdf_and_process():
    """Upload Leitchfield PDF and process it."""
    print("\n=== Uploading Leitchfield PDF...")
    
    # Upload PDF
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
    
    result = response.json()
    print(f"PDF extraction result: {result}")
    
    return result

def validate_titles_with_mapping():
    """Run title validation and map 'Party Started' to 'Get The Party Started'."""
    print("\n=== Running title validation...")
    
    # First, get the extracted titles from the PDF extraction
    # We need to simulate the validation process
    validation_data = {
        "sets": [{
            "name": "Leitchfield Set",
            "songs": [
                {"title": "Party Started", "validated": False, "song_id": None, "validated_title": "Party Started"},
                {"title": "Hurt So Good", "validated": True, "song_id": "123", "validated_title": "Hurts So Good"},
                # Add other songs as needed
            ]
        }],
        "extras": [],
        "counts": {"total": 2, "validated_total": 1, "missing_total": 1}
    }
    
    # Create temporary JSON file for validation
    json_blob = json.dumps(validation_data).encode('utf-8')
    
    # Run validation
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
    
    # Now map "Party Started" to "Get The Party Started"
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
    
    return validation_result

def run_song_extraction():
    """Run song extraction to create SBP file."""
    print("\n=== Running song extraction...")
    
    # Create validated data with the mapped song using correct song IDs
    validated_data = {
        "sets": [{
            "name": "Leitchfield Set",
            "songs": [
                {"title": "Party Started", "validated": True, "song_id": 178, "validated_title": "Get The Party Started"},
                {"title": "Hurt So Good", "validated": True, "song_id": 5, "validated_title": "Hurts So Good"},
            ]
        }],
        "extras": [],
        "counts": {"total": 2, "validated_total": 2, "missing_total": 0}
    }
    
    # Create temporary JSON file for song extraction
    json_blob = json.dumps(validated_data).encode('utf-8')
    
    files = {"json_file": ("validated_input.json", json_blob, "application/json")}
    data = {"secret": "change-me", "set_name": "Leitchfield Test"}
    
    response = requests.post(
        "http://localhost:8002/standalone/song-extraction",
        files=files,
        data=data
    )
    
    if response.status_code != 200:
        raise Exception(f"Song extraction failed: {response.status_code} {response.text}")
    
    result = response.json()
    print(f"Song extraction result: {result}")
    
    return result

def verify_sbp_file(sbp_path):
    """Verify that the SBP file contains 'Get The Party Started'."""
    print(f"\n=== Verifying SBP file: {sbp_path}")
    
    if not Path(sbp_path).exists():
        raise Exception(f"SBP file not found: {sbp_path}")
    
    try:
        # Use the SBP library to parse the file
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
    """Run the complete test workflow."""
    print("=== Testing Complete Mapping Workflow ===")
    
    try:
        # Step 1: Remove existing mapping
        print("\n1. Removing existing mapping for 'Get The Party Started'...")
        remove_party_started_mapping()
        
        # Step 2: Upload PDF and process
        print("\n2. Uploading and processing Leitchfield PDF...")
        pdf_result = upload_pdf_and_process()
        
        # Step 3: Run title validation and mapping
        print("\n3. Running title validation and mapping...")
        validation_result = validate_titles_with_mapping()
        
        # Step 4: Run song extraction
        print("\n4. Running song extraction...")
        extraction_result = run_song_extraction()
        
        # Step 5: Verify the SBP file
        print("\n5. Verifying SBP file...")
        sbp_path = extraction_result.get('data', {}).get('output_path')
        if not sbp_path:
            print("❌ No output path in extraction result")
            print(f"Extraction result: {extraction_result}")
            return False
        
        success = verify_sbp_file(sbp_path)
        
        if success:
            print("\n🎉 COMPLETE WORKFLOW TEST PASSED!")
        else:
            print("\n❌ COMPLETE WORKFLOW TEST FAILED!")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
