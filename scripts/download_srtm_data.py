import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from botocore import UNSIGNED
from botocore.client import Config
import os


def download_file_from_s3(bucket_name, file_key, download_path):
    """
    Downloads a file from an S3 bucket.

    Args:
        bucket_name (str): Name of the S3 bucket.
        file_key (str): Key (path) of the file in the S3 bucket.
        download_path (str): Local path where the file will be downloaded.
    """
    try:
        # Create an S3 client
        s3_client = boto3.client(
            's3',
            endpoint_url='https://opentopography.s3.sdsc.edu',
            config=Config(signature_version=UNSIGNED)
        )

        # Download the file
        s3_client.download_file(bucket_name, file_key, download_path)
        print(f"File '{file_key}' downloaded successfully to '{download_path}'.")
    except FileNotFoundError:
        print(f"Error: The specified download path '{download_path}' is invalid.")
    except NoCredentialsError:
        print("Error: AWS credentials not found.")
    except PartialCredentialsError:
        print("Error: Incomplete AWS credentials provided.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


# Define the latitude and longitude range for South Africa
min_latitude = -35  # Southernmost point
max_latitude = -22  # Northernmost point
min_longitude = 16  # Westernmost point
max_longitude = 33  # Easternmost point

# Open a file to write the tile names
directory = "srtm_data"
if not os.path.exists(directory):
    os.makedirs(directory)
for lat in range(min_latitude, max_latitude + 1):
    for lon in range(min_longitude, max_longitude + 1):
        lat_prefix = "S" if lat < 0 else "N"
        lon_prefix = "W" if lon < 0 else "E"
        tile_name = f"{lat_prefix}{abs(lat):02d}{lon_prefix}{abs(lon):03d}.tif"
        download_file_from_s3(
            "raster",
            f"SRTM_GL1/SRTM_GL1_srtm/{tile_name}",
            f"{directory}/{tile_name}"
        )
