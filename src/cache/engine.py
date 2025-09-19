#!/usr/bin/env python3
"""
Smart ROM Cache Manager - Core Engine
Handles intelligent caching of game ROMs with LRU cleanup and prioritization
"""

import os
import sqlite3
import time
import shutil
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
import requests
from datetime import datetime, timedelta

@dataclass
class CacheEntry:
    """Represents a cached ROM file"""
    rom_id: str
    filename: str
    size_bytes: int
    last_accessed: float
    download_time: float
    priority_score: int = 0
    is_favorite: bool = False

@dataclass
class CacheConfig:
    """Cache configuration settings"""
    max_size_gb: float = 50.0
    cleanup_threshold: float = 0.9  # Start cleanup at 90% full
    min_free_space_gb: float = 5.0
    favorite_protection: bool = True
    platforms_priority: Dict[str, int] = None  # Higher = keep longer
    
    def __post_init__(self):
        if self.platforms_priority is None:
            # Default platform priorities (higher = keep longer)
            self.platforms_priority = {
                'nes': 10, 'snes': 10, 'gb': 10, 'gbc': 10, 'gba': 9,
                'genesis': 8, 'n64': 7, 'psx': 6, 'ps2': 5,
                'gamecube': 4, 'wii': 3, 'xbox': 2, 'ps3': 1, 'xbox360': 1
            }

