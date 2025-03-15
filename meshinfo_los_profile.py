import json
import utils
import os
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import distance
from geopy.distance import geodesic
import logging
import time
import io
import base64


class LOSProfile():
    def __init__(self, nodes={}, node=None):
        self.nodes = nodes
        self.node = node
        self.datasets = []
        directory = "srtm_data"
        try:
            for filename in os.listdir(directory):
                if filename.endswith(".tif"):
                    filepath = os.path.join(directory, filename)
                    dataset = rasterio.open(filepath)
                    self.datasets.append(dataset)
        except FileNotFoundError as e:
            logging.warning("No SRTM data")
            pass

    def calculate_distance_between_coords(self, coord1, coord2):
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        return geodesic((lat1, lon1), (lat2, lon2)).meters

    def read_elevation_from_tifb(self, lat, lon):
        """
        Reads elevation data from preloaded .tif files for a specific
        coordinate.
        """
        for dataset in self.datasets:
            if dataset.bounds.left <= lon <= dataset.bounds.right \
                    and dataset.bounds.bottom <= lat <= dataset.bounds.top:
                # Rasterio expects (lat, lon) as (y, x)
                row, col = dataset.index(lon, lat)

                # Read only the required pixel
                elevation = dataset.read(
                    1,
                    window=((row, row+1), (col, col+1))
                )[0, 0]

                # Check for NoData values
                if elevation == dataset.nodata or np.isnan(elevation):
                    logging.warning(
                        f"Invalid elevation data at ({lat}, {lon})"
                    )
                    return []

                return elevation

        logging.debug(
            f"No elevation data found for coordinates ({lat}, {lon})"
        )
        return []

    def read_elevation_from_tif(self, lat, lon):
        """
        Reads elevation data from SRTM .tif files in the given directory for a
        specific coordinate.
        """
        for dataset in self.datasets:
            if dataset.bounds.left <= lon <= dataset.bounds.right \
                    and dataset.bounds.bottom <= lat <= dataset.bounds.top:
                row, col = dataset.index(lon, lat)
                elevation = dataset.read(1)[row, col]
                return elevation
        logging.warning(
            f"No elevation data found for coordinates ({lat}, {lon})"
        )
        return []

    def generate_los_profile(self, coord1, coord2, resolution=100):
        """
        Generates a line-of-sight profile between two coordinates using SRTM
        data and altitude.
        Uses geodesic distance instead of Euclidean distance.
        """
        lat1, lon1, alt1 = coord1
        lat2, lon2, alt2 = coord2

        # Interpolate points along the line
        latitudes = np.linspace(lat1, lat2, resolution)
        longitudes = np.linspace(lon1, lon2, resolution)

        elevations = []
        for lat, lon in zip(latitudes, longitudes):
            elevation = self.read_elevation_from_tif(lat, lon)
            elevations.append(elevation)

        # Compute accurate geodesic distances from start point
        distances = [
            geodesic((lat1, lon1), (lat, lon)).meters for lat, lon in
            zip(latitudes, longitudes)
        ]

        profile = [elevation for elevation in elevations]
        # Add altitude to elevation for the final profile
        if alt1:
            profile[0] = alt1

        if alt2:
            profile[-1] = alt2
        return distances, profile

    def plot_los_profile(self, distances, profile, label):
        """
        Plots the line-of-sight profile (including altitude) as a solid graph
        and saves it as a PNG image.
        Additionally, plots a direct straight-line path for comparison.
        """
        plt.figure(figsize=(10, 6))
        plt.gca().set_facecolor("cyan")
        plt.margins(x=0, y=0, tight=True)

        # Direct line (interpolated between start and end altitudes)
        direct_line = np.linspace(profile[0], profile[-1], len(profile))

        # Plot the terrain profile
        plt.fill_between(
            distances,
            profile,
            color="brown",
            alpha=1.0,
            label="Terrain Profile"
        )
        plt.plot(
            distances,
            profile,
            color="brown",
            label="Profile Outline"
        )

        # Plot the direct LOS line
        plt.plot(
            distances,
            direct_line,
            color="green",
            linestyle="dashed",
            linewidth=2,
            label="Direct LOS Line"
        )

        plt.xlabel("Distance (meters)")
        plt.ylabel("Elevation + Altitude (meters)")
        plt.title(f"{label}")

        # Save the plot to a BytesIO buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", bbox_inches="tight")

        # Encode image to Base64
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Print Base64 output (or return it from a function)
        return img_base64

    def get_profiles(self):
        profiles = {}
        hexid = utils.convert_node_id_from_int_to_hex(self.node)
        if not self.datasets:
            return profiles
        if hexid not in self.nodes:
            return profiles
        mynode = self.nodes[hexid]
        if "position" not in mynode:
            return profiles
        if "latitude" not in mynode["position"]:
            return profiles
        mylat = mynode["position"]["latitude"]
        mylon = mynode["position"]["longitude"]
        myalt = mynode["position"]["altitude"]
        c = 0
        for node_id in self.nodes:
            node = self.nodes[node_id]
            if node_id == hexid:
                continue
            if "position" not in node:
                continue
            try:
                lat = node["position"]["latitude"]
                lon = node["position"]["longitude"]
                alt = node["position"]["altitude"]
                dist = self.calculate_distance_between_coords(
                    (mylat, mylon),
                    (lat, lon)
                )

                if (dist and dist < 20000):
                    coord1 = (mylat, mylon, myalt)
                    coord2 = (lat, lon, alt)
                    output_path = f"altitude_{c}.png"
                    c += 1
                    lname1 = mynode["long_name"]
                    sname1 = mynode["short_name"]
                    lname2 = node["long_name"]
                    sname2 = node["short_name"]
                    label = f"{lname1} ({sname1}) <=> {lname2} ({sname2})"
                    distances, profile = self.generate_los_profile(
                        coord1,
                        coord2
                    )
                    image = self.plot_los_profile(
                        distances,
                        profile,
                        label
                    )
                    profiles[node_id] = {
                        "image": image,
                        "distance": dist
                    }
            except KeyError as e:
                pass
            except TypeError as e:
                pass
        return profiles


if __name__ == "__main__":
    from meshdata import MeshData
    md = MeshData()
    nodes = md.get_nodes()
    lp = LOSProfile(nodes, 862243760)
    print(lp.get_profiles())
