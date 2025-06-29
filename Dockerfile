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
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
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
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN fc-cache -fv

COPY requirements.txt banner run.sh ./

# Upgrade pip and install all packages with optimizations
RUN pip install --upgrade pip setuptools wheel

# Architecture-specific optimizations for rasterio
ARG TARGETPLATFORM
ENV GDAL_CONFIG=/usr/bin/gdal-config

# For ARM64, install build tools to speed up compilation
RUN if [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*; \
    fi

RUN su app -c "pip install --no-cache-dir --user -r requirements.txt"

COPY --chown=app:app banner run.sh ./
COPY --chown=app:app *.py ./
COPY --chown=app:app www  ./www
COPY --chown=app:app templates ./templates
COPY --chown=app:app migrations ./migrations

HEALTHCHECK NONE

RUN chmod +x run.sh

USER app

EXPOSE ${APP_PORT}

CMD ["./run.sh"]