# trunk-ignore-all(checkov/CKV_DOCKER_3)
FROM python:3.13.3-slim-bookworm

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
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system app && \
    useradd --system --gid app --home-dir /app --create-home app

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
ARG TARGETPLATFORM
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
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
    $([ "$(uname -m)" = "aarch64" ] && echo "curl") \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN fc-cache -fv

# Architecture-specific rasterio installation
ENV GDAL_CONFIG=/usr/bin/gdal-config

# For ARM64: Install conda/mamba and use conda-forge for rasterio
RUN if [ "$(uname -m)" = "aarch64" ]; then \
    echo "Installing conda and rasterio for ARM64"; \
    curl -L -O https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh && \
    bash Miniforge3-Linux-aarch64.sh -b -p /opt/conda && \
    rm Miniforge3-Linux-aarch64.sh && \
    /opt/conda/bin/mamba install -c conda-forge rasterio -y; \
    fi

# Update PATH to include conda if installed
ENV PATH="/opt/conda/bin:${PATH}"

COPY requirements.txt banner run.sh ./

# Upgrade pip and install packages
RUN pip install --upgrade pip setuptools wheel

# Install requirements with platform-specific optimizations
# Detect ARM64 by checking uname since TARGETPLATFORM may not be set
RUN if [ "$(uname -m)" = "aarch64" ]; then \
    echo "ARM64 detected, using conda for heavy packages and piwheels for others"; \
    # Install heavy packages via conda for faster ARM64 builds \
    /opt/conda/bin/mamba install -c conda-forge matplotlib scipy pandas Pillow shapely cryptography -y; \
    # Filter out conda-installed packages from requirements for pip \
    grep -v -E "^(rasterio|matplotlib|scipy|pandas|Pillow|shapely|cryptography)" requirements.txt > requirements_filtered.txt || echo "" > requirements_filtered.txt; \
    su app -c "pip install --no-cache-dir --user --extra-index-url https://www.piwheels.org/simple -r requirements_filtered.txt"; \
    else \
    echo "Non-ARM64 detected, using standard pip install"; \
    # Standard install for non-ARM64 \
    su app -c "pip install --no-cache-dir --user -r requirements.txt"; \
    fi

# Ensure pytz is installed for timezone support (critical for time display)
RUN su app -c "pip install --no-cache-dir --user pytz==2025.2"

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
