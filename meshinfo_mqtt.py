import logging
from paho.mqtt import client as mqtt_client
from process_payload import process_payload
import configparser
import time


config = configparser.ConfigParser()
config.read("config.ini")
logger = logging.getLogger(__name__)


def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker!")
        else:
            logger.error("Failed to connect, return code %d\n", rc)

    def on_disconnect(client, userdata, rc):
        logger.warning(f"Disconnected with result code {rc}. Reconnecting...")
        while True:
            try:
                client.reconnect()
                logger.info("Reconnected successfully!")
                break
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                time.sleep(5)  # Wait before retrying
    client = mqtt_client.Client()
    if "username" in config["mqtt"] \
            and config["mqtt"]["username"] \
            and "password" in config["mqtt"] \
            and config["mqtt"]["password"]:
        client.username_pw_set(
            config["mqtt"]["username"],
            config["mqtt"]["password"]
        )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(config["mqtt"]["broker"], int(config["mqtt"]["port"]))
    return client


def subscribe(client: mqtt_client):
    def on_message(client, userdata, msg):
        if "/2/e/" in msg.topic or "/2/map/" in msg.topic:
            process_payload(msg.payload, msg.topic)

    client.subscribe(config["mqtt"]["topic"])
    client.on_message = on_message


def run():
    client = connect_mqtt()
    subscribe(client)
    client.loop_forever()


if __name__ == '__main__':
    run()
