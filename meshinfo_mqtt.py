import logging
from paho.mqtt import client as mqtt_client
from process_payload import process_payload
from meshdata import MeshData # Import MeshData
from mqtt_stats import mqtt_stats
import configparser
import time
from meshtastic import mqtt_pb2, portnums_pb2


config = configparser.ConfigParser()
config.read("config.ini")
logger = logging.getLogger(__name__)

try:
    mesh_data_instance = MeshData()
    logger.info("MeshData instance created successfully.")
except Exception as e:
    logger.error(f"Fatal error: Could not initialize MeshData. Exiting. Error: {e}")
    exit(1) # Exit if we can't connect to the DB

def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        # Track connection statistics
        mqtt_stats.on_connect(rc)

        if rc == 0:
            logger.info("Connected to MQTT Broker! Return Code: %d", rc)
            # --- Add log before calling subscribe ---
            logger.info("on_connect: Attempting to subscribe...")
            try:
                subscribe(client, mesh_data_instance)
                logger.info("on_connect: subscribe() call completed.")
            except Exception as e:
                 logger.exception("on_connect: Error calling subscribe()") # Log exception if subscribe fails
            # --- End log ---
        else:
            logger.error("Failed to connect, return code %d", rc)

    def on_disconnect(client, userdata, rc):
        # Track disconnection statistics
        disconnect_reasons = {
            0: "Normal disconnection",
            1: "Unacceptable protocol version",
            2: "Identifier rejected",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorized",
            7: "Connection lost"
        }
        reason = disconnect_reasons.get(rc, f"Unknown reason (code {rc})")
        mqtt_stats.on_disconnect(rc, reason)

        logger.warning(f"Disconnected with result code {rc} ({reason}). Will attempt reconnect.")
        # No need for manual reconnect loop, paho handles it with reconnect_delay_set

    client = mqtt_client.Client(client_id="", clean_session=True, userdata=mesh_data_instance) # Ensure clean session if needed
    client.user_data_set(mesh_data_instance) # Redundant if passed in constructor, but safe
    if "username" in config["mqtt"] \
            and config["mqtt"]["username"] \
            and "password" in config["mqtt"] \
            and config["mqtt"]["password"]:
        logger.info("Setting MQTT username and password.")
        client.username_pw_set(
            config["mqtt"]["username"],
            config["mqtt"]["password"]
        )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=5, max_delay=120) # Increased min delay slightly

    broker_address = config["mqtt"]["broker"]
    broker_port = int(config["mqtt"]["port"])
    logger.info(f"Connecting to MQTT broker at {broker_address}:{broker_port}...")
    try:
        client.connect(broker_address, broker_port, 60) # Keepalive 60 seconds
    except Exception as e:
        logger.exception(f"Failed to connect to MQTT broker: {e}")
        raise # Reraise the exception to prevent starting loop_forever on failed connect
    return client


def extract_message_info(payload):
    """Extract basic message info for statistics without full processing"""
    try:
        se = mqtt_pb2.ServiceEnvelope()
        se.ParseFromString(payload)
        mp = se.packet

        if mp and mp.HasField("decoded"):
            portnum = mp.decoded.portnum

            # Map portnum to friendly name
            portnum_names = {
                portnums_pb2.TEXT_MESSAGE_APP: "Text Message",
                portnums_pb2.TEXT_MESSAGE_COMPRESSED_APP: "Text (Compressed)",
                portnums_pb2.POSITION_APP: "Position",
                portnums_pb2.NODEINFO_APP: "Node Info",
                portnums_pb2.ROUTING_APP: "Routing",
                portnums_pb2.TELEMETRY_APP: "Telemetry",
                portnums_pb2.NEIGHBORINFO_APP: "Neighbor Info",
                portnums_pb2.TRACEROUTE_APP: "Traceroute",
                portnums_pb2.MAP_REPORT_APP: "Map Report",
                portnums_pb2.ATAK_PLUGIN: "ATAK Plugin",
                portnums_pb2.STORE_FORWARD_APP: "Store & Forward",
                portnums_pb2.RANGE_TEST_APP: "Range Test",
                portnums_pb2.SIMULATOR_APP: "Simulator",
                portnums_pb2.ZPS_APP: "ZPS",
                portnums_pb2.POWERSTRESS_APP: "Power Stress",
                72: "ATAK Plugin"  # Explicitly include portnum 72
            }

            message_type = portnum_names.get(portnum, f"Unknown ({portnum})")
            return portnum, message_type
    except Exception as e:
        logger.debug(f"Could not extract message info: {e}")
    return None, None

def subscribe(client: mqtt_client, md_instance: MeshData):
    # --- Add log at the start ---
    logger.info("subscribe: Entered function.")
    # --- End log ---
    def on_message(client, userdata, msg):
        # Track raw message received (before any processing)
        mqtt_stats.on_raw_message_received()

        # Extract message info for statistics
        portnum, message_type = extract_message_info(msg.payload)

        # Track message received with type info
        mqtt_stats.on_message_received(portnum=portnum, message_type=message_type)

        # --- Add log for every message received ---
        logger.debug(f"on_message: Received message on topic: {msg.topic} (type: {message_type})")
        # --- End log ---

        # Filter for relevant topics
        if "/2/e/" in msg.topic or "/2/map/" in msg.topic:
            logger.debug(f"on_message: Processing message from relevant topic: {msg.topic}")
            try:
                # Pass the existing MeshData instance
                result = process_payload(msg.payload, msg.topic, md_instance)
                if result is None:
                    # Message was dropped (likely ATAK or other filter)
                    mqtt_stats.on_message_processed(success=True)  # Intentionally dropped
                else:
                    mqtt_stats.on_message_processed(success=True)
            except Exception as e:
                logger.exception(f"on_message: Error calling process_payload for topic {msg.topic}")
                mqtt_stats.on_message_dropped("PROCESSING_ERROR")
                mqtt_stats.on_message_processed(success=False)
        else:
            logger.debug(f"on_message: Skipping message from topic: {msg.topic}")
            # Still count as processed since we intentionally skipped it
            mqtt_stats.on_message_processed(success=True)


    topic_to_subscribe = config["mqtt"]["topic"]
    logger.info(f"subscribe: Subscribing to topic: {topic_to_subscribe}")
    try:
        result, mid = client.subscribe(topic_to_subscribe)
        if result == mqtt_client.MQTT_ERR_SUCCESS:
            logger.info(f"subscribe: Successfully initiated subscription to {topic_to_subscribe} (MID: {mid})")
        else:
            logger.error(f"subscribe: Failed to initiate subscription to {topic_to_subscribe}, Error code: {result}")
            return # Don't set on_message if subscribe failed

        logger.info("subscribe: Setting on_message callback.")
        client.on_message = on_message
        logger.info("subscribe: on_message callback set.")
    except Exception as e:
        logger.exception(f"subscribe: Error during subscribe call or setting on_message for topic {topic_to_subscribe}")



def run():
    logger.info("Starting MQTT client run sequence...")
    try:
        client = connect_mqtt()
        logger.info("Entering MQTT client loop (loop_forever)...")
        client.loop_forever()
    except Exception as e:
        logger.exception("An error occurred during MQTT client execution.")
    finally:
        logger.info("Exited MQTT client loop.")


if __name__ == '__main__':
    # Configure logging (ensure level allows DEBUG if you want to see the on_message logs)
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
    run()
