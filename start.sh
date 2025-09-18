#!/bin/bash
# MeshInfo-Lite Startup Script
# Automatically sets up database privileges and starts the application

set -e

echo "=== MeshInfo-Lite Container Startup ==="

# Function to run database setup with error handling
run_database_setup() {
    echo "Setting up database privileges..."
    
    # Try to run the Python setup script in startup mode (non-failing)
    if python3 setup_docker.py --startup; then
        echo "✓ Database privilege setup completed successfully"
        return 0
    else
        echo "⚠ Database privilege setup failed, but continuing..."
        echo "  The application may have limited functionality until privileges are granted"
        echo "  You can manually run: python setup_docker.py"
        return 1
    fi
}

# Function to wait for config file
wait_for_config() {
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if [ -f "config.ini" ]; then
            echo "✓ Configuration file found"
            return 0
        fi
        
        echo "Waiting for config.ini (attempt $attempt/$max_attempts)..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "⚠ config.ini not found after $max_attempts attempts"
    echo "  The application will start but may not function correctly"
    echo "  Please ensure config.ini is mounted correctly"
    return 1
}

# Wait for configuration
wait_for_config

# Try to set up database privileges (non-blocking)
if run_database_setup; then
    echo "Database setup completed successfully"
else
    echo "Database setup encountered issues, but continuing startup"
fi

echo "Starting MeshInfo-Lite application..."
echo "=== Application Startup ==="

# Run the original startup sequence
exec ./run.sh