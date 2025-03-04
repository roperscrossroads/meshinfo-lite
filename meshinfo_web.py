from flask import Flask, send_file, send_from_directory
from waitress import serve
import logging
import os

app = Flask(__name__)

# Define root directory and images directory
ROOT_DIR = os.path.abspath("./www")


# Serve static files from the root directory
@app.route('/')
def serve_index():
    return send_file(f'{ROOT_DIR}/index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(ROOT_DIR, filename)


def run():
    # Enable Waitress logging
    waitress_logger = logging.getLogger("waitress")
    waitress_logger.setLevel(logging.DEBUG)  # Enable all logs from Waitress
    serve(app, host="0.0.0.0", port=8080)
