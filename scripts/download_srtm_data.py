#!/usr/bin/env python3
"""
SRTM Elevation Data Downloader for MeshInfo-Lite

This script downloads SRTM (Shuttle Radar Topography Mission) elevation data
for use with the Line of Sight (LOS) terrain analysis feature in MeshInfo-Lite.

The script reads configuration from config.ini to determine the geographic region
for which to download elevation data.

Usage:
    python scripts/download_srtm_data.py
    
Configuration:
    Set the [srtm] section in config.ini with your mesh region coordinates:
    
    [srtm]
    min_latitude=32
    max_latitude=35  
    min_longitude=-84
    max_longitude=-80
"""

import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from botocore import UNSIGNED
from botocore.client import Config
import os
import sys
import configparser


def download_file_from_s3(bucket_name, file_key, download_path):
    """
    Downloads a file from an S3 bucket.

    Args:
        bucket_name (str): Name of the S3 bucket.
        file_key (str): Key (path) of the file in the S3 bucket.
        download_path (str): Local path where the file will be downloaded.
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create an S3 client
        s3_client = boto3.client(
            's3',
            endpoint_url='https://opentopography.s3.sdsc.edu',
            config=Config(signature_version=UNSIGNED)
        )

        # Check if file already exists
        if os.path.exists(download_path):
            print(f"File '{file_key}' already exists at '{download_path}'. Skipping download.")
            return True

        # Download the file
        print(f"Downloading '{file_key}'...")
        s3_client.download_file(bucket_name, file_key, download_path)
        print(f"File '{file_key}' downloaded successfully to '{download_path}'.")
        return True
        
    except FileNotFoundError:
        print(f"Error: The specified download path '{download_path}' is invalid.")
        return False
    except NoCredentialsError:
        print("Error: AWS credentials not found.")
        return False
    except PartialCredentialsError:
        print("Error: Incomplete AWS credentials provided.")
        return False
    except Exception as e:
        print(f"Warning: Could not download '{file_key}': {e}")
        return False


def load_config():
    """
    Load configuration from config.ini file.
    
    Returns:
        configparser.ConfigParser: Loaded configuration
    """
    config = configparser.ConfigParser()
    
    # Try to read config.ini from current directory or parent directory
    config_paths = ['config.ini', '../config.ini']
    config_found = False
    
    for path in config_paths:
        if os.path.exists(path):
            config.read(path)
            config_found = True
            print(f"Loaded configuration from: {path}")
            break
    
    if not config_found:
        print("Error: config.ini not found in current directory or parent directory.")
        print("Please ensure config.ini exists and contains [srtm] section with coordinates.")
        sys.exit(1)
    
    return config


def validate_coordinates(min_lat, max_lat, min_lon, max_lon):
    """
    Validate coordinate ranges.
    
    Args:
        min_lat, max_lat, min_lon, max_lon: Coordinate boundaries
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not (-90 <= min_lat <= max_lat <= 90):
        print(f"Error: Invalid latitude range {min_lat} to {max_lat}. Must be between -90 and 90.")
        return False
        
    if not (-180 <= min_lon <= max_lon <= 180):
        print(f"Error: Invalid longitude range {min_lon} to {max_lon}. Must be between -180 and 180.")
        return False
        
    if (max_lat - min_lat) > 10 or (max_lon - min_lon) > 10:
        print(f"Warning: Large coordinate range may result in many files being downloaded.")
        print(f"Latitude range: {max_lat - min_lat}°, Longitude range: {max_lon - min_lon}°")
        
    return True


def main():
    """
    Main function to download SRTM data based on configuration.
    """
    print("=== SRTM Elevation Data Downloader for MeshInfo-Lite ===")
    print()
    
    # Load configuration
    config = load_config()
    
    # Check if srtm section exists
    if 'srtm' not in config:
        print("Error: [srtm] section not found in config.ini")
        print("Please add the following section to your config.ini:")
        print()
        print("[srtm]")
        print("min_latitude=32")
        print("max_latitude=35")
        print("min_longitude=-84")
        print("max_longitude=-80")
        sys.exit(1)
    
    # Read coordinate bounds from config
    try:
        min_latitude = int(config['srtm']['min_latitude'])
        max_latitude = int(config['srtm']['max_latitude'])
        min_longitude = int(config['srtm']['min_longitude'])
        max_longitude = int(config['srtm']['max_longitude'])
    except (KeyError, ValueError) as e:
        print(f"Error reading SRTM coordinates from config: {e}")
        print("Please ensure all coordinate values (min_latitude, max_latitude, min_longitude, max_longitude) are specified as integers.")
        sys.exit(1)
    
    # Validate coordinates
    if not validate_coordinates(min_latitude, max_latitude, min_longitude, max_longitude):
        sys.exit(1)
    
    print(f"Region to download:")
    print(f"  Latitude: {min_latitude}° to {max_latitude}°")
    print(f"  Longitude: {min_longitude}° to {max_longitude}°")
    print()
    
    # Create srtm_data directory
    directory = "srtm_data"
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")
    
    # Calculate total tiles and download
    total_tiles = (max_latitude - min_latitude + 1) * (max_longitude - min_longitude + 1)
    downloaded = 0
    skipped = 0
    failed = 0
    
    print(f"Downloading {total_tiles} SRTM tiles...")
    print()
    
    for lat in range(min_latitude, max_latitude + 1):
        for lon in range(min_longitude, max_longitude + 1):
            # Generate tile name in SRTM format
            lat_prefix = "S" if lat < 0 else "N"
            lon_prefix = "W" if lon < 0 else "E"
            tile_name = f"{lat_prefix}{abs(lat):02d}{lon_prefix}{abs(lon):03d}.tif"
            
            download_path = os.path.join(directory, tile_name)
            
            # Check if file already exists
            if os.path.exists(download_path):
                skipped += 1
                continue
            
            # Download the file
            success = download_file_from_s3(
                "raster",
                f"SRTM_GL1/SRTM_GL1_srtm/{tile_name}",
                download_path
            )
            
            if success:
                downloaded += 1
            else:
                failed += 1
    
    print()
    print("=== Download Summary ===")
    print(f"Total tiles: {total_tiles}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (already exist): {skipped}")
    print(f"Failed: {failed}")
    
    if downloaded > 0 or skipped > 0:
        print()
        print("✅ SRTM data is ready!")
        print("The Line of Sight (LOS) feature should now work for nodes with position data.")
        print("Restart MeshInfo-Lite to load the elevation data.")
    
    if failed > 0:
        print()
        print("⚠️  Some tiles failed to download. This may be normal if SRTM data")
        print("   is not available for all coordinates in your region (e.g., over water).")


if __name__ == "__main__":
    main()