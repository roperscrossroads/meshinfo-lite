#!/bin/bash
# Setup script to download SRTM data for LOS functionality

echo "Setting up SRTM elevation data for LOS functionality..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but not found"
    exit 1
fi

# Install boto3 if not available
if ! python3 -c "import boto3" 2>/dev/null; then
    echo "Installing boto3..."
    pip3 install boto3
fi

# Run the SRTM download script
echo "Downloading SRTM elevation data..."
python3 scripts/download_srtm_data.py

echo "SRTM setup complete!"
echo "You can now restart your containers to enable LOS functionality."
