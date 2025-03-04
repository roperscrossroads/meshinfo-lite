# -*- coding: utf-8 -*-

import logging
import configparser
import datetime
import time
from jinja2 import Environment, FileSystemLoader

import utils
import meshtastic_support
from meshdata import MeshData
from meshtastic_monday import MeshtasticMonday
import json


class StaticHTMLRenderer:
    def __init__(self):
        md = MeshData()
        config = configparser.ConfigParser()
        config.read("config.ini")
        self.config = config
        self.nodes = md.get_nodes()
        self.chat = md.get_chat()
        self.graph = md.graph_nodes()
        self.telemetry = md.get_telemetry_all()
        self.traceroutes = md.get_traceroutes()
        self.logs = md.get_logs()
        self.active_nodes = {
            node: dict(self.nodes[node])
            for node in self.nodes if self.nodes[node]["active"]
        }

    def save_file(self, filename, content):
        """Save content to a file in the www directory."""
        with open(f"www/{filename}", "wb") as f:
            f.write(content.encode("utf-8"))

    def render_html(self, template_file, **kwargs):
        """Render an HTML template with the given arguments."""
        env = Environment(loader=FileSystemLoader("."), autoescape=True)
        template_file = "node.html" \
            if template_file.startswith("node_") else f"{template_file}"
        template = env.get_template(f"templates/{template_file}.j2")
        return template.render(**kwargs)

    def render_html_and_save(self, filename, **kwargs):
        """Render an HTML template and save the output."""
        logging.debug(f"Rendering {filename}")
        html = self.render_html(filename, **kwargs)
        self.save_file(filename, html)

    # Page Renderers
    def render_index(self):
        self.render_html_and_save(
            "index.html",
            config=self.config,
            nodes=self.nodes,
            active_nodes=self.active_nodes,
            timestamp=datetime.datetime.now(),
        )

    def render_chat(self):
        self.render_html_and_save(
            "chat.html",
            config=self.config,
            nodes=self.nodes,
            chat=self.chat,
            utils=utils,
            datetime=datetime.datetime,
            timestamp=datetime.datetime.now(),
        )

    def render_nodes(self):
        self.render_html_and_save(
            "nodes.html",
            config=self.config,
            nodes=self.nodes,
            active_nodes=self.active_nodes,
            hardware=meshtastic_support.HardwareModel,
            meshtastic_support=meshtastic_support,
            utils=utils,
            datetime=datetime.datetime,
            timestamp=datetime.datetime.now(),
        )

    def render_nodes_each(self):
        for node_id, node in self.nodes.items():
            self.render_html_and_save(
                f"node_{node_id}.html",
                config=self.config,
                node=node,
                nodes=self.nodes,
                hardware=meshtastic_support.HardwareModel,
                meshtastic_support=meshtastic_support,
                utils=utils,
                datetime=datetime.datetime,
                timestamp=datetime.datetime.now(),
            )

    def render_graph(self):
        self.render_html_and_save(
            "graph.html",
            config=self.config,
            nodes=self.nodes,
            graph=self.graph,
            utils=utils,
            datetime=datetime.datetime,
            timestamp=datetime.datetime.now(),
        )

    def render_map(self):
        self.render_html_and_save(
            "map.html",
            config=self.config,
            nodes=self.nodes,
            utils=utils,
            datetime=datetime,
            timestamp=datetime.datetime.now(),
        )

    def render_neighbors(self):
        active_nodes_with_neighbors = {
            node_id: dict(node)
            for node_id, node in self.nodes.items()
            if node.get("active") and node.get("neighbors")
        }

        self.render_html_and_save(
            "neighbors.html",
            config=self.config,
            nodes=self.nodes,
            active_nodes_with_neighbors=active_nodes_with_neighbors,
            utils=utils,
            datetime=datetime.datetime,
            timestamp=datetime.datetime.now(),
        )

    def render_telemetry(self):
        self.render_html_and_save(
            "telemetry.html",
            config=self.config,
            nodes=self.nodes,
            telemetry=self.telemetry,
            utils=utils,
            datetime=datetime.datetime,
            timestamp=datetime.datetime.now(),
        )

    def render_traceroutes(self):
        self.render_html_and_save(
            "traceroutes.html",
            config=self.config,
            nodes=self.nodes,
            traceroutes=self.traceroutes,
            utils=utils,
            datetime=datetime.datetime,
            timestamp=datetime.datetime.now(),
        )

    def render_monday(self):
        monday = MeshtasticMonday(self.chat).get_data()
        self.render_html_and_save(
            "monday.html",
            config=self.config,
            nodes=self.nodes,
            monday=monday,
            utils=utils,
            datetime=datetime.datetime,
            timestamp=datetime.datetime.now(),
        )
    
    def render_logs(self):
        self.render_html_and_save(
            "mqtt_log.html",
            config=self.config,
            logs=self.logs,
            utils=utils,
            datetime=datetime.datetime,
            timestamp=datetime.datetime.now(),
            json=json
        )

    def render(self):
        """Render all pages."""
        logging.info("Rendering web pages")
        self.render_logs()
        self.render_monday()
        self.render_traceroutes()
        self.render_telemetry()
        self.render_neighbors()
        self.render_index()
        self.render_chat()
        self.render_nodes()
        self.render_nodes_each()
        self.render_graph()
        self.render_map()


def render():
    renderer = StaticHTMLRenderer()
    renderer.render()


def run():
    config = configparser.ConfigParser()
    config.read("config.ini")
    interval = int(config["server"]["render_interval"])
    while True:
        render()
        time.sleep(interval)
