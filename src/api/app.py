#!/usr/bin/env python3
"""
FastAPI Application - REST API Backend for Smart ROM Cache Manager
"""

import time
import asyncio
import threading
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import our models and core components
from .models import *
from ..cache.engine import ROMCacheManager, CacheConfig
from ..integration.emulationstation import EmulationStationIntegration, ROMServer

class ROMCacheAPI:
    """Main API application class"""
    
    def __init__(self, cache_manager: ROMCacheManager, integration: EmulationStationIntegration):
        self.cache_manager = cache_manager
        self.integration = integration
        self.start_time = time.time()
        self.app = self._create_app()
        
        # Track download status
        self.downloading_roms: Dict[str, str] = {}  # rom_id -> status
        
    def _create_app(self) -> FastAPI:
        """Create FastAPI application with all routes"""
        app = FastAPI(
            title="Smart ROM Cache Manager",
            description="Intelligent caching system for retro gaming ROM collections",
            version="0.1.0",
            docs_url="/api/docs",
            redoc_url="/api/redoc"
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Mount static files and templates
        static_path = Path(__file__).parent.parent / "web" / "static"
        templates_path = Path(__file__).parent.parent / "web" / "templates"
        
        if static_path.exists():
            app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
        
        self.templates = Jinja2Templates(directory=str(templates_path)) if templates_path.exists() else None
        
        # Add all routes
        self._add_cache_routes(app)
        self._add_rom_routes(app)
        self._add_system_routes(app)
        self._add_web_routes(app)
        
        return app
    
    def _add_cache_routes(self, app: FastAPI):
        """Add cache management routes"""
        
        @app.get("/api/cache/stats", response_model=CacheStatsResponse)
        async def get_cache_stats():
            """Get current cache statistics"""
            try:
                stats = self.cache_manager.get_cache_stats()
                return CacheStatsResponse(**stats)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/cache/config", response_model=CacheConfigResponse)
        async def get_cache_config():
            """Get current cache configuration"""
            try:
                config = self.cache_manager.config
                return CacheConfigResponse(
                    max_size_gb=config.max_size_gb,
                    cleanup_threshold=config.cleanup_threshold,
                    min_free_space_gb=config.min_free_space_gb,
                    favorite_protection=config.favorite_protection,
                    platforms_priority=config.platforms_priority
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.put("/api/cache/config", response_model=SuccessResponse)
        async def update_cache_config(config_update: CacheConfigUpdate):
            """Update cache configuration"""
            try:
                # Update configuration (in a real app, this would persist to config file)
                if config_update.max_size_gb is not None:
                    self.cache_manager.config.max_size_gb = config_update.max_size_gb
                if config_update.cleanup_threshold is not None:
                    self.cache_manager.config.cleanup_threshold = config_update.cleanup_threshold
                if config_update.min_free_space_gb is not None:
                    self.cache_manager.config.min_free_space_gb = config_update.min_free_space_gb
                if config_update.favorite_protection is not None:
                    self.cache_manager.config.favorite_protection = config_update.favorite_protection
                if config_update.platforms_priority is not None:
                    self.cache_manager.config.platforms_priority = config_update.platforms_priority
                
                return SuccessResponse(message="Cache configuration updated successfully")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/api/cache/cleanup", response_model=CleanupResponse)
        async def cleanup_cache(cleanup_request: CleanupRequest):
            """Trigger cache cleanup"""
            try:
                if cleanup_request.force or self.cache_manager.needs_cleanup():
                    removed_roms = self.cache_manager.cleanup_cache(cleanup_request.target_free_gb)
                    
                    # Calculate freed space (approximate)
                    freed_gb = len(removed_roms) * 0.1  # Rough estimate
                    
                    return CleanupResponse(
                        removed_roms=removed_roms,
                        freed_gb=freed_gb,
                        message=f"Cleanup completed. Removed {len(removed_roms)} ROMs."
                    )
                else:
                    return CleanupResponse(
                        removed_roms=[],
                        freed_gb=0.0,
                        message="Cleanup not needed at this time."
                    )
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    def _add_rom_routes(self, app: FastAPI):
        """Add ROM management routes"""
        
        @app.get("/api/roms", response_model=SearchResponse)
        async def search_roms(
            query: Optional[str] = Query(None, description="Search query"),
            platform: Optional[str] = Query(None, description="Filter by platform"),
            status: Optional[ROMStatus] = Query(None, description="Filter by status"),
            favorites_only: bool = Query(False, description="Show only favorites"),
            sort_by: str = Query("filename", description="Sort field"),
            sort_order: str = Query("asc", description="Sort order"),
            limit: int = Query(100, description="Max results"),
            offset: int = Query(0, description="Results offset")
        ):
            """Search and list ROMs"""
            try:
                # Get cached ROMs
                cached_roms = self.cache_manager.list_cached_roms()
                
                # Convert to ROMInfo models
                rom_infos = []
                for rom in cached_roms:
                    rom_info = ROMInfo(
                        rom_id=rom.rom_id,
                        filename=rom.filename,
                        platform=rom.rom_id.split('_')[0] if '_' in rom.rom_id else 'unknown',
                        size_bytes=rom.size_bytes,
                        size_mb=round(rom.size_bytes / (1024 * 1024), 2) if rom.size_bytes else None,
                        status=ROMStatus.CACHED,
                        is_favorite=rom.is_favorite,
                        last_accessed=datetime.fromtimestamp(rom.last_accessed) if rom.last_accessed else None,
                        download_time=datetime.fromtimestamp(rom.download_time) if rom.download_time else None,
                        priority_score=rom.priority_score
                    )
                    rom_infos.append(rom_info)
                
                # Apply filters
                filtered_roms = rom_infos
                
                if query:
                    query = query.lower()
                    filtered_roms = [r for r in filtered_roms if query in r.filename.lower()]
                
                if platform:
                    filtered_roms = [r for r in filtered_roms if r.platform == platform]
                
                if status:
                    filtered_roms = [r for r in filtered_roms if r.status == status]
                
                if favorites_only:
                    filtered_roms = [r for r in filtered_roms if r.is_favorite]
                
                # Apply sorting
                reverse = sort_order.lower() == 'desc'
                if sort_by == 'filename':
                    filtered_roms.sort(key=lambda x: x.filename, reverse=reverse)
                elif sort_by == 'size':
                    filtered_roms.sort(key=lambda x: x.size_bytes or 0, reverse=reverse)
                elif sort_by == 'last_accessed':
                    filtered_roms.sort(key=lambda x: x.last_accessed or datetime.min, reverse=reverse)
                elif sort_by == 'platform':
                    filtered_roms.sort(key=lambda x: x.platform, reverse=reverse)
                
                # Apply pagination
                total_count = len(filtered_roms)
                paginated_roms = filtered_roms[offset:offset + limit]
                
                return SearchResponse(
                    roms=paginated_roms,
                    total_count=total_count,
                    has_more=offset + limit < total_count
                )
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/roms/{rom_id}", response_model=ROMInfo)
        async def get_rom_info(rom_id: str):
            """Get detailed information about a specific ROM"""
            try:
                cached_roms = self.cache_manager.list_cached_roms()
                rom_entry = next((r for r in cached_roms if r.rom_id == rom_id), None)
                
                if not rom_entry:
                    raise HTTPException(status_code=404, detail="ROM not found")
                
                return ROMInfo(
                    rom_id=rom_entry.rom_id,
                    filename=rom_entry.filename,
                    platform=rom_entry.rom_id.split('_')[0] if '_' in rom_entry.rom_id else 'unknown',
                    size_bytes=rom_entry.size_bytes,
                    size_mb=round(rom_entry.size_bytes / (1024 * 1024), 2) if rom_entry.size_bytes else None,
                    status=ROMStatus.CACHED,
                    is_favorite=rom_entry.is_favorite,
                    last_accessed=datetime.fromtimestamp(rom_entry.last_accessed) if rom_entry.last_accessed else None,
                    download_time=datetime.fromtimestamp(rom_entry.download_time) if rom_entry.download_time else None,
                    priority_score=rom_entry.priority_score
                )
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/api/roms/download", response_model=DownloadResponse)
        async def download_rom(download_request: DownloadRequest, background_tasks: BackgroundTasks):
            """Download a ROM to cache"""
            try:
                rom_id = download_request.rom_id
                
                # Check if already cached
                if self.cache_manager.is_cached(rom_id):
                    return DownloadResponse(
                        rom_id=rom_id,
                        status="already_cached",
                        message="ROM is already cached"
                    )
                
                # Check if already downloading
                if rom_id in self.downloading_roms:
                    return DownloadResponse(
                        rom_id=rom_id,
                        status="downloading",
                        message="ROM download already in progress"
                    )
                
                # Start download in background
                self.downloading_roms[rom_id] = "downloading"
                background_tasks.add_task(self._download_rom_task, rom_id)
                
                return DownloadResponse(
                    rom_id=rom_id,
                    status="started",
                    message="ROM download started"
                )
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.put("/api/roms/{rom_id}/favorite", response_model=SuccessResponse)
        async def update_rom_favorite(rom_id: str, favorite_request: FavoriteUpdateRequest):
            """Update ROM favorite status"""
            try:
                self.cache_manager.set_favorite(rom_id, favorite_request.is_favorite)
                status = "added to" if favorite_request.is_favorite else "removed from"
                return SuccessResponse(message=f"ROM {status} favorites")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/platforms", response_model=List[PlatformInfo])
        async def get_platforms():
            """Get platform statistics"""
            try:
                cached_roms = self.cache_manager.list_cached_roms()
                platform_stats = {}
                
                for rom in cached_roms:
                    platform = rom.rom_id.split('_')[0] if '_' in rom.rom_id else 'unknown'
                    if platform not in platform_stats:
                        platform_stats[platform] = {
                            'cached_count': 0,
                            'total_size_bytes': 0
                        }
                    
                    platform_stats[platform]['cached_count'] += 1
                    platform_stats[platform]['total_size_bytes'] += rom.size_bytes or 0
                
                platforms = []
                for platform, stats in platform_stats.items():
                    platforms.append(PlatformInfo(
                        platform=platform,
                        display_name=get_platform_display_name(platform),
                        cached_count=stats['cached_count'],
                        available_count=stats['cached_count'],  # For now, same as cached
                        total_size_gb=stats['total_size_bytes'] / (1024**3)
                    ))
                
                return platforms
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    def _add_system_routes(self, app: FastAPI):
        """Add system status and health routes"""
        
        @app.get("/api/status", response_model=SystemStatusResponse)
        async def get_system_status():
            """Get overall system status"""
            try:
                uptime = time.time() - self.start_time
                
                # Check server status (simplified)
                servers = []
                for server_name, server in self.integration.rom_servers.items():
                    servers.append(ServerInfo(
                        name=server_name,
                        base_url=server.base_url,
                        status="unknown",  # Would need actual health check
                        platforms=list(server.platform_paths.keys()),
                        last_check=None
                    ))
                
                return SystemStatusResponse(
                    status="running",
                    cache_manager="active",
                    file_watcher="active" if self.integration.observer.is_alive() else "inactive",
                    servers=servers,
                    uptime_seconds=uptime,
                    version="0.1.0"
                )
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/health")
        async def health_check():
            """Simple health check endpoint"""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    
    def _add_web_routes(self, app: FastAPI):
        """Add web UI routes"""
        
        if not self.templates:
            return
        
        @app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Main dashboard page"""
            stats = self.cache_manager.get_cache_stats()
            return self.templates.TemplateResponse(
                "dashboard.html",
                {"request": request, "stats": stats}
            )
        
        @app.get("/browse", response_class=HTMLResponse)
        async def browse_roms(request: Request):
            """ROM browser page"""
            return self.templates.TemplateResponse(
                "browse.html",
                {"request": request}
            )
        
        @app.get("/settings", response_class=HTMLResponse)
        async def settings(request: Request):
            """Settings page"""
            config = self.cache_manager.config
            return self.templates.TemplateResponse(
                "settings.html",
                {"request": request, "config": config}
            )
    
    async def _download_rom_task(self, rom_id: str):
        """Background task to download ROM"""
        try:
            # Extract platform and filename from ROM ID
            platform = rom_id.split('_')[0]
            # This is simplified - in reality we'd need to look up the filename
            filename = f"{rom_id}.rom"
            
            # Find download URL (simplified)
            download_url = self.integration._build_download_url(platform, filename)
            
            if download_url:
                # Download using cache manager
                success = self.cache_manager.add_to_cache(
                    rom_id=rom_id,
                    source_url=download_url,
                    filename=filename,
                    platform=platform
                )
                
                self.downloading_roms[rom_id] = "completed" if success else "error"
            else:
                self.downloading_roms[rom_id] = "error"
                
        except Exception as e:
            self.downloading_roms[rom_id] = "error"
        
        # Clean up status after a while
        await asyncio.sleep(60)  # Keep status for 1 minute
        self.downloading_roms.pop(rom_id, None)

def create_app(cache_manager: ROMCacheManager, integration: EmulationStationIntegration) -> FastAPI:
    """Factory function to create FastAPI app"""
    api = ROMCacheAPI(cache_manager, integration)
    return api.app

# Development server
if __name__ == "__main__":
    # This would be used for development/testing
    from ..cache.engine import CacheConfig
    
    # Create dummy instances
    config = CacheConfig()
    cache_manager = ROMCacheManager("/tmp/test_cache", config)
    
    # Create mock integration
    rom_server = ROMServer(name="test", base_url="http://localhost:8080")
    integration = EmulationStationIntegration(
        cache_manager=cache_manager,
        es_roms_dir="/tmp/roms",
        rom_servers=[rom_server]
    )
    
    app = create_app(cache_manager, integration)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)