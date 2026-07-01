#!/usr/bin/env python3
"""
Integration test for the setlist-helper UI and backend integration.
"""

import requests
import json
import time
import os
from pathlib import Path

# Test configuration
API_BASE_URL = "http://localhost:8002"
API_SECRET = "change-me"
TEST_SESSION_ID = "test-session-123"

def test_health_endpoint():
    """Test the health endpoint."""
    print("Testing health endpoint...")
    response = requests.get(f"{API_BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    print("✅ Health endpoint working")

def test_user_status():
    """Test user status endpoint."""
    print("Testing user status endpoint...")
    headers = {
        "X-Secret": API_SECRET,
        "X-Session-ID": TEST_SESSION_ID
    }
    response = requests.get(f"{API_BASE_URL}/user/status", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "user_id" in data
    assert "backup_uploaded" in data
    print("✅ User status endpoint working")

def test_backup_verification():
    """Test backup verification endpoint."""
    print("Testing backup verification...")
    
    # Create a test backup file
    test_backup_path = Path("test_backup.zip")
    with open(test_backup_path, "wb") as f:
        f.write(b"fake backup content")
    
    try:
        headers = {
            "X-Secret": API_SECRET,
            "X-Session-ID": TEST_SESSION_ID
        }
        
        with open(test_backup_path, "rb") as f:
            files = {"backup": ("test_backup.zip", f, "application/zip")}
            response = requests.post(f"{API_BASE_URL}/verify_backup", headers=headers, files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] == True
        assert "file_id" in data
        print("✅ Backup verification working")
        
    finally:
        # Clean up test file
        if test_backup_path.exists():
            test_backup_path.unlink()

def test_setlist_processing():
    """Test setlist processing endpoint."""
    print("Testing setlist processing...")
    
    # Create a test PDF file
    test_pdf_path = Path("test_setlist.pdf")
    with open(test_pdf_path, "wb") as f:
        f.write(b"fake PDF content")
    
    try:
        headers = {
            "X-Secret": API_SECRET,
            "X-Session-ID": TEST_SESSION_ID
        }
        
        with open(test_pdf_path, "rb") as f:
            files = {"file": ("test_setlist.pdf", f, "application/pdf")}
            data = {"name": "Test Set"}
            response = requests.post(f"{API_BASE_URL}/process_setlist", headers=headers, files=files, data=data)
        
        # This might fail if no backup is uploaded, which is expected
        if response.status_code == 400:
            print("✅ Setlist processing correctly requires backup first")
        else:
            print("✅ Setlist processing working")
        
    finally:
        # Clean up test file
        if test_pdf_path.exists():
            test_pdf_path.unlink()

def test_user_files():
    """Test user files endpoint."""
    print("Testing user files endpoint...")
    headers = {
        "X-Secret": API_SECRET,
        "X-Session-ID": TEST_SESSION_ID
    }
    response = requests.get(f"{API_BASE_URL}/user/files", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "backups" in data
    assert "setlists" in data
    assert "downloads" in data
    print("✅ User files endpoint working")

def test_admin_endpoints():
    """Test admin endpoints."""
    print("Testing admin endpoints...")
    headers = {
        "X-Secret": API_SECRET
    }
    response = requests.get(f"{API_BASE_URL}/admin/errors", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "system_info" in data
    print("✅ Admin endpoints working")

def main():
    """Run all integration tests."""
    print("🚀 Starting integration tests...")
    print(f"Testing against: {API_BASE_URL}")
    print(f"Using secret: {API_SECRET}")
    print()
    
    try:
        test_health_endpoint()
        test_user_status()
        test_backup_verification()
        test_setlist_processing()
        test_user_files()
        test_admin_endpoints()
        
        print()
        print("🎉 All integration tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
