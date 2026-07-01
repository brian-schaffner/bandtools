#!/usr/local/bin/python3
"""
Test the main UI quick pick mapping to verify it works end-to-end.
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
    
    cursor.execute(
        "DELETE FROM title_mappings WHERE pdf_title LIKE ? OR catalog_title LIKE ?",
        ("%Party Started%", "%Get The Party Started%")
    )
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"Removed {deleted_count} existing mappings for 'Get The Party Started'")

def test_main_ui_quick_pick_workflow():
    """Test the main UI workflow with quick pick mapping."""
    print("\n=== Testing Main UI Quick Pick Workflow ===")
    
    # Step 1: Upload PDF using main UI streaming API
    print("\n1. Uploading PDF via main UI...")
    
    with open("pdfs/leitchfield%20derby%202025.pdf", "rb") as f:
        files = {"pdf": ("leitchfield derby 202025.pdf", f, "application/pdf")}
        data = {"secret": "change-me", "session_id": "brian@schaffner.net"}
        
        response = requests.post(
            "http://localhost:8002/process_setlist_streaming",
            files=files,
            data=data
        )
    
    if response.status_code != 200:
        raise Exception(f"PDF upload failed: {response.status_code} {response.text}")
    
    # Parse the streaming response to get the final result
    lines = response.text.strip().split('\n')
    final_result = None
    
    for line in lines:
        if line.startswith('data: '):
            try:
                data = json.loads(line[6:])
                if data.get('stage') == 'completed':
                    final_result = data
                    break
            except:
                continue
    
    if not final_result:
        raise Exception("Could not parse final result from streaming response")
    
    print(f"Main UI processing completed: {final_result}")
    
    # Step 2: Check if we have a download URL
    download_url = final_result.get('download_url')
    if not download_url:
        print("❌ No download URL in final result")
        return False
    
    print(f"Download URL: {download_url}")
    
    # Step 3: Download and verify the SBP file
    print("\n2. Downloading and verifying SBP file...")
    
    response = requests.get(download_url)
    if response.status_code != 200:
        print(f"❌ Download failed: {response.status_code}")
        return False
    
    # Save the SBP file temporarily
    sbp_path = "temp_test_output.sbp"
    with open(sbp_path, "wb") as f:
        f.write(response.content)
    
    print(f"SBP file downloaded: {len(response.content)} bytes")
    
    # Step 4: Parse and verify the SBP file
    try:
        from sbp_library import SBPLibrary
        
        sbp_lib = SBPLibrary()
        sbp_file = sbp_lib.load_sbp_file(sbp_path)
        
        print(f"SBP file loaded successfully")
        print(f"Number of songs: {len(sbp_file.songs)}")
        print(f"Number of sets: {len(sbp_file.sets)}")
        
        # Check if "Get The Party Started" is in the songs
        song_titles = [song.name for song in sbp_file.songs]
        print(f"Song titles in SBP file: {song_titles[:10]}...")  # Show first 10
        
        if "Get The Party Started" in song_titles:
            print("✅ SUCCESS: 'Get The Party Started' found in SBP file!")
            
            # Find the song and check its details
            party_song = next((song for song in sbp_file.songs if song.name == "Get The Party Started"), None)
            if party_song:
                print(f"✅ Song details: ID={party_song.id}, Name='{party_song.name}'")
            
            return True
        else:
            print("❌ FAILURE: 'Get The Party Started' NOT found in SBP file")
            print(f"Available songs: {song_titles}")
            return False
            
    except Exception as e:
        print(f"❌ Error parsing SBP file: {e}")
        return False
    finally:
        # Clean up
        if Path(sbp_path).exists():
            Path(sbp_path).unlink()

def main():
    """Run the test."""
    print("=== Testing Main UI Quick Pick Mapping ===")
    
    try:
        # Step 1: Remove existing mapping
        print("\n1. Removing existing mapping...")
        remove_party_started_mapping()
        
        # Step 2: Test the main UI workflow
        success = test_main_ui_quick_pick_workflow()
        
        if success:
            print("\n🎉 MAIN UI QUICK PICK TEST PASSED!")
        else:
            print("\n❌ MAIN UI QUICK PICK TEST FAILED!")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