class ROMCacheManager:
    """Core cache management system"""
    
    def __init__(self, cache_dir: str, config: CacheConfig, db_path: str = None):
        self.cache_dir = Path(cache_dir)
        self.config = config
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self.db_path = db_path or (self.cache_dir / "cache.db")
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database for cache metadata"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                rom_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                last_accessed REAL NOT NULL,
                download_time REAL NOT NULL,
                priority_score INTEGER DEFAULT 0,
                is_favorite BOOLEAN DEFAULT FALSE,
                platform TEXT,
                file_hash TEXT
            )
        """)
        conn.commit()
        conn.close()
        
    def get_cache_stats(self) -> Dict:
        """Get current cache statistics"""
        total_size = 0
        file_count = 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT COUNT(*), SUM(size_bytes) FROM cache_entries")
        row = cursor.fetchone()
        file_count = row[0] or 0
        total_size = row[1] or 0
        conn.close()
        
        max_size_bytes = int(self.config.max_size_gb * 1024**3)
        usage_percent = (total_size / max_size_bytes) * 100 if max_size_bytes > 0 else 0
        
        return {
            'total_files': file_count,
            'total_size_gb': total_size / (1024**3),
            'max_size_gb': self.config.max_size_gb,
            'usage_percent': usage_percent,
            'free_space_gb': self.config.max_size_gb - (total_size / 1024**3)
        }
    
    def is_cached(self, rom_id: str) -> bool:
        """Check if ROM is already cached"""
        cache_path = self.cache_dir / f"{rom_id}"
        return cache_path.exists()
    
    def get_cache_path(self, rom_id: str) -> Path:
        """Get local cache path for ROM"""
        return self.cache_dir / rom_id
    
    def calculate_priority_score(self, entry: CacheEntry, platform: str = None) -> int:
        """Calculate priority score for cache entry"""
        score = 0
        
        # Base score from configuration
        if platform and platform in self.config.platforms_priority:
            score += self.config.platforms_priority[platform] * 10
        
        # Recently accessed bonus (decay over time)
        hours_since_access = (time.time() - entry.last_accessed) / 3600
        if hours_since_access < 24:
            score += 50  # Recently played bonus
        elif hours_since_access < 168:  # 1 week
            score += 20
        
        # Favorite protection
        if entry.is_favorite:
            score += 100
            
        # Smaller files get slight priority (easier to keep around)
        if entry.size_bytes < 100 * 1024 * 1024:  # < 100MB
            score += 10
        elif entry.size_bytes > 5 * 1024**3:  # > 5GB
            score -= 10
            
        return score
    
    def needs_cleanup(self) -> bool:
        """Check if cache cleanup is needed"""
        stats = self.get_cache_stats()
        return stats['usage_percent'] > (self.config.cleanup_threshold * 100)
    
    def cleanup_cache(self, target_free_gb: float = None) -> List[str]:
        """Remove cached files to free up space, returns list of removed ROM IDs"""
        if target_free_gb is None:
            target_free_gb = self.config.min_free_space_gb
            
        removed_roms = []
        
        # Get all cache entries sorted by priority (lowest first)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT rom_id, filename, size_bytes, last_accessed, download_time, 
                   is_favorite, platform, priority_score
            FROM cache_entries 
            ORDER BY priority_score ASC, last_accessed ASC
        """)
        
        current_stats = self.get_cache_stats()
        bytes_to_free = int((target_free_gb - current_stats['free_space_gb']) * 1024**3)
        
        if bytes_to_free <= 0:
            conn.close()
            return removed_roms
            
        freed_bytes = 0
        for row in cursor:
            rom_id = row[0]
            size_bytes = row[2]
            is_favorite = row[5]
            
            # Protect favorites if configured
            if is_favorite and self.config.favorite_protection:
                continue
                
            # Remove the file
            cache_path = self.get_cache_path(rom_id)
            if cache_path.exists():
                cache_path.unlink()
                removed_roms.append(rom_id)
                freed_bytes += size_bytes
                
                # Remove from database
                conn.execute("DELETE FROM cache_entries WHERE rom_id = ?", (rom_id,))
                
                if freed_bytes >= bytes_to_free:
                    break
        
        conn.commit()
        conn.close()
        
        return removed_roms
    
    def add_to_cache(self, rom_id: str, source_url: str, filename: str, 
                     platform: str = None) -> bool:
        """Download and add ROM to cache"""
        
        # Check if cleanup is needed first
        if self.needs_cleanup():
            self.cleanup_cache()
        
        cache_path = self.get_cache_path(rom_id)
        
        try:
            # Download the file
            response = requests.get(source_url, stream=True)
            response.raise_for_status()
            
            # Get file size
            file_size = int(response.headers.get('content-length', 0))
            
            # Check if we have enough space
            stats = self.get_cache_stats()
            available_space = (self.config.max_size_gb - stats['total_size_gb']) * 1024**3
            
            if file_size > available_space:
                # Try cleanup and check again
                self.cleanup_cache(file_size / 1024**3 + self.config.min_free_space_gb)
                stats = self.get_cache_stats()
                available_space = (self.config.max_size_gb - stats['total_size_gb']) * 1024**3
                
                if file_size > available_space:
                    raise Exception(f"Not enough space for {filename} ({file_size / 1024**3:.2f}GB)")
            
            # Download to temporary file first
            temp_path = cache_path.with_suffix('.tmp')
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Move to final location
            temp_path.rename(cache_path)
            
            # Add to database
            now = time.time()
            entry = CacheEntry(
                rom_id=rom_id,
                filename=filename,
                size_bytes=file_size,
                last_accessed=now,
                download_time=now
            )
            
            priority_score = self.calculate_priority_score(entry, platform)
            
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO cache_entries 
                (rom_id, filename, size_bytes, last_accessed, download_time, 
                 priority_score, platform)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (rom_id, filename, file_size, now, now, priority_score, platform))
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            # Cleanup on failure
            if cache_path.exists():
                cache_path.unlink()
            raise e
    
    def mark_accessed(self, rom_id: str):
        """Mark ROM as recently accessed (for LRU tracking)"""
        now = time.time()
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE cache_entries 
            SET last_accessed = ? 
            WHERE rom_id = ?
        """, (now, rom_id))
        conn.commit()
        conn.close()
    
    def set_favorite(self, rom_id: str, is_favorite: bool = True):
        """Mark ROM as favorite (protected from cleanup)"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE cache_entries 
            SET is_favorite = ? 
            WHERE rom_id = ?
        """, (is_favorite, rom_id))
        conn.commit()
        conn.close()
    
    def list_cached_roms(self) -> List[CacheEntry]:
        """Get list of all cached ROMs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT rom_id, filename, size_bytes, last_accessed, download_time, 
                   priority_score, is_favorite
            FROM cache_entries
            ORDER BY last_accessed DESC
        """)
        
        entries = []
        for row in cursor:
            entries.append(CacheEntry(
                rom_id=row[0],
                filename=row[1],
                size_bytes=row[2],
                last_accessed=row[3],
                download_time=row[4],
                priority_score=row[5],
                is_favorite=bool(row[6])
            ))
        
        conn.close()
        return entries

# Example usage and testing
if __name__ == "__main__":
    # Example configuration
    config = CacheConfig(
        max_size_gb=10.0,  # 10GB cache for testing
        cleanup_threshold=0.8
    )
    
    cache_manager = ROMCacheManager("/tmp/rom_cache_test", config)
    
    # Print cache stats
    stats = cache_manager.get_cache_stats()
    print(f"Cache Stats: {stats}")
    
    # Test cache operations would go here
    # cache_manager.add_to_cache("test_rom", "http://example.com/rom.zip", "test.zip")