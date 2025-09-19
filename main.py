#!/usr/bin/env python3
"""
Smart ROM Cache Manager - Main Application Entry Point
"""

import os
import sys
from pathlib import Path
import uvicorn
from src.cache.engine import ROMCacheManager, CacheConfig
from src.integration.emulationstation import EmulationStationIntegration, ROMServer
from src.api.app import create_app

def create_application():
    """Create and configure the application"""
    
    # Create cache directory
    cache_dir = Path("./cache")
    cache_dir.mkdir(exist_ok=True)
    
    # Create EmulationStation ROM directory for testing
    roms_dir = Path("./test_roms")
    roms_dir.mkdir(exist_ok=True)
    
    # Configure cache manager
    config = CacheConfig(
        max_size_gb=10.0,  # 10GB cache limit for testing
        cleanup_threshold=0.8,
        min_free_space_gb=1.0
    )
    
    cache_manager = ROMCacheManager(str(cache_dir), config)
    
    # Create test ROM server configuration
    rom_server = ROMServer(
        name="test_server", 
        base_url="http://localhost:8888",  # Our test server from earlier
        platform_paths={
            'nes': 'nes',
            'snes': 'snes',
            'n64': 'n64',
            'psx': 'psx'
        }
    )
    
    # Create EmulationStation integration
    integration = EmulationStationIntegration(
        cache_manager=cache_manager,
        es_roms_dir=str(roms_dir),
        rom_servers=[rom_server]
    )
    
    # Start file system watching (optional for web-only mode)
    try:
        integration.start_watching()
        print("✓ File system watcher started")
    except Exception as e:
        print(f"⚠ File watcher not started: {e}")
    
    # Create FastAPI application
    app = create_app(cache_manager, integration)
    
    return app

# Create the application instance
app = create_application()

def main():
    """Main function for running the development server"""
    print("🚀 Starting Smart ROM Cache Manager")
    print("📁 Cache directory: ./cache")
    print("📁 ROMs directory: ./test_roms")
    print("🌐 Web interface: http://localhost:8000")
    print("📚 API docs: http://localhost:8000/api/docs")
    print("⏹️  Press Ctrl+C to stop")
    
    # Run the development server
    uvicorn.run(
        "main:app",  # Import string format for reload
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src"],  # Only reload on src changes
        log_level="info"
    )

if __name__ == "__main__":
    main()