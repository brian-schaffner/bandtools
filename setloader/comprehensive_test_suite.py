#!/usr/bin/env python3
"""
Comprehensive Test Suite for Setlist Processing System
Covers all requirements: UI, Authentication, Processing, System Integration
"""

import subprocess
import json
import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime

class ComprehensiveTestSuite:
    def __init__(self):
        self.root = Path(__file__).parent
        self.pack_dir = self.root / "pack"
        self.uploads_dir = self.root / "uploads"
        self.test_pdf = self.uploads_dir / "TKs-1.pdf"
        self.results = {}
        self.start_time = datetime.now()
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def test_system_requirements(self):
        """Test system requirements: ports, processes, file limits"""
        self.log("🔧 Testing system requirements...")
        
        try:
            # Test file descriptor limits
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            if soft < 4096:
                self.log(f"❌ File descriptor limit too low: {soft}")
                return False
            self.log(f"✅ File descriptor limit: {soft}")
            
            # Test port availability
            import socket
            for port in [3002, 8002]:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                if result == 0:
                    self.log(f"✅ Port {port} is accessible")
                else:
                    self.log(f"❌ Port {port} is not accessible")
                    return False
                    
            return True
            
        except Exception as e:
            self.log(f"❌ System requirements test failed: {e}")
            return False
    
    def test_ui_styling(self):
        """Test UI styling requirements"""
        self.log("🎨 Testing UI styling...")
        
        try:
            # Test main page
            response = requests.get("http://localhost:3002", timeout=15)
            if response.status_code != 200:
                self.log(f"❌ Main page returned {response.status_code}")
                return False
                
            html_content = response.text
            
            # Check for proper HTML structure with Tailwind classes
            required_classes = [
                'class="min-h-screen bg-background"',
                'class="text-xl font-semibold text-foreground"',
                'class="bg-card text-card-foreground"'
            ]
            
            for class_str in required_classes:
                if class_str not in html_content:
                    self.log(f"❌ Missing required Tailwind class: {class_str}")
                    return False
                    
            # Test CSS endpoint
            css_url = "http://localhost:3002/_next/static/css/app/layout.css"
            css_response = requests.get(css_url, timeout=15)
            
            if css_response.status_code != 200:
                self.log(f"❌ CSS endpoint returned {css_response.status_code}")
                return False
                
            css_content = css_response.text
            if 'text/css' not in css_response.headers.get('content-type', '') and '.bg-background' not in css_content:
                self.log("❌ CSS not being served correctly")
                return False
                
            self.log("✅ UI styling test passed")
            return True
            
        except Exception as e:
            self.log(f"❌ UI styling test failed: {e}")
            return False
    
    def test_authentication_flow(self):
        """Test authentication requirements"""
        self.log("🔐 Testing authentication flow...")
        
        try:
            # Test user status endpoint
            response = requests.get("http://localhost:8002/user/status", timeout=10)
            if response.status_code != 200:
                self.log(f"❌ User status endpoint returned {response.status_code}")
                return False
                
            data = response.json()
            self.log(f"✅ User status: {data.get('user_email', 'Not authenticated')}")
            
            # Test OAuth endpoints exist
            oauth_endpoints = [
                "/auth/google",
                "/auth/logout"
            ]
            
            for endpoint in oauth_endpoints:
                test_response = requests.get(f"http://localhost:8002{endpoint}", timeout=5)
                # Should return some response (not 404)
                if test_response.status_code == 404:
                    self.log(f"❌ OAuth endpoint {endpoint} not found")
                    return False
                    
            self.log("✅ Authentication flow test passed")
            return True
            
        except Exception as e:
            self.log(f"❌ Authentication test failed: {e}")
            return False
    
    def test_pdf_processing_accuracy(self):
        """Test PDF processing accuracy requirements"""
        self.log("📄 Testing PDF processing accuracy...")
        
        try:
            if not self.test_pdf.exists():
                self.log("❌ Test PDF not found")
                return False
                
            # Run hybrid extraction
            output_file = self.pack_dir / "test_extraction.txt"
            result = subprocess.run([
                "python3", "src/hybrid_extractor.py",
                str(self.test_pdf),
                str(output_file)
            ], cwd=str(self.root), capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                self.log(f"❌ PDF extraction failed: {result.stderr}")
                return False
                
            # Count extracted titles
            with open(output_file, 'r') as f:
                titles = [line.strip() for line in f if line.strip()]
                
            expected_count = 59
            actual_count = len(titles)
            
            if actual_count != expected_count:
                self.log(f"❌ Expected {expected_count} songs, got {actual_count}")
                return False
                
            self.log(f"✅ PDF processing accuracy: {actual_count}/{expected_count} songs")
            return True
            
        except Exception as e:
            self.log(f"❌ PDF processing test failed: {e}")
            return False
    
    def test_catalog_matching(self):
        """Test catalog matching requirements"""
        self.log("📚 Testing catalog matching...")
        
        try:
            # Check for user backup
            backup_files = list(self.uploads_dir.glob("*.sbpbackup"))
            if not backup_files:
                self.log("❌ No backup files found")
                return False
                
            # Extract catalog from backup
            backup_file = backup_files[0]
            catalog_output = self.pack_dir / "user_catalog.txt"
            
            result = subprocess.run([
                "python3", "-c", f"""
import json
from pathlib import Path

backup_file = Path('{backup_file}')
catalog_output = Path('{catalog_output}')

# Extract from backup
import zipfile
with zipfile.ZipFile(backup_file, 'r') as zip_ref:
    zip_ref.extractall('pack/')

# Parse dataFile.txt
datafile = Path('pack/dataFile.txt')
if datafile.exists():
    with open(datafile, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if content.startswith('1.0\\n'):
        content = content[4:]
    
    data = json.loads(content)
    songs = data.get('songs', [])
    
    titles = []
    for song in songs:
        title = song.get('title', song.get('name', ''))
        if title and title.strip():
            titles.append(title.strip())
    
    with open(catalog_output, 'w', encoding='utf-8') as f:
        for title in sorted(set(titles)):
            f.write(title + '\\n')
    
    print(f'Extracted {{len(titles)}} song titles')
else:
    print('No dataFile.txt found')
"""
            ], cwd=str(self.root), capture_output=True, text=True)
            
            if result.returncode != 0:
                self.log(f"❌ Catalog extraction failed: {result.stderr}")
                return False
                
            # Check catalog size
            if catalog_output.exists():
                with open(catalog_output, 'r') as f:
                    catalog_lines = len([line for line in f if line.strip()])
                self.log(f"✅ Catalog contains {catalog_lines} songs")
                return catalog_lines > 300  # Should have many songs
            else:
                self.log("❌ Catalog file not created")
                return False
                
        except Exception as e:
            self.log(f"❌ Catalog matching test failed: {e}")
            return False
    
    def test_processing_pipeline(self):
        """Test end-to-end processing pipeline"""
        self.log("⚙️ Testing processing pipeline...")
        
        try:
            # Test processing endpoint
            files = {'file': open(self.test_pdf, 'rb')}
            response = requests.post(
                "http://localhost:8002/process_setlist_simple",
                files=files,
                headers={'X-Session-ID': 'test-session'},
                timeout=60
            )
            files['file'].close()
            
            if response.status_code != 200:
                self.log(f"❌ Processing endpoint returned {response.status_code}")
                return False
                
            data = response.json()
            
            # Check processing results
            if 'processing_results' in data:
                results = data['processing_results']
                self.log(f"✅ Processing results: {results}")
                
                # Validate metrics
                song_count = results.get('song_count', 0)
                successful_mappings = results.get('successful_mappings', 0)
                unfound_titles = results.get('unfound_titles', [])
                
                if song_count != 59:
                    self.log(f"❌ Expected 59 songs, got {song_count}")
                    return False
                    
                self.log(f"✅ Pipeline test passed: {song_count} songs, {successful_mappings} mapped")
                return True
            else:
                self.log("❌ No processing results in response")
                return False
                
        except Exception as e:
            self.log(f"❌ Processing pipeline test failed: {e}")
            return False
    
    def test_download_functionality(self):
        """Test download functionality"""
        self.log("📥 Testing download functionality...")
        
        try:
            # First process a file to get a download ID
            files = {'file': open(self.test_pdf, 'rb')}
            response = requests.post(
                "http://localhost:8002/process_setlist_simple",
                files=files,
                headers={'X-Session-ID': 'test-session'},
                timeout=60
            )
            files['file'].close()
            
            if response.status_code != 200:
                self.log(f"❌ Processing failed: {response.status_code}")
                return False
                
            data = response.json()
            download_id = data.get('download_id')
            
            if not download_id:
                self.log("❌ No download ID in response")
                return False
                
            # Test download endpoint
            download_url = f"http://localhost:8002/download/{download_id}"
            download_response = requests.get(download_url, timeout=30)
            
            if download_response.status_code != 200:
                self.log(f"❌ Download failed: {download_response.status_code}")
                return False
                
            self.log("✅ Download functionality test passed")
            return True
            
        except Exception as e:
            self.log(f"❌ Download test failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests and generate report"""
        self.log("🚀 STARTING COMPREHENSIVE TEST SUITE")
        self.log("=" * 50)
        
        tests = [
            ("System Requirements", self.test_system_requirements),
            ("UI Styling", self.test_ui_styling),
            ("Authentication Flow", self.test_authentication_flow),
            ("PDF Processing Accuracy", self.test_pdf_processing_accuracy),
            ("Catalog Matching", self.test_catalog_matching),
            ("Processing Pipeline", self.test_processing_pipeline),
            ("Download Functionality", self.test_download_functionality)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            self.log(f"\n=== {test_name.upper()} ===")
            try:
                if test_func():
                    self.log(f"✅ {test_name}: PASS")
                    passed += 1
                else:
                    self.log(f"❌ {test_name}: FAIL")
            except Exception as e:
                self.log(f"❌ {test_name}: ERROR - {e}")
        
        self.log(f"\n📊 TEST RESULTS: {passed}/{total} tests passed")
        
        if passed == total:
            self.log("🎉 ALL TESTS PASSED - SYSTEM IS FLAWLESS!")
            return True
        else:
            self.log(f"⚠️ {total - passed} tests failed - System needs fixes")
            return False

if __name__ == "__main__":
    suite = ComprehensiveTestSuite()
    success = suite.run_all_tests()
    sys.exit(0 if success else 1)
