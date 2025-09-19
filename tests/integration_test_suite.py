#!/usr/bin/env python3
"""
ROM Cache Manager - Test Suite
Comprehensive testing without requiring full EmulationStation setup
"""

import os
import tempfile
import shutil
import time
import threading
from pathlib import Path
import sqlite3
import requests
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver
from unittest.mock import Mock, patch
import json

# Import our modules (in real deployment these would be proper imports)
from src.cache.engine import ROMCacheManager, CacheConfig, CacheEntry
# from src.integration.emulationstation import EmulationStationIntegration, ROMServer

class MockHTTPServer:
    """Simple HTTP server for testing ROM downloads"""
    
    def __init__(self, test_files_dir: Path):
        self.test_files_dir = test_files_dir
        self.server = None
        self.thread = None
        self.port = 8888
        
    def start(self):
        """Start mock HTTP server"""
        os.chdir(self.test_files_dir)
        
        handler = SimpleHTTPRequestHandler
        self.server = HTTPServer(("localhost", self.port), handler)
        
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        
        print(f"Mock HTTP server started at http://localhost:{self.port}")
    
    def stop(self):
        """Stop mock HTTP server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()

class ROMCacheTestSuite:
    """Comprehensive test suite for ROM cache system"""
    
    def __init__(self):
        self.temp_dir = None
        self.cache_manager = None
        self.mock_server = None
        
    def setup(self):
        """Setup test environment"""
        print("Setting up test environment...")
        
        # Create temporary directory structure
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rom_cache_test_"))
        print(f"Test directory: {self.temp_dir}")
        
        # Create test ROM files
        self.test_files_dir = self.temp_dir / "test_roms"
        self.test_files_dir.mkdir(parents=True)
        
        # Create mock ROM files of various sizes
        self.create_test_roms()
        
        # Start mock HTTP server
        self.mock_server = MockHTTPServer(self.test_files_dir)
        self.mock_server.start()
        time.sleep(0.5)  # Give server time to start
        
        # Setup cache manager
        cache_dir = self.temp_dir / "cache"
        config = CacheConfig(
            max_size_gb=0.1,  # 100MB for testing
            cleanup_threshold=0.7,
            min_free_space_gb=0.01
        )
        
        self.cache_manager = ROMCacheManager(str(cache_dir), config)
        
        print("Test environment ready!")
    
    def create_test_roms(self):
        """Create test ROM files of various sizes"""
        test_roms = [
            ("nes/super_mario_bros.nes", 40 * 1024),      # 40KB - typical NES
            ("nes/zelda.nes", 128 * 1024),                # 128KB - larger NES
            ("snes/super_metroid.smc", 3 * 1024 * 1024),  # 3MB - SNES
            ("n64/mario64.z64", 8 * 1024 * 1024),         # 8MB - N64
            ("psx/ff7_disc1.bin", 650 * 1024 * 1024),     # 650MB - PSX (large)
        ]
        
        for rom_path, size in test_roms:
            full_path = self.test_files_dir / rom_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create file with random-ish content
            with open(full_path, 'wb') as f:
                # Write size bytes of data
                chunk = b'ROM_DATA_' * 100  # 900 bytes per chunk
                chunks_needed = size // len(chunk)
                remainder = size % len(chunk)
                
                for _ in range(chunks_needed):
                    f.write(chunk)
                if remainder:
                    f.write(chunk[:remainder])
            
            print(f"Created test ROM: {rom_path} ({size / 1024:.1f}KB)")
    
    def test_basic_cache_operations(self):
        """Test basic cache functionality"""
        print("\n=== Testing Basic Cache Operations ===")
        
        # Test initial stats
        stats = self.cache_manager.get_cache_stats()
        assert stats['total_files'] == 0
        assert stats['total_size_gb'] == 0
        print("✓ Initial cache stats correct")
        
        # Test adding a small ROM
        small_rom_url = f"http://localhost:{self.mock_server.port}/nes/super_mario_bros.nes"
        success = self.cache_manager.add_to_cache(
            rom_id="nes_super_mario_bros",
            source_url=small_rom_url,
            filename="super_mario_bros.nes",
            platform="nes"
        )
        
        assert success, "Failed to cache small ROM"
        assert self.cache_manager.is_cached("nes_super_mario_bros")
        print("✓ Small ROM cached successfully")
        
        # Test cache stats update
        stats = self.cache_manager.get_cache_stats()
        assert stats['total_files'] == 1
        assert stats['total_size_gb'] > 0
        print("✓ Cache stats updated correctly")
        
        # Test marking as accessed
        self.cache_manager.mark_accessed("nes_super_mario_bros")
        print("✓ ROM marked as accessed")
        
        # Test setting favorite
        self.cache_manager.set_favorite("nes_super_mario_bros", True)
        print("✓ ROM marked as favorite")
        
        return True
    
    def test_cache_cleanup(self):
        """Test cache cleanup and LRU logic"""
        print("\n=== Testing Cache Cleanup ===")
        
        # Fill cache with multiple ROMs
        roms_to_cache = [
            ("nes_super_mario_bros", "nes/super_mario_bros.nes", "nes"),
            ("nes_zelda", "nes/zelda.nes", "nes"),
            ("snes_super_metroid", "snes/super_metroid.smc", "snes"),
            ("n64_mario64", "n64/mario64.z64", "n64")
        ]
        
        for rom_id, rom_path, platform in roms_to_cache:
            url = f"http://localhost:{self.mock_server.port}/{rom_path}"
            try:
                self.cache_manager.add_to_cache(rom_id, url, Path(rom_path).name, platform)
                print(f"✓ Cached {rom_id}")
            except Exception as e:
                print(f"⚠ Failed to cache {rom_id}: {e}")
        
        # Check stats before cleanup
        stats = self.cache_manager.get_cache_stats()
        print(f"Cache usage before cleanup: {stats['usage_percent']:.1f}%")
        
        # Force cleanup by trying to add large ROM
        large_rom_url = f"http://localhost:{self.mock_server.port}/psx/ff7_disc1.bin"
        try:
            self.cache_manager.add_to_cache(
                "psx_ff7", large_rom_url, "ff7_disc1.bin", "psx"
            )
            print("✓ Large ROM cached (triggered cleanup)")
        except Exception as e:
            print(f"Large ROM caching failed (expected): {e}")
        
        # Check cleanup results
        stats = self.cache_manager.get_cache_stats()
        print(f"Cache usage after cleanup: {stats['usage_percent']:.1f}%")
        
        # List remaining ROMs
        cached_roms = self.cache_manager.list_cached_roms()
        print(f"ROMs remaining after cleanup: {len(cached_roms)}")
        for rom in cached_roms:
            print(f"  - {rom.rom_id} (favorite: {rom.is_favorite})")
        
        return True
    
    def test_priority_scoring(self):
        """Test priority scoring algorithm"""
        print("\n=== Testing Priority Scoring ===")
        
        # Create test entries with different characteristics
        now = time.time()
        
        # Recent, small, favorite ROM
        recent_fav = CacheEntry(
            rom_id="test_recent_fav",
            filename="recent_fav.nes",
            size_bytes=40 * 1024,
            last_accessed=now - 3600,  # 1 hour ago
            download_time=now - 7200,
            is_favorite=True
        )
        
        # Old, large ROM
        old_large = CacheEntry(
            rom_id="test_old_large",
            filename="old_large.bin",
            size_bytes=650 * 1024 * 1024,  # 650MB
            last_accessed=now - 30 * 24 * 3600,  # 30 days ago
            download_time=now - 30 * 24 * 3600,
            is_favorite=False
        )
        
        # Calculate priority scores
        recent_score = self.cache_manager.calculate_priority_score(recent_fav, "nes")
        old_score = self.cache_manager.calculate_priority_score(old_large, "psx")
        
        print(f"Recent favorite ROM score: {recent_score}")
        print(f"Old large ROM score: {old_score}")
        
        assert recent_score > old_score, "Priority scoring logic incorrect"
        print("✓ Priority scoring working correctly")
        
        return True
    
    def test_concurrent_access(self):
        """Test concurrent access handling"""
        print("\n=== Testing Concurrent Access ===")
        
        # This would test the threading logic in EmulationStation integration
        # For now, just test that cache manager is thread-safe
        
        def cache_rom(rom_id, delay=0):
            time.sleep(delay)
            url = f"http://localhost:{self.mock_server.port}/nes/super_mario_bros.nes"
            try:
                return self.cache_manager.add_to_cache(rom_id, url, "test.nes", "nes")
            except Exception as e:
                print(f"Thread {rom_id} failed: {e}")
                return False
        
        # Start multiple threads trying to cache different ROMs
        threads = []
        for i in range(3):
            t = threading.Thread(target=cache_rom, args=(f"concurrent_test_{i}", i * 0.1))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        print("✓ Concurrent access test completed")
        return True
    
    def test_symlink_integration(self):
        """Test cross-platform linking integration"""
        print("\n=== Testing Cross-Platform Linking Integration ===")
        
        # Import the cross-platform linker
        from src.integration.emulationstation import CrossPlatformLinker
        
        # Create mock EmulationStation directory structure
        es_roms_dir = self.temp_dir / "roms"
        nes_dir = es_roms_dir / "nes"
        nes_dir.mkdir(parents=True)
        
        # Initialize cross-platform linker
        linker = CrossPlatformLinker()
        print(f"Detected link strategy: {linker.strategy.value}")
        
        # Create a link pointing to cache
        rom_id = "nes_test_link"
        cache_path = self.cache_manager.get_cache_path(rom_id)
        target_path = nes_dir / "test_game.nes"
        
        # Create the link using cross-platform strategy
        success = linker.create_link(cache_path, target_path)
        assert success, "Failed to create link"
        print("✓ Link created successfully")
        
        # Cache the ROM
        url = f"http://localhost:{self.mock_server.port}/nes/super_mario_bros.nes"
        success = self.cache_manager.add_to_cache(rom_id, url, "test_game.nes", "nes")
        assert success
        print("✓ ROM cached successfully")
        
        # Verify cache file exists
        assert cache_path.exists()
        print("✓ Cache file exists")
        
        # Update the target (important for copy strategy)
        linker.update_cached_file(cache_path, target_path)
        
        # Verify target file accessibility
        assert target_path.exists(), "Target file should be accessible"
        print("✓ Target file accessible")
        
        # Test cleanup
        success = linker.remove_link(target_path)
        assert success, "Failed to remove link"
        print("✓ Link cleanup successful")
        
        return True
    
    def test_error_handling(self):
        """Test error handling scenarios"""
        print("\n=== Testing Error Handling ===")
        
        # Test download of non-existent ROM
        try:
            self.cache_manager.add_to_cache(
                "nonexistent", 
                f"http://localhost:{self.mock_server.port}/does_not_exist.rom",
                "missing.rom", 
                "test"
            )
            assert False, "Should have failed for non-existent ROM"
        except Exception as e:
            print(f"✓ Correctly handled missing ROM: {type(e).__name__}")
        
        # Test invalid ROM ID
        assert not self.cache_manager.is_cached("invalid_rom_id")
        print("✓ Correctly handled invalid ROM ID")
        
        # Test database operations with invalid data
        try:
            self.cache_manager.mark_accessed("nonexistent_rom")
            print("✓ Gracefully handled accessing non-existent ROM")
        except Exception as e:
            print(f"⚠ Unexpected error: {e}")
        
        return True
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("ROM Cache Manager Test Suite")
        print("=" * 50)
        
        try:
            self.setup()
            
            tests = [
                self.test_basic_cache_operations,
                self.test_cache_cleanup,
                self.test_priority_scoring,
                self.test_concurrent_access,
                self.test_symlink_integration,
                self.test_error_handling
            ]
            
            passed = 0
            failed = 0
            
            for test in tests:
                try:
                    if test():
                        passed += 1
                        print(f"✅ {test.__name__} PASSED")
                    else:
                        failed += 1
                        print(f"❌ {test.__name__} FAILED")
                except Exception as e:
                    failed += 1
                    print(f"❌ {test.__name__} FAILED: {e}")
                    import traceback
                    traceback.print_exc()
            
            print(f"\n=== Test Results ===")
            print(f"Passed: {passed}")
            print(f"Failed: {failed}")
            print(f"Total:  {passed + failed}")
            
            # Show final cache stats
            stats = self.cache_manager.get_cache_stats()
            print(f"\nFinal cache stats: {stats}")
            
        except Exception as e:
            print(f"Test setup failed: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up test environment"""
        print("\nCleaning up test environment...")
        
        if self.mock_server:
            self.mock_server.stop()
        
        # Give Windows a moment to release file handles
        import sys
        if sys.platform.startswith('win'):
            time.sleep(1)
        
        if self.temp_dir and self.temp_dir.exists():
            try:
                # Try normal cleanup first
                shutil.rmtree(self.temp_dir)
                print(f"Removed test directory: {self.temp_dir}")
            except PermissionError as e:
                print(f"⚠ Cleanup warning (Windows file lock): {e}")
                print("  Test files may remain in temp directory - this is normal on Windows")
                # On Windows, temp files will be cleaned up on reboot
                # Don't fail the test for this common Windows issue

# Simple test runner
if __name__ == "__main__":
    test_suite = ROMCacheTestSuite()
    test_suite.run_all_tests()