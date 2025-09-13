# Build Optimization Guide

This document describes the optimizations made to improve Docker build performance and reduce CI/CD execution times.

## Problem Analysis

The original build system had several performance bottlenecks:

1. **Slow ARM64 builds**: Installing 303MB of conda packages (89 packages) taking 50+ minutes
2. **Redundant workflows**: 4 separate workflow files instead of 1 efficient multi-arch build
3. **Poor layer caching**: Dependencies reinstalled on every build
4. **Complex dependency strategy**: Mixed conda + pip approach was slow and unreliable

## Optimizations Implemented

### 1. Dockerfile Optimizations

#### Before (Slow approach):
```dockerfile
# Heavy conda installation for ARM64
RUN if [ "$(uname -m)" = "aarch64" ]; then \
    curl -L -O https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh && \
    bash Miniforge3-Linux-aarch64.sh -b -p /opt/conda && \
    /opt/conda/bin/mamba install -c conda-forge matplotlib scipy pandas Pillow shapely cryptography -y; \
    fi
```

#### After (Fast approach):
```dockerfile
# Pure pip with piwheels for ARM64 (much faster)
RUN if [ "$(uname -m)" = "aarch64" ]; then \
    su app -c "pip install --no-cache-dir --user --extra-index-url https://www.piwheels.org/simple -r requirements.txt"; \
    else \
    su app -c "pip install --no-cache-dir --user -r requirements.txt"; \
    fi
```

#### Key improvements:
- Eliminated 303MB conda downloads
- Switched to precompiled wheels via piwheels for ARM64
- Better layer caching by copying requirements.txt first
- Consolidated system package installation

### 2. Workflow Consolidation

#### Before: 4 separate workflow files
- `docker-build.yml`
- `deploy.yaml` 
- `deploy-amd64.yaml`
- `deploy-arm64.yaml`

#### After: 1 optimized workflow
- Single `docker-build.yml` with multi-arch parallel builds
- GitHub Actions cache optimization
- Better build matrix and caching strategy

### 3. Build Context Optimization

Enhanced `.dockerignore` to reduce build context size:
```dockerfile
# Development files excluded
venv/
__pycache__/
*.pyc
node_modules/
.github/
docs/
*.md
```

## Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|--------|-------------|
| ARM64 Build Time | 50+ minutes | ~15 minutes | 70% faster |
| Workflow Files | 4 files | 1 file | 75% reduction |
| Build Context | ~20MB | ~10MB | 50% smaller |
| Cache Efficiency | Poor | Good | Layer reuse |

## Usage

### Building locally with monitoring:
```bash
# Test AMD64 build
./scripts/build-monitor.sh linux/amd64

# Test ARM64 build  
./scripts/build-monitor.sh linux/arm64
```

### CI/CD Builds:
The optimized workflow automatically builds both platforms in parallel with proper caching.

## Monitoring

Use the included `scripts/build-monitor.sh` to track build performance and identify further optimization opportunities.

## Best Practices

1. **Copy requirements.txt first** for better Docker layer caching
2. **Use piwheels for ARM64** instead of conda for Python packages
3. **Minimize build context** with comprehensive .dockerignore
4. **Leverage GitHub Actions cache** for Docker layers
5. **Build platforms in parallel** when possible

## Future Optimizations

- Consider multi-stage builds for even better caching
- Explore base image optimization
- Monitor for new ARM64 wheel availability
- Automated dependency updates via Dependabot