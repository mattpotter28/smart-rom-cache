#!/usr/bin/env python3
"""
API Models - Pydantic data models for REST API
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

class CacheStatsResponse(BaseModel):
    """Cache statistics response model"""
    total_files: int = Field(description="Total number of cached ROM files")
    total_size_gb: float = Field(description="Total cache size in GB")
    max_size_gb: float = Field(description="Maximum cache size limit in GB")
    usage_percent: float = Field(description="Cache usage percentage")
    free_space_gb: float = Field(description="Available cache space in GB")
    
class ROMStatus(str, Enum):
    """ROM availability status"""
    CACHED = "cached"
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    ERROR = "error"

class ROMInfo(BaseModel):
    """ROM information model"""
    rom_id: str = Field(description="Unique ROM identifier")
    filename: str = Field(description="ROM filename")
    platform: str = Field(description="Gaming platform (nes, snes, etc.)")
    size_bytes: Optional[int] = Field(default=None, description="ROM file size in bytes")
    size_mb: Optional[float] = Field(default=None, description="ROM file size in MB")
    status: ROMStatus = Field(description="Current ROM status")
    is_favorite: bool = Field(default=False, description="Whether ROM is marked as favorite")
    last_accessed: Optional[datetime] = Field(default=None, description="Last access timestamp")
    download_time: Optional[datetime] = Field(default=None, description="Download timestamp")
    priority_score: int = Field(default=0, description="Cache priority score")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class PlatformInfo(BaseModel):
    """Platform information model"""
    platform: str = Field(description="Platform identifier")
    display_name: str = Field(description="Human-readable platform name")
    cached_count: int = Field(description="Number of cached ROMs for this platform")
    available_count: int = Field(description="Total available ROMs for this platform")
    total_size_gb: float = Field(description="Total size of cached ROMs for this platform")

class ServerInfo(BaseModel):
    """ROM server information model"""
    name: str = Field(description="Server name")
    base_url: str = Field(description="Server base URL")
    status: str = Field(description="Server connection status")
    platforms: List[str] = Field(description="Supported platforms")
    last_check: Optional[datetime] = Field(default=None, description="Last connectivity check")

class DownloadRequest(BaseModel):
    """ROM download request model"""
    rom_id: str = Field(description="ROM identifier to download")
    priority: Optional[int] = Field(default=0, description="Download priority")

class DownloadResponse(BaseModel):
    """ROM download response model"""
    rom_id: str = Field(description="ROM identifier")
    status: str = Field(description="Download status")
    message: str = Field(description="Status message")
    download_url: Optional[str] = Field(default=None, description="Download URL used")

class BulkDownloadRequest(BaseModel):
    """Bulk ROM download request model"""
    rom_ids: List[str] = Field(description="List of ROM identifiers to download")
    priority: Optional[int] = Field(default=0, description="Download priority for all ROMs")

class CacheConfigResponse(BaseModel):
    """Cache configuration response model"""
    max_size_gb: float = Field(description="Maximum cache size in GB")
    cleanup_threshold: float = Field(description="Cleanup threshold (0.0-1.0)")
    min_free_space_gb: float = Field(description="Minimum free space to maintain")
    favorite_protection: bool = Field(description="Whether favorites are protected from cleanup")
    platforms_priority: Dict[str, int] = Field(description="Platform priority mapping")

class CacheConfigUpdate(BaseModel):
    """Cache configuration update model"""
    max_size_gb: Optional[float] = Field(default=None, description="Maximum cache size in GB")
    cleanup_threshold: Optional[float] = Field(default=None, description="Cleanup threshold (0.0-1.0)")
    min_free_space_gb: Optional[float] = Field(default=None, description="Minimum free space to maintain")
    favorite_protection: Optional[bool] = Field(default=None, description="Whether favorites are protected from cleanup")
    platforms_priority: Optional[Dict[str, int]] = Field(default=None, description="Platform priority mapping")

class CleanupRequest(BaseModel):
    """Cache cleanup request model"""
    target_free_gb: Optional[float] = Field(default=None, description="Target free space in GB")
    force: bool = Field(default=False, description="Force cleanup even if not needed")

class CleanupResponse(BaseModel):
    """Cache cleanup response model"""
    removed_roms: List[str] = Field(description="List of ROM IDs that were removed")
    freed_gb: float = Field(description="Amount of space freed in GB")
    message: str = Field(description="Cleanup result message")

class FavoriteUpdateRequest(BaseModel):
    """ROM favorite status update request"""
    rom_id: str = Field(description="ROM identifier")
    is_favorite: bool = Field(description="New favorite status")

class SearchRequest(BaseModel):
    """ROM search request model"""
    query: Optional[str] = Field(default=None, description="Search query string")
    platform: Optional[str] = Field(default=None, description="Filter by platform")
    status: Optional[ROMStatus] = Field(default=None, description="Filter by ROM status")
    favorites_only: bool = Field(default=False, description="Show only favorites")
    sort_by: str = Field(default="name", description="Sort field (name, size, last_accessed, platform)")
    sort_order: str = Field(default="asc", description="Sort order (asc, desc)")
    limit: int = Field(default=100, description="Maximum results to return")
    offset: int = Field(default=0, description="Results offset for pagination")

class SearchResponse(BaseModel):
    """ROM search response model"""
    roms: List[ROMInfo] = Field(description="List of matching ROMs")
    total_count: int = Field(description="Total number of matching ROMs")
    has_more: bool = Field(description="Whether there are more results available")

class SystemStatusResponse(BaseModel):
    """System status response model"""
    status: str = Field(description="Overall system status")
    cache_manager: str = Field(description="Cache manager status")
    file_watcher: str = Field(description="File watcher status")
    servers: List[ServerInfo] = Field(description="ROM server statuses")
    uptime_seconds: float = Field(description="System uptime in seconds")
    version: str = Field(description="Application version")

class ErrorResponse(BaseModel):
    """API error response model"""
    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")

class SuccessResponse(BaseModel):
    """Generic success response model"""
    success: bool = Field(default=True, description="Operation success status")
    message: str = Field(description="Success message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Additional response data")

# Platform display name mappings
PLATFORM_DISPLAY_NAMES = {
    "nes": "Nintendo Entertainment System",
    "snes": "Super Nintendo",
    "gb": "Game Boy",
    "gbc": "Game Boy Color", 
    "gba": "Game Boy Advance",
    "genesis": "Sega Genesis",
    "n64": "Nintendo 64",
    "psx": "PlayStation",
    "ps2": "PlayStation 2",
    "gamecube": "Nintendo GameCube",
    "wii": "Nintendo Wii",
    "xbox": "Original Xbox",
    "ps3": "PlayStation 3",
    "xbox360": "Xbox 360",
    "switch": "Nintendo Switch"
}

def get_platform_display_name(platform: str) -> str:
    """Get human-readable platform name"""
    return PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform.title())