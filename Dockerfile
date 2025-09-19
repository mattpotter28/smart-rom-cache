# Multi-stage build for smaller production image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r romcache && useradd -r -g romcache romcache

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=romcache:romcache src/ ./src/
COPY --chown=romcache:romcache main.py .
COPY --chown=romcache:romcache docker/entrypoint.sh /entrypoint.sh

# Create necessary directories
RUN mkdir -p /app/cache /app/config /app/logs /app/roms && \
    chown -R romcache:romcache /app

# Make entrypoint executable
RUN chmod +x /entrypoint.sh

# Switch to non-root user
USER romcache

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Expose port
EXPOSE 8000

# Set default environment variables
ENV PYTHONPATH=/app \
    CACHE_SIZE_GB=20 \
    CLEANUP_THRESHOLD=0.8 \
    MIN_FREE_SPACE_GB=2 \
    LOG_LEVEL=INFO \
    WORKERS=1

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]