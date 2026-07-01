#!/usr/bin/env python3
"""
Comprehensive test to compare Main UI vs Standalone functionality
Tests the same workflow through both interfaces and compares results
"""

import requests
import json
import time
import os
from pathlib import Path

# Test configuration
BASE_URL = "http://localhost:8002"
SECRET = "change-me"
USER_ID = "35e76f8b-65f7-48c1-9920-932122e98219"

def log_test(message):
    print(f"[TEST] {message}")

def test_authentication():
    """Test authentication for main UI"""
    log_test("Testing authentication...")
    
    # Use a known active session token from the database
    # The last active session token is: b0c25cd8-6f7e-4c32-af82-1218113f4f46
    return "b0c25cd8-6f7e-4c32-af82-1218113f4f46"

def test_standalone_workflow():
    """Test the standalone workflow end-to-end"""
    log_test("=== TESTING STANDALONE WORKFLOW ===")
    
    results = {}
    
    # Step 1: PDF Extraction
    log_test("Step 1: PDF Extraction")
    pdf_file = "pdfs/docs%20may%202025.pdf"
    if not os.path.exists(pdf_file):
        log_test(f"❌ PDF file {pdf_file} not found")
        return None
    
    with open(pdf_file, 'rb') as f:
        files = {'pdf': f}
        data = {'secret': SECRET}
        response = requests.post(f"{BASE_URL}/standalone/pdf-extraction", 
                               files=files,
                               data=data)
    
    if response.status_code == 200:
        pdf_result = response.json()
        results['pdf_extraction'] = pdf_result
        log_test(f"✅ PDF extraction successful: {pdf_result.get('message', '')}")
    else:
        log_test(f"❌ PDF extraction failed: {response.status_code}")
        return None
    
    # Step 2: Title Validation
    log_test("Step 2: Title Validation")
    validation_data = pdf_result['data']
    
    # Create a temporary JSON file for upload
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(validation_data, f)
        temp_file = f.name
    
    try:
        with open(temp_file, 'rb') as f:
            files = {'json_file': f}
            data = {'secret': SECRET}
            response = requests.post(f"{BASE_URL}/standalone/title-validation",
                                   files=files,
                                   data=data)
    finally:
        os.unlink(temp_file)
    
    if response.status_code == 200:
        validation_result = response.json()
        results['title_validation'] = validation_result
        log_test(f"✅ Title validation successful: {validation_result.get('message', '')}")
        
        # Check for unfound titles
        unfound_count = 0
        if 'data' in validation_result and 'sets' in validation_result['data']:
            for set_data in validation_result['data']['sets']:
                if 'songs' in set_data:
                    for song in set_data['songs']:
                        if not song.get('validated', False):
                            unfound_count += 1
        
        log_test(f"📊 Found {unfound_count} unfound titles")
        
        # Test quick pick mapping if there are unfound titles
        if unfound_count > 0:
            log_test("Step 2.5: Testing quick pick mapping")
            
            # Save a mapping
            mapping_response = requests.post(f"{BASE_URL}/standalone/save-mapping",
                                          json={
                                              "pdf_title": "Refuge",
                                              "catalog_title": "Refugee"
                                          },
                                          headers={'X-Secret': SECRET})
            
            if mapping_response.status_code == 200:
                log_test("✅ Quick pick mapping saved")
                
                # Re-validate to see if mapping is applied
                revalidation_response = requests.post(f"{BASE_URL}/standalone/title-validation",
                                                    json=validation_data,
                                                    headers={'X-Secret': SECRET})
                
                if revalidation_response.status_code == 200:
                    revalidation_result = revalidation_response.json()
                    results['title_validation_after_mapping'] = revalidation_result
                    log_test("✅ Re-validation after mapping successful")
                else:
                    log_test(f"❌ Re-validation failed: {revalidation_response.status_code}")
            else:
                log_test(f"❌ Quick pick mapping failed: {mapping_response.status_code}")
    else:
        log_test(f"❌ Title validation failed: {response.status_code}")
        return None
    
    # Step 3: Song Extraction
    log_test("Step 3: Song Extraction")
    final_validation_data = results.get('title_validation_after_mapping', results['title_validation'])
    
    # Create a temporary JSON file for upload
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(final_validation_data['data'], f)
        temp_file = f.name
    
    try:
        with open(temp_file, 'rb') as f:
            files = {'json_file': f}
            data = {'secret': SECRET}
            response = requests.post(f"{BASE_URL}/standalone/song-extraction",
                                   files=files,
                                   data=data)
    finally:
        os.unlink(temp_file)
    
    if response.status_code == 200:
        extraction_result = response.json()
        results['song_extraction'] = extraction_result
        log_test(f"✅ Song extraction successful: {extraction_result.get('message', '')}")
        
        # Check download URL
        if 'data' in extraction_result and 'download_url' in extraction_result['data']:
            download_url = extraction_result['data']['download_url']
            log_test(f"📥 Download URL: {download_url}")
    else:
        log_test(f"❌ Song extraction failed: {response.status_code}")
        return None
    
    return results

def test_main_ui_workflow():
    """Test the main UI workflow end-to-end"""
    log_test("=== TESTING MAIN UI WORKFLOW ===")
    
    results = {}
    session_token = test_authentication()
    
    # Step 1: Upload PDF and start processing
    log_test("Step 1: Upload PDF to main UI")
    pdf_file = "pdfs/docs%20may%202025.pdf"
    if not os.path.exists(pdf_file):
        log_test(f"❌ PDF file {pdf_file} not found")
        return None
    
    with open(pdf_file, 'rb') as f:
        files = {'file': f}
        data = {'secret': SECRET}
        response = requests.post(f"{BASE_URL}/process_setlist_streaming",
                               files=files,
                               data=data,
                               headers={'X-Session-ID': session_token})
    
    if response.status_code == 200:
        # Parse streaming response
        streaming_data = response.text
        log_test("✅ PDF upload and processing started")
        
        # Extract results from streaming data
        lines = streaming_data.split('\n')
        for line in lines:
            if line.startswith('data: '):
                try:
                    data = json.loads(line[6:])
                    if data.get('stage') == 'pdf_extraction':
                        results['pdf_extraction'] = data
                        log_test(f"✅ PDF extraction completed: {data.get('message', '')}")
                    elif data.get('stage') == 'title_validation':
                        results['title_validation'] = data
                        log_test(f"✅ Title validation completed: {data.get('message', '')}")
                    elif data.get('stage') == 'song_extraction':
                        results['song_extraction'] = data
                        log_test(f"✅ Song extraction completed: {data.get('message', '')}")
                except json.JSONDecodeError:
                    continue
    else:
        log_test(f"❌ Main UI processing failed: {response.status_code}")
        return None
    
    # Step 2: Test quick pick mapping in main UI
    log_test("Step 2: Testing quick pick mapping in main UI")
    
    # Get current mappings
    mappings_response = requests.get(f"{BASE_URL}/user/title-mappings",
                                   headers={
                                       'X-Secret': SECRET,
                                       'X-Session-ID': session_token
                                   })
    
    if mappings_response.status_code == 200:
        current_mappings = mappings_response.json()
        log_test(f"📊 Current mappings count: {len(current_mappings)}")
        
        # Add a new mapping
        new_mappings = dict(current_mappings)
        new_mappings["Refuge"] = "Refugee"
        
        save_response = requests.post(f"{BASE_URL}/user/title-mappings",
                                   json=new_mappings,
                                   headers={
                                       'X-Secret': SECRET,
                                       'X-Session-ID': session_token
                                   })
        
        if save_response.status_code == 200:
            log_test("✅ Mapping saved in main UI")
            
            # Test reprocessing
            reprocess_response = requests.post(f"{BASE_URL}/user/reprocess-setlist",
                                             headers={
                                                 'X-Secret': SECRET,
                                                 'X-Session-ID': session_token
                                             })
            
            if reprocess_response.status_code == 200:
                log_test("✅ Reprocessing triggered in main UI")
                results['reprocessing'] = reprocess_response.json()
            else:
                log_test(f"❌ Reprocessing failed: {reprocess_response.status_code}")
        else:
            log_test(f"❌ Mapping save failed: {save_response.status_code}")
    else:
        log_test(f"❌ Failed to get mappings: {mappings_response.status_code}")
    
    return results

def compare_results(standalone_results, main_ui_results):
    """Compare results between standalone and main UI"""
    log_test("=== COMPARING RESULTS ===")
    
    comparison = {
        'standalone': standalone_results,
        'main_ui': main_ui_results,
        'differences': []
    }
    
    # Compare PDF extraction
    if 'pdf_extraction' in standalone_results and 'pdf_extraction' in main_ui_results:
        standalone_pdf = standalone_results['pdf_extraction']
        main_ui_pdf = main_ui_results['pdf_extraction']
        
        if standalone_pdf.get('success') != main_ui_pdf.get('success'):
            comparison['differences'].append("PDF extraction success status differs")
        
        if standalone_pdf.get('data', {}).get('total_count') != main_ui_pdf.get('total'):
            comparison['differences'].append("PDF extraction song counts differ")
    
    # Compare title validation
    if 'title_validation' in standalone_results and 'title_validation' in main_ui_results:
        standalone_validation = standalone_results['title_validation']
        main_ui_validation = main_ui_results['title_validation']
        
        # Compare validation counts
        standalone_validated = standalone_validation.get('data', {}).get('counts', {}).get('validated_total', 0)
        main_ui_validated = main_ui_validation.get('validated', 0)  # Fixed: use 'validated' not 'validated_count'
        
        if standalone_validated != main_ui_validated:
            comparison['differences'].append(f"Validation counts differ: standalone={standalone_validated}, main_ui={main_ui_validated}")
    
    # Compare song extraction
    if 'song_extraction' in standalone_results and 'song_extraction' in main_ui_results:
        standalone_extraction = standalone_results['song_extraction']
        main_ui_extraction = main_ui_results['song_extraction']
        
        if standalone_extraction.get('success') != main_ui_extraction.get('success'):
            comparison['differences'].append("Song extraction success status differs")
    
    return comparison

def main():
    """Run the comprehensive comparison test"""
    log_test("Starting Main UI vs Standalone Comparison Test")
    
    # Test standalone workflow
    standalone_results = test_standalone_workflow()
    if not standalone_results:
        log_test("❌ Standalone workflow failed")
        return
    
    # Test main UI workflow
    main_ui_results = test_main_ui_workflow()
    if not main_ui_results:
        log_test("❌ Main UI workflow failed")
        return
    
    # Compare results
    comparison = compare_results(standalone_results, main_ui_results)
    
    # Print summary
    log_test("=== TEST SUMMARY ===")
    log_test(f"Standalone workflow: {'✅ PASSED' if standalone_results else '❌ FAILED'}")
    log_test(f"Main UI workflow: {'✅ PASSED' if main_ui_results else '❌ FAILED'}")
    
    if comparison['differences']:
        log_test("❌ DIFFERENCES FOUND:")
        for diff in comparison['differences']:
            log_test(f"  - {diff}")
    else:
        log_test("✅ No significant differences found")
    
    # Save detailed results
    with open('test_comparison_results.json', 'w') as f:
        json.dump(comparison, f, indent=2)
    
    log_test("📄 Detailed results saved to test_comparison_results.json")

if __name__ == "__main__":
    main()
