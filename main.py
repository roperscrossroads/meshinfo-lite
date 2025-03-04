import meshinfo_web
import meshinfo_mqtt
import meshinfo_renderer
import threading
import logging
import colorlog
import sys
#  logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
def setup_logger():
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Set to lowest level to capture all logs

    # Create a console handler
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)

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
    logger = setup_logger()

    thread_mqtt = threading.Thread(target=meshinfo_mqtt.run)
    thread_web = threading.Thread(target=meshinfo_web.run)
    thread_renderer = threading.Thread(target=meshinfo_renderer.run)

    thread_mqtt.start()
    thread_web.start()
    thread_renderer.start()

    thread_mqtt.join()
    thread_web.join()
    thread_renderer.join()
