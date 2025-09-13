#!/bin/bash
# Build performance monitoring script
# This script helps monitor and optimize Docker build performance

set -e

PLATFORM=${1:-"linux/amd64"}
IMAGE_NAME=${2:-"meshinfo-lite-test"}

echo "🚀 Starting optimized build for platform: $PLATFORM"
echo "📊 Monitoring build performance..."

start_time=$(date +%s)

# Build with BuildKit and detailed progress
DOCKER_BUILDKIT=1 docker build \
  --platform "$PLATFORM" \
  --progress=plain \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --tag "$IMAGE_NAME" \
  . 2>&1 | tee "build-$PLATFORM.log"

end_time=$(date +%s)
duration=$((end_time - start_time))

echo "✅ Build completed!"
echo "⏱️  Total build time: ${duration} seconds"
echo "📋 Build log saved to: build-$PLATFORM.log"

# Extract and display key metrics
echo ""
echo "📈 Build Performance Summary:"
echo "=========================================="
echo "Platform: $PLATFORM"
echo "Duration: ${duration}s"
echo "Log file: build-$PLATFORM.log"

# Check for common optimization opportunities
if grep -q "COPY.*requirements.txt" "build-$PLATFORM.log"; then
    echo "✅ Requirements cached properly"
else
    echo "⚠️  Requirements caching could be improved"
fi

if grep -q "piwheels" "build-$PLATFORM.log"; then
    echo "✅ Using piwheels for ARM64 optimization"
fi

if grep -q "conda" "build-$PLATFORM.log"; then
    echo "⚠️  Still using conda - consider switching to pip"
fi

echo "=========================================="