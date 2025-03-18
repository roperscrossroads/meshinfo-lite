#!/usr/bin/env python3

import datetime
from datetime import timedelta
import requests
import time
from math import asin, cos, radians, sin, sqrt
import string
import random
import bcrypt
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import configparser
import logging


def distance_between_two_points(lat1, lon1, lat2, lon2):
    """
    Calculate the Haversine distance between two latitude/longitude points.
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    radius = 6371  # Radius of Earth in kilometers
    return radius * c


def calculate_distance_between_nodes(node1, node2):
    """Calculate the distance between two nodes, ensuring data integrity."""
    if not node1 or not node2:
        return None
    if not node1.get("position") or not node2.get("position"):
        return None
    if any(
        key not in node1["position"] or key not in node2["position"]
        or node1["position"][key] is None or node2["position"][key] is None
        for key in ["latitude_i", "longitude_i"]
    ):
        return None
    return round(
        distance_between_two_points(
            node1["position"]["latitude_i"] / 10000000,
            node1["position"]["longitude_i"] / 10000000,
            node2["position"]["latitude_i"] / 10000000,
            node2["position"]["longitude_i"] / 10000000,
        ),
        2,
    )


def convert_node_id_from_int_to_hex(node_id: int):
    """Convert an integer node ID to a hexadecimal string."""
    return f"{node_id:08x}"


def convert_node_id_from_hex_to_int(node_id: str):
    """Convert a hexadecimal node ID to an integer."""
    return int(node_id.lstrip("!"), 16)


def days_since_datetime(dt):
    """Return the number of days since a given UTC datetime."""
    now = datetime.datetime.now(datetime.timezone.utc)
    if isinstance(dt, str):
        dt = datetime.datetime.fromisoformat(dt)
    return (now - dt).days


def geocode_position(api_key: str, latitude: float, longitude: float):
    """Retrieve geolocation data using an API."""
    if latitude is None or longitude is None:
        return None
    url = f"https://geocode.maps.co/reverse" + \
        f"?lat={latitude}&lon={longitude}&api_key={api_key}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None


def latlon_to_grid(lat, lon):
    """Convert latitude and longitude to Maidenhead grid locator."""
    lon += 180
    lat += 90
    return (
        chr(int(lon / 20) + ord("A"))
        + chr(int(lat / 10) + ord("A"))
        + str(int((lon % 20) / 2))
        + str(int((lat % 10) / 1))
        + chr(int((lon % 2) * 12) + ord("a"))
        + chr(int((lat % 1) * 24) + ord("a"))
    )


def graph_icon(name):
    """Return the appropriate icon for a given node name."""
    icons = {
        "qth": "house",
        "home": "house",
        "base": "house",
        "main": "house",
        "mobile": "car",
        " hs": "tower",
        "router": "tower",
        "edc": "heltec",
        "mqtt": "computer",
        "bridge": "computer",
        "gateway": "computer",
        "meshtastic": "meshtastic",
        "bbs": "bbs",
        "narf": "narf"
    }
    for key, icon in icons.items():
        if key in name.lower():
            return f"/images/icons/{icon}.png"
    return "/images/icons/radio.png"


def filter_dict(data, whitelist):
    """Recursively filter a dictionary to only include whitelisted keys."""
    if isinstance(data, dict):
        return {
            key: filter_dict(data[key], whitelist[key])
            if isinstance(data[key], (dict, list))
            else data[key]
            for key in whitelist if key in data
        }
    if isinstance(data, list):
        return [
            filter_dict(item, whitelist) if isinstance(item, dict) else item
            for item in data
        ]
    return data


def time_since_bak(epoch_timestamp):
    """Convert an epoch timestamp to a human-readable duration."""
    elapsed_seconds = int(time.time()) - epoch_timestamp
    if elapsed_seconds < 0:
        return "The timestamp is in the future!"
    time_units = [
        ("day", elapsed_seconds // 86400),
        ("hour", (elapsed_seconds % 86400) // 3600),
        ("minute", (elapsed_seconds % 3600) // 60),
        ("second", elapsed_seconds % 60),
    ]
    return ", ".join(
        f"{int(value)} {unit}{'s' if value > 1 else ''}"
        for unit, value in time_units if value > 0
    ) or "Just now"


def time_since(epoch_timestamp):
    diff = epoch_timestamp - time.time()  # Calculate the difference
    sign = "-" if diff < 0 else ""
    diff = abs(diff)  # Work with absolute difference
    td = timedelta(seconds=diff)
    formatted_diff = f"{sign}{td.seconds // 3600:02}:{(td.seconds % 3600) // 60:02}:{td.seconds % 60:02}"
    return formatted_diff


def active_nodes(nodes):
    return {
        node: dict(nodes[node])
        for node in nodes if nodes[node]["active"]
    }


def get_owner_nodes(nodes, owner):
    return {
        node: dict(nodes[node])
        for node in nodes if nodes[node]["owner"] == owner
    }


def generate_random_code(length=6):
    characters = string.ascii_letters
    return ''.join(random.choices(characters, k=length))


def generate_random_otp(length=4):
    characters = string.digits
    return ''.join(random.choices(characters, k=length))


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode(), salt)
    return hashed_password


def check_password(password: str, hashed_password: str) -> bool:
    """Checks if a password matches its hashed version."""
    return bcrypt.checkpw(password.encode(), hashed_password)


def send_email(recipient_email, subject, message):
    config = configparser.ConfigParser()
    config.read('config.ini')
    try:
        # Set up the SMTP server (Gmail SMTP)
        smtp_server = config["smtp"]["server"]
        smtp_port = int(config["smtp"]["port"])
        sender_email = config["smtp"]["email"]
        sender_password = config["smtp"]["password"]

        # Create message
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        # Connect to SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection
        server.login(sender_email, sender_password)  # Login to your email
        server.send_message(msg)  # Send email
        server.quit()  # Close connection

        logging.info("Email sent successfully!")

    except Exception as e:
        logging.error(str(e))
