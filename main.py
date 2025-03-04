import meshinfo_web
import meshinfo_mqtt
import meshinfo_renderer
from meshdata import MeshData
import threading
import logging
import colorlog
import configparser
import sys
import os


#  logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
def setup_logger():
    config = configparser.ConfigParser()
    config.read('config.ini')
    log_level = logging.DEBUG if config["server"]["debug"] == "true" \
        else logging.INFO
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)  # Set to lowest level to capture all logs

    # Create a console handler
    handler = logging.StreamHandler()
    handler.setLevel(log_level)

    # Define a formatter with colors
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )

    # Set the formatter for the handler
    handler.setFormatter(formatter)

    # Avoid duplicate handlers
    if not logger.hasHandlers():
        logger.addHandler(handler)

    return logger


if __name__ == "__main__":
    config_file = "config.ini"

    if not os.path.isfile(config_file):
        print(f"Error: Configuration file '{config_file}' not found!")
        sys.exit(1)

    logger = setup_logger()

    fh = open("banner", "r")
    logger.info(fh.read())
    fh.close()

    try:
        md = MeshData()
        md.setup_database()
    except Exception as e:
        logger.error("Failed to setup database")
        sys.exit(1)

    thread_mqtt = threading.Thread(target=meshinfo_mqtt.run)
    thread_web = threading.Thread(target=meshinfo_web.run)
    thread_renderer = threading.Thread(target=meshinfo_renderer.run)

    thread_mqtt.start()
    thread_web.start()
    thread_renderer.start()

    thread_mqtt.join()
    thread_web.join()
    thread_renderer.join()
