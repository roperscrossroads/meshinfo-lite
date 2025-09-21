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
    $([ "$TARGETPLATFORM" = "linux/arm64" ] && echo "curl") \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN fc-cache -fv

# Architecture-specific rasterio installation
ENV GDAL_CONFIG=/usr/bin/gdal-config

# Install conda/mamba for both architectures for consistency
RUN if [ "$(uname -m)" = "aarch64" ]; then \
    echo "ARM64 detected, installing miniforge"; \
    curl -fsSL -o miniforge.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh; \
    else \
    echo "x86-64 detected, installing miniforge"; \
    curl -fsSL -o miniforge.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh; \
    fi && \
    bash miniforge.sh -b -p /opt/conda && \
    rm miniforge.sh && \
    /opt/conda/bin/mamba install -c conda-forge rasterio -y

# Update PATH to include conda for both architectures
ENV PATH="/opt/conda/bin:${PATH}"

COPY requirements.txt banner run.sh ./

# Upgrade pip and install packages
RUN pip install --upgrade pip setuptools wheel

# Install requirements, excluding rasterio (already installed via conda)
# Filter out rasterio since it's installed via conda for both architectures
RUN grep -v "^rasterio" requirements.txt > requirements_filtered.txt || echo "" > requirements_filtered.txt

# Use piwheels for ARM64 builds for faster installation, standard pip for x86-64
RUN if [ "$(uname -m)" = "aarch64" ]; then \
    echo "ARM64: Using piwheels for faster package installation"; \
    su app -c "pip install --no-cache-dir --user --extra-index-url https://www.piwheels.org/simple -r requirements_filtered.txt"; \
    else \
    echo "x86-64: Using standard pip installation"; \
    su app -c "pip install --no-cache-dir --user -r requirements_filtered.txt"; \
    fi

COPY --chown=app:app banner run.sh ./
COPY --chown=app:app *.py ./
COPY --chown=app:app *.sh ./
COPY --chown=app:app www  ./www
COPY --chown=app:app templates ./templates
COPY --chown=app:app migrations ./migrations

HEALTHCHECK NONE

RUN chmod +x run.sh
RUN chmod +x *.sh

USER app

EXPOSE ${APP_PORT}

CMD ["./run.sh"]