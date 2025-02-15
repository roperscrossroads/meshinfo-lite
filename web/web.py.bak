from flask import Flask, send_file, send_from_directory
from asgiref.wsgi import WsgiToAsgi
import uvicorn
import os

app = Flask(__name__)

# Define root directory and images directory
ROOT_DIR = os.path.abspath("./output/static-html")
IMAGES_DIR = os.path.abspath("./public/images")


class WEB:
    async def serve(self, loop):
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

        app_asgi = WsgiToAsgi(app)

        conf = uvicorn.Config(
            app=app_asgi,
            host="0.0.0.0",
            port=8000,
            loop=loop
        )
        server = uvicorn.Server(conf)
        print(
            f"Starting Uvicorn server bound at http://{conf.host}:{conf.port}"
        )
        await server.serve()
        print("Uvicorn server stopped")
