from asgiref.wsgi import WsgiToAsgi
from flask import Flask, send_file, send_from_directory
from hypercorn.asyncio import serve
from hypercorn.config import Config
import os

app = Flask(__name__)

# Define root directory and images directory
ROOT_DIR = os.path.abspath("./output/static-html")
IMAGES_DIR = os.path.abspath("./public/images")
CSS_DIR = os.path.abspath("./public/css")


# Serve static files from the root directory
@app.route('/')
def serve_index():
    return send_file(f'{ROOT_DIR}/index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(ROOT_DIR, filename)


# Serve images from a separate directory
@app.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(IMAGES_DIR, filename)


# Serve CSS from a separate directory
@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(CSS_DIR, filename)


class WEB:
    async def serve(self):
        config = Config()
        config.bind = ["0.0.0.0:8000"]
        print(f"Starting Hypercorn server an port 8000")
        asgi_app = WsgiToAsgi(app)
        await serve(asgi_app, config)
        print("Hypercorn server stopped")
