#!/bin/bash
set -e

# Docker entrypoint script for Smart ROM Cache Manager
# Handles initialization, configuration, and startup

echo "🚀 Starting Smart ROM Cache Manager"
echo "Version: ${APP_VERSION:-development}"
echo "Environment: ${ENVIRONMENT:-production}"

# Create required directories
mkdir -p /app/cache /app/config /app/logs /app/roms

# Set default configuration if not provided
export CACHE_SIZE_GB=${CACHE_SIZE_GB:-20}
export CLEANUP_THRESHOLD=${CLEANUP_THRESHOLD:-0.8}
export MIN_FREE_SPACE_GB=${MIN_FREE_SPACE_GB:-2}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

# Generate configuration file if it doesn't exist
CONFIG_FILE="/app/config/config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "📝 Generating configuration file..."
    cat > "$CONFIG_FILE" << EOF
# Smart ROM Cache Manager Configuration
cache:
  max_size_gb: ${CACHE_SIZE_GB}
  cleanup_threshold: ${CLEANUP_THRESHOLD}
  min_free_space_gb: ${MIN_FREE_SPACE_GB}
  favorite_protection: true
  
  # Platform priorities (higher = keep longer)
  platforms_priority:
    nes: 10
    snes: 10
    gb: 10
    gbc: 10
    gba: 9
    genesis: 8
    n64: 7
    psx: 6
    ps2: 5
    gamecube: 4
    wii: 3
    xbox: 2
    ps3: 1
    xbox360: 1

servers:
  - name: "default_server"
    base_url: "${ROM_SERVER_URL:-http://localhost:8080}"
    platform_paths:
      nes: "nes"
      snes: "snes"
      n64: "n64"
      psx: "psx"
      ps2: "ps2"
      gamecube: "gamecube"
      wii: "wii"
      ps3: "ps3"
      xbox360: "xbox360"

emulationstation:
  roms_directory: "/app/roms"
  config_directory: "/app/config"
  
logging:
  level: "${LOG_LEVEL}"
  file: "/app/logs/rom-cache.log"
  max_size_mb: 100
  backup_count: 5

web:
  host: "0.0.0.0"
  port: 8000
  workers: ${WORKERS:-1}
EOF
    echo "✅ Configuration file created"
fi

# Wait for dependencies if specified
if [ -n "$WAIT_FOR_SERVICES" ]; then
    echo "⏳ Waiting for dependencies: $WAIT_FOR_SERVICES"
    for service in $(echo $WAIT_FOR_SERVICES | tr ',' ' '); do
        echo "  Waiting for $service..."
        host=$(echo $service | cut -d: -f1)
        port=$(echo $service | cut -d: -f2)
        
        timeout 60 bash -c "until nc -z $host $port; do sleep 1; done"
        if [ $? -eq 0 ]; then
            echo "  ✅ $service is ready"
        else
            echo "  ❌ $service failed to become ready"
            exit 1
        fi
    done
fi

# Run database migrations if needed
if [ -n "$DATABASE_URL" ] && [ "$SKIP_MIGRATIONS" != "true" ]; then
    echo "🔄 Running database migrations..."
    python -c "
from src.utils.database import init_database
init_database('$DATABASE_URL')
print('✅ Database migrations completed')
" || echo "⚠️  Database migrations failed (continuing anyway)"
fi

# Validate configuration
echo "🔍 Validating configuration..."
python -c "
import yaml
import sys
try:
    with open('/app/config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    print('✅ Configuration is valid')
except Exception as e:
    print(f'❌ Configuration error: {e}')
    sys.exit(1)
"

# Set up log rotation
if command -v logrotate >/dev/null 2>&1; then
    cat > /tmp/logrotate.conf << EOF
/app/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    copytruncate
}
EOF
fi

# Health check function
health_check() {
    echo "🏥 Starting health check monitoring..."
    while true; do
        sleep 30
        if ! curl -f http://localhost:8000/api/health >/dev/null 2>&1; then
            echo "⚠️  Health check failed"
        fi
    done &
}

# Signal handlers for graceful shutdown
shutdown_handler() {
    echo "🛑 Received shutdown signal"
    echo "📊 Final statistics:"
    curl -s http://localhost:8000/api/cache/stats | python -m json.tool || true
    echo "👋 Goodbye!"
    exit 0
}

trap shutdown_handler SIGTERM SIGINT

# Start background health monitoring (except in test mode)
if [ "$ENVIRONMENT" != "test" ]; then
    health_check
fi

# Show startup info
echo "📁 Cache directory: /app/cache"
echo "📁 ROMs directory: /app/roms" 
echo "📁 Config directory: /app/config"
echo "📁 Logs directory: /app/logs"
echo "🌐 Web interface: http://localhost:8000"
echo "📚 API docs: http://localhost:8000/api/docs"
echo "⏹️  Send SIGTERM or SIGINT to stop gracefully"

# Execute the main command
echo "🎯 Starting main application..."
exec "$@"