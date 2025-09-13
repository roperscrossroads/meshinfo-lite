# trunk-ignore-all(checkov/CKV_DOCKER_3)
FROM python:3.13.3-slim-bookworm AS base

LABEL org.opencontainers.image.source=https://github.com/agessaman/meshinfo-lite
LABEL org.opencontainers.image.description="Realtime web UI to run against a Meshtastic regional or private mesh network."

ENV MQTT_TLS=false
ENV PYTHONUNBUFFERED=1 \
    # Set standard locations
    PATH="/app/.local/bin:${PATH}" \
    # Consistent port for the app
    APP_PORT=8000 \
    # Optimize pip for faster builds
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Speed up pip installations
    PIP_DEFAULT_TIMEOUT=100

RUN groupadd --system app && \
    useradd --system --gid app --home-dir /app --create-home app

# Set the working directory in the container
WORKDIR /app

# Install system dependencies in a single layer with better caching
FROM base AS dependencies
ARG TARGETPLATFORM
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    curl \
    libexpat1 \
    libcairo2 \
    pkg-config \
    fonts-symbola \
    fontconfig \
    freetype2-demos \
    libgdal-dev \
    gdal-bin \
    libgeos-dev \
    libproj-dev \
    proj-bin \
    default-mysql-client \
    && fc-cache -fv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Architecture-specific optimizations
ENV GDAL_CONFIG=/usr/bin/gdal-config

# Copy requirements first for better Docker layer caching
COPY requirements.txt requirements-rasterio.txt ./

# Install requirements with optimized strategy for each architecture
RUN if [ "$(uname -m)" = "aarch64" ]; then \
    echo "ARM64 detected, using mamba for rasterio (fastest pre-compiled option)"; \
    # Install miniforge (includes mamba) - mambaforge is deprecated \
    curl -fsSL -o miniforge.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh && \
    echo "Downloaded miniforge installer, size: $(stat -c%s miniforge.sh) bytes" && \
    bash miniforge.sh -b -p /opt/miniforge && \
    rm miniforge.sh && \
    # Use mamba to install rasterio (much faster than compiling) \
    /opt/miniforge/bin/mamba install -c conda-forge rasterio=1.4.3 -y && \
    # Install all other packages via pip with piwheels for speed \
    su app -c "pip install --no-cache-dir --user --extra-index-url https://www.piwheels.org/simple -r requirements.txt"; \
    else \
    echo "Non-ARM64 detected, using standard pip install for all packages"; \
    # Standard install for non-ARM64 (includes rasterio) \
    su app -c "pip install --no-cache-dir --user -r requirements.txt -r requirements-rasterio.txt"; \
    fi

# Ensure pytz is installed for timezone support (critical for time display)
RUN su app -c "pip install --no-cache-dir --user pytz==2025.2"

# Application stage
FROM dependencies AS application

# Copy application files (better layer caching by copying requirements first)
COPY --chown=app:app banner run.sh ./
COPY --chown=app:app *.py ./
COPY --chown=app:app *.sh ./
COPY --chown=app:app www  ./www
COPY --chown=app:app templates ./templates
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app scripts ./scripts

# Create runtime_cache directory with proper permissions
RUN mkdir -p /app/runtime_cache && \
    chown -R app:app /app/runtime_cache && \
    chmod 777 /app/runtime_cache

HEALTHCHECK NONE

RUN chmod +x run.sh
RUN chmod +x *.sh

# Ensure cache directory permissions persist
USER root
RUN echo '#!/bin/bash' > /app/fix_cache.sh && \
    echo 'mkdir -p /app/runtime_cache' >> /app/fix_cache.sh && \
    echo 'chmod 777 /app/runtime_cache' >> /app/fix_cache.sh && \
    echo 'chown -R app:app /app/runtime_cache' >> /app/fix_cache.sh && \
    echo 'exec su app -c "./run.sh"' >> /app/fix_cache.sh && \
    chmod +x /app/fix_cache.sh

USER root

EXPOSE ${APP_PORT}

# Run with cache fix wrapper to ensure permissions
CMD ["/app/fix_cache.sh"]
