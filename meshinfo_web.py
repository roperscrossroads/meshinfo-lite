from flask import Flask, send_file, send_from_directory, render_template
from waitress import serve
from paste.translogger import TransLogger
import configparser
import logging
import os

import utils
import meshtastic_support
from meshdata import MeshData
from meshtastic_monday import MeshtasticMonday
import json
import datetime
import time
import re

app = Flask(__name__)

config = configparser.ConfigParser()
config.read("config.ini")


# Serve static files from the root directory
@app.route('/')
def serve_index():
    md = MeshData()
    nodes = md.get_nodes()
    return render_template(
        "index.html.j2",
        config=config,
        nodes=nodes,
        active_nodes=utils.active_nodes(nodes),
        timestamp=datetime.datetime.now(),
    )


@app.route('/nodes.html')
def nodes():
    md = MeshData()
    nodes = md.get_nodes()
    latest = md.get_latest_node()
    return render_template(
        "nodes.html.j2",
        config=config,
        nodes=nodes,
        active_nodes=utils.active_nodes(nodes),
        latest=latest,
        hardware=meshtastic_support.HardwareModel,
        meshtastic_support=meshtastic_support,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )


@app.route('/chat.html')
def chat():
    md = MeshData()
    nodes = md.get_nodes()
    chat = md.get_chat()
    return render_template(
        "chat.html.j2",
        config=config,
        nodes=nodes,
        chat=chat,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )


@app.route('/graph.html')
def graph():
    md = MeshData()
    nodes = md.get_nodes()
    graph = md.graph_nodes()
    return render_template(
        "graph.html.j2",
        config=config,
        nodes=nodes,
        graph=graph,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )


@app.route('/map.html')
def map():
    md = MeshData()
    nodes = md.get_nodes()
    return render_template(
        "map.html.j2",
        config=config,
        nodes=nodes,
        utils=utils,
        datetime=datetime,
        timestamp=datetime.datetime.now()
    )


@app.route('/neighbors.html')
def neighbors():
    md = MeshData()
    nodes = md.get_nodes()
    active_nodes_with_neighbors = {
        node_id: dict(node)
        for node_id, node in nodes.items()
        if node.get("active") and node.get("neighbors")
    }
    return render_template(
        "neighbors.html.j2",
        config=config,
        nodes=nodes,
        active_nodes_with_neighbors=active_nodes_with_neighbors,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )


@app.route('/telemetry.html')
def telemetry():
    md = MeshData()
    nodes = md.get_nodes()
    telemetry = md.get_telemetry_all()
    return render_template(
        "telemetry.html.j2",
        config=config,
        nodes=nodes,
        telemetry=telemetry,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now()
    )


@app.route('/traceroutes.html')
def traceroutes():
    md = MeshData()
    nodes = md.get_nodes()
    traceroutes = md.get_traceroutes()
    return render_template(
        "traceroutes.html.j2",
        config=config,
        nodes=nodes,
        traceroutes=traceroutes,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )


@app.route('/logs.html')
def logs():
    md = MeshData()
    logs = md.get_logs()
    return render_template(
        "logs.html.j2",
        config=config,
        logs=logs,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
        json=json
    )


@app.route('/monday.html')
def monday():
    md = MeshData()
    nodes = md.get_nodes()
    chat = md.get_chat()
    monday = MeshtasticMonday(chat).get_data()
    return render_template(
        "monday.html.j2",
        config=config,
        nodes=nodes,
        monday=monday,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )


@app.route('/<path:filename>')
def serve_static(filename):
    nodep = r"node\_\w{8}\.html"
    if re.match(nodep, filename):
        md = MeshData()
        nodes = md.get_nodes()
        node = filename.replace("node_", "").replace(".html", "")
        return render_template(
                f"node.html.j2",
                config=config,
                node=nodes[node],
                nodes=nodes,
                hardware=meshtastic_support.HardwareModel,
                meshtastic_support=meshtastic_support,
                utils=utils,
                datetime=datetime.datetime,
                timestamp=datetime.datetime.now(),
            )

    return send_from_directory("www", filename)


def run():
    # Enable Waitress logging
    config = configparser.ConfigParser()
    config.read('config.ini')
    port = int(config["webserver"]["port"])

    waitress_logger = logging.getLogger("waitress")
    waitress_logger.setLevel(logging.DEBUG)  # Enable all logs from Waitress
    #  serve(app, host="0.0.0.0", port=port)
    serve(TransLogger(app, setup_console_handler=False), port=port)


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.ini')
    port = int(config["webserver"]["port"])
    app.run(debug=True, port=port)
