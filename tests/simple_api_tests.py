#!/usr/bin/env python3
"""
Simple API Tests - Quick validation that everything is working
Run with: python tests/simple_api_tests.py
"""

import requests
import json
import time
import sys
from pathlib import Path

class SimpleAPITester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.passed = 0
        self.failed = 0
        
    def test(self, name, test_func):
        """Run a test and track results"""
        try:
            print(f"🧪 Testing {name}... ", end="")
            result = test_func()
            if result:
                print("✅ PASS")
                self.passed += 1
            else:
                print("❌ FAIL")
                self.failed += 1
        except Exception as e:
            print(f"❌ FAIL - {e}")
            self.failed += 1
            
    def test_health_check(self):
        """Test basic health endpoint"""
        response = requests.get(f"{self.base_url}/api/health", timeout=5)
        data = response.json()
        return response.status_code == 200 and data.get("status") == "healthy"
        
    def test_cache_stats(self):
        """Test cache statistics"""
        response = requests.get(f"{self.base_url}/api/cache/stats", timeout=5)
        data = response.json()
        required_fields = ["total_files", "total_size_gb", "usage_percent", "free_space_gb"]
        return (response.status_code == 200 and 
                all(field in data for field in required_fields))
    
    def test_cache_config(self):
        """Test cache configuration"""
        response = requests.get(f"{self.base_url}/api/cache/config", timeout=5)
        data = response.json()
        return (response.status_code == 200 and 
                "max_size_gb" in data and 
                "cleanup_threshold" in data)
                
    def test_rom_search(self):
        """Test ROM search endpoint"""
        response = requests.get(f"{self.base_url}/api/roms", timeout=5)
        data = response.json()
        return (response.status_code == 200 and 
                "roms" in data and 
                "total_count" in data and
                isinstance(data["roms"], list))
                
    def test_system_status(self):
        """Test system status"""
        response = requests.get(f"{self.base_url}/api/status", timeout=5)
        data = response.json()
        return (response.status_code == 200 and 
                "status" in data and
                "uptime_seconds" in data)
                
    def test_web_dashboard(self):
        """Test web dashboard loads"""
        response = requests.get(f"{self.base_url}/", timeout=5)
        return (response.status_code == 200 and 
                "text/html" in response.headers.get("content-type", ""))
                
    def test_api_docs(self):
        """Test API documentation"""
        response = requests.get(f"{self.base_url}/api/docs", timeout=5)
        return (response.status_code == 200 and 
                "text/html" in response.headers.get("content-type", ""))
                
    def test_cache_cleanup(self):
        """Test cache cleanup endpoint"""
        cleanup_data = {"force": False}
        response = requests.post(
            f"{self.base_url}/api/cache/cleanup",
            json=cleanup_data,
            timeout=10
        )
        data = response.json()
        return (response.status_code == 200 and 
                "removed_roms" in data and 
                "message" in data)
                
    def test_config_update(self):
        """Test configuration update"""
        # Get current config
        response = requests.get(f"{self.base_url}/api/cache/config", timeout=5)
        if response.status_code != 200:
            return False
            
        original_config = response.json()
        original_size = original_config.get("max_size_gb", 10.0)
        
        # Update config
        new_size = original_size + 1.0
        update_data = {"max_size_gb": new_size}
        response = requests.put(
            f"{self.base_url}/api/cache/config",
            json=update_data,
            timeout=5
        )
        
        if response.status_code != 200:
            return False
            
        # Verify update
        response = requests.get(f"{self.base_url}/api/cache/config", timeout=5)
        updated_config = response.json()
        
        # Reset to original
        reset_data = {"max_size_gb": original_size}
        requests.put(f"{self.base_url}/api/cache/config", json=reset_data)
        
        return updated_config.get("max_size_gb") == new_size
        
    def test_performance(self):
        """Test basic performance"""
        start_time = time.time()
        response = requests.get(f"{self.base_url}/api/cache/stats", timeout=5)
        end_time = time.time()
        
        response_time = end_time - start_time
        return response.status_code == 200 and response_time < 1.0
        
    def run_all_tests(self):
        """Run complete test suite"""
        print("🚀 Smart ROM Cache Manager - API Test Suite")
        print("=" * 50)
        
        # Wait for service to be ready
        print("⏳ Waiting for service to be ready...")
        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"{self.base_url}/api/health", timeout=2)
                if response.status_code == 200:
                    print("✅ Service is ready!")
                    break
            except:
                pass
            time.sleep(1)
        else:
            print("❌ Service not ready after 30 seconds")
            return False
            
        print()
        
        # Run tests
        self.test("Health Check", self.test_health_check)
        self.test("Cache Stats", self.test_cache_stats)  
        self.test("Cache Config", self.test_cache_config)
        self.test("ROM Search", self.test_rom_search)
        self.test("System Status", self.test_system_status)
        self.test("Web Dashboard", self.test_web_dashboard)
        self.test("API Documentation", self.test_api_docs)
        self.test("Cache Cleanup", self.test_cache_cleanup)
        self.test("Config Update", self.test_config_update)
        self.test("Performance", self.test_performance)
        
        print()
        print("=" * 50)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📊 Total: {self.passed + self.failed}")
        
        if self.failed == 0:
            print("🎉 ALL TESTS PASSED! System is ready for production.")
        else:
            print(f"⚠️  {self.failed} tests failed. Check the issues above.")
            
        return self.failed == 0


def test_rom_server_integration():
    """Test integration with ROM server"""
    print("\n🌐 Testing ROM Server Integration")
    print("-" * 30)
    
    rom_server_url = "http://localhost:8888"
    
    test_files = [
        "nes/mario.nes",
        "snes/metroid.smc",
        "n64/mario64.z64",
        "psx/ff7.bin"
    ]
    
    server_working = True
    for test_file in test_files:
        try:
            response = requests.get(f"{rom_server_url}/{test_file}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {test_file} - Available ({len(response.content)} bytes)")
            else:
                print(f"❌ {test_file} - Not found (HTTP {response.status_code})")
                server_working = False
        except Exception as e:
            print(f"❌ {test_file} - Error: {e}")
            server_working = False
            
    if server_working:
        print("🎉 ROM Server is working correctly!")
    else:
        print("⚠️  ROM Server issues detected. Start with:")
        print("   cd test_data/rom_server && python -m http.server 8888")
        
    return server_working


if __name__ == "__main__":
    # Test ROM Cache Manager API
    tester = SimpleAPITester()
    api_success = tester.run_all_tests()
    
    # Test ROM Server
    rom_server_success = test_rom_server_integration()
    
    # Overall result
    if api_success and rom_server_success:
        print("\n🚀 SYSTEM READY FOR DOCKER PACKAGING! 🚀")
        sys.exit(0)
    else:
        print("\n⚠️  Fix issues before proceeding to Docker")
        sys.exit(1)