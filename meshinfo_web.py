from flask import (
    Flask,
    send_from_directory,
    render_template,
    request,
    make_response,
    redirect,
    url_for,
    abort,
    g,
    jsonify
)
from flask_caching import Cache
from waitress import serve
from paste.translogger import TransLogger
import configparser
import logging
import os

import utils
import meshtastic_support
from meshdata import MeshData
from meshinfo_register import Register
from meshtastic_monday import MeshtasticMonday
from meshinfo_telemetry_graph import draw_graph
from meshinfo_los_profile import LOSProfile
from timezone_utils import convert_to_local, format_timestamp, time_ago
import json
import datetime
import time
import re

app = Flask(__name__)

cache_dir = os.path.join(os.path.dirname(__file__), 'runtime_cache')

# Ensure the cache directory exists
if not os.path.exists(cache_dir):
    try:
        os.makedirs(cache_dir)
        logging.info(f"Created cache directory: {cache_dir}")
    except OSError as e:
        logging.error(f"Could not create cache directory {cache_dir}: {e}")
        cache_dir = None # Indicate failure

# Configure Flask-Caching
cache_config = {
    'CACHE_TYPE': 'SimpleCache', # Default fallback
    'CACHE_DEFAULT_TIMEOUT': 300 # Default timeout 5 minutes
}
if cache_dir:
    cache_config = {
        'CACHE_TYPE': 'FileSystemCache',
        'CACHE_DIR': cache_dir,
        'CACHE_THRESHOLD': 1000,  # Max number of items (optional, adjust as needed)
        'CACHE_DEFAULT_TIMEOUT': 60 # Keep your 60 second default timeout
    }
    logging.info(f"Using FileSystemCache with directory: {cache_dir}")
else:
    logging.warning("Falling back to SimpleCache due to directory creation issues.")


# Initialize Cache with the chosen config
cache = Cache(app, config=cache_config)

# Make globals available to templates
app.jinja_env.globals.update(convert_to_local=convert_to_local)
app.jinja_env.globals.update(format_timestamp=format_timestamp)
app.jinja_env.globals.update(time_ago=time_ago)
app.jinja_env.globals.update(min=min)
app.jinja_env.globals.update(max=max)

config = configparser.ConfigParser()
config.read("config.ini")


# --- Add these MeshData Management functions ---
def get_meshdata():
    """Opens a new MeshData connection if there is none yet for the
    current application context.
    """
    if 'meshdata' not in g:
        try:
            g.meshdata = MeshData()
            logging.debug("MeshData instance created for request context.")
        except Exception as e:
            logging.error(f"Failed to create MeshData for request context: {e}")
            # Indicate failure
            g.meshdata = None
    return g.meshdata

@app.teardown_appcontext
def teardown_meshdata(exception):
    """Closes the MeshData connection at the end of the request."""
    md = g.pop('meshdata', None)
    if md is not None:
        # MeshData.__del__ should handle closing connection if implemented
        # Add explicit md.db.close() if __del__ doesn't or isn't reliable
        logging.debug("MeshData instance removed from request context.")
# --- End MeshData Management functions ---


def auth():
    jwt = request.cookies.get('jwt')
    if not jwt:
        return None
    reg = Register()
    decoded_jwt = reg.auth(jwt)
    return decoded_jwt


@app.errorhandler(404)
def not_found(e):
    return render_template(
        "404.html.j2",
        auth=auth,
        config=config
    ), 404


# Serve static files from the root directory
@app.route('/')
@cache.cached(timeout=60)  # Cache for 60 seconds
def serve_index(success_message=None, error_message=None):
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    nodes = md.get_nodes()
    return render_template(
        "index.html.j2",
        auth=auth(),
        config=config,
        nodes=nodes,
        active_nodes=utils.active_nodes(nodes),
        timestamp=datetime.datetime.now(),
        success_message=success_message,
        error_message=error_message
    )


@app.route('/nodes.html')
@cache.cached(timeout=60)  # Cache for 60 seconds
def nodes():
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    nodes = md.get_nodes()
    logging.info(f"/nodes.html: Loaded {len(nodes)} nodes.") # Add this
    latest = md.get_latest_node()
    return render_template(
        "nodes.html.j2",
        auth=auth(),
        config=config,
        nodes=nodes,
        show_inactive=False,  # Add this line
        latest=latest,
        hardware=meshtastic_support.HardwareModel,
        meshtastic_support=meshtastic_support,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )

@app.route('/allnodes.html')
@cache.cached(timeout=60)  # Cache for 60 seconds
def allnodes():
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    nodes = md.get_nodes()
    latest = md.get_latest_node()
    return render_template(
        "nodes.html.j2",  # Change to use nodes.html.j2
        auth=auth(),
        config=config,
        nodes=nodes,
        show_inactive=True,
        latest=latest,
        hardware=meshtastic_support.HardwareModel,
        meshtastic_support=meshtastic_support,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )


@app.route('/chat-classic.html')
def chat():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    nodes = md.get_nodes()
    chat_data = md.get_chat(page=page, per_page=per_page)
    
    # start_item and end_item for pagination
    chat_data['start_item'] = (page - 1) * per_page + 1 if chat_data['total'] > 0 else 0
    chat_data['end_item'] = min(page * per_page, chat_data['total'])
    
    return render_template(
        "chat.html.j2",
        auth=auth(),
        config=config,
        nodes=nodes,
        chat=chat_data["items"],
        pagination=chat_data,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
        debug=False,
    )

@app.route('/chat.html')
def chat2():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    nodes = md.get_nodes()
    chat_data = md.get_chat(page=page, per_page=per_page)
    
    chat_data['start_item'] = (page - 1) * per_page + 1 if chat_data['total'] > 0 else 0
    chat_data['end_item'] = min(page * per_page, chat_data['total'])
    
    return render_template(
        "chat2.html.j2",
        auth=auth(),
        config=config,
        nodes=nodes,
        chat=chat_data["items"],
        pagination=chat_data,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
        meshtastic_support=meshtastic_support,
        debug=False,
    )

@app.route('/message_map.html')
def message_map():
    message_id = request.args.get('id')
    if not message_id:
        abort(404)

    md = get_meshdata() # Use application context
    if not md: abort(503, description="Database connection unavailable")

    nodes = md.get_nodes() # Still get latest node info for names etc.

    # Get message and basic reception data
    cursor = md.db.cursor(dictionary=True)
    cursor.execute("""
        SELECT t.*, GROUP_CONCAT(r.received_by_id) as receiver_ids
        FROM text t
        LEFT JOIN message_reception r ON t.message_id = r.message_id
        WHERE t.message_id = %s
        GROUP BY t.message_id
    """, (message_id,))

    message_base = cursor.fetchone()
    cursor.close()

    if not message_base:
        abort(404)

    # Get the precise message time (assuming ts_created is Unix timestamp)
    message_time = message_base['ts_created'].timestamp() # Convert from DB datetime to Unix timestamp

    # Fetch historical position for the sender
    sender_position = md.get_position_at_time(message_base['from_id'], message_time)

    # Fetch historical positions for receivers
    receiver_positions = {}
    receiver_details = {} # Store SNR etc. associated with the position
    if message_base['receiver_ids']:
        receiver_ids_list = [int(r_id) for r_id in message_base['receiver_ids'].split(',')]

        # Fetch full reception details for these receivers for THIS message
        # Need a separate query as GROUP_CONCAT loses details
        query_placeholders = ', '.join(['%s'] * len(receiver_ids_list))
        sql_reception = f"""
            SELECT * FROM message_reception
            WHERE message_id = %s AND received_by_id IN ({query_placeholders})
        """
        params_reception = [message_id] + receiver_ids_list
        cursor = md.db.cursor(dictionary=True)
        cursor.execute(sql_reception, params_reception)
        receptions = cursor.fetchall()
        cursor.close()

        for reception in receptions: # Iterate through detailed reception info
            receiver_id = reception['received_by_id']
            logging.info(f"Attempting to find position for receiver: {receiver_id} at time {message_time}") # Log attempt
            pos = md.get_position_at_time(receiver_id, message_time)
            logging.info(f"Position found for receiver {receiver_id}: {pos}") # Log result
            if pos: # Only store if position was actually found
                receiver_positions[receiver_id] = pos
                # Store details associated with this reception
                receiver_details[receiver_id] = {
                    'rx_snr': reception['rx_snr'],
                    'rx_rssi': reception['rx_rssi'],
                    'hop_start': reception['hop_start'],
                    'hop_limit': reception['hop_limit'],
                    'rx_time': reception['rx_time']
                }
            else:
                logging.warning(f"No position found for receiver {receiver_id} near time {message_time}")


    # Prepare message object for template
    message = {
        'id': message_id,
        'from_id': message_base['from_id'],
        'text': message_base['text'],
        'ts_created': message_time, # Pass Unix timestamp
        # Pass receiver IDs and their corresponding details
        'receiver_ids': receiver_ids_list if message_base['receiver_ids'] else []
    }


    # Check if sender has position data before rendering map
    if not sender_position:
         # Decide how to handle - show map without sender? Show error?
         # For now, let's allow rendering but template must handle missing sender pos
         logging.warning(f"Sender position at time {message_time} not found for node {message['from_id']}")
         # abort(404, description="Sender position data not available for message time")

    # --- Add this logging ---
    logging.debug(f"Data for message {message_id} map:")
    logging.debug(f"  Sender Position: {sender_position}")
    logging.debug(f"  Receiver Positions Dict: {receiver_positions}")
    logging.debug(f"  Receiver Details Dict: {receiver_details}")
    logging.debug(f"  Receiver IDs List: {message.get('receiver_ids', [])}")
    # --- End logging ---

    return render_template(
        "message_map.html.j2",
        auth=auth(),
        config=config,
        nodes=nodes, # Pass current node info for names
        message=message,
        sender_position=sender_position, # Pass historical sender position
        receiver_positions=receiver_positions, # Pass dict of historical receiver positions
        receiver_details=receiver_details, # Pass dict of receiver SNR/hop details
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now() # Page generation time
    )

@app.route('/traceroute_map.html')
def traceroute_map():
    traceroute_id = request.args.get('id')
    if not traceroute_id:
        abort(404)
        
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    nodes = md.get_nodes()
    
    # Get traceroute data
    cursor = md.db.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM traceroute WHERE traceroute_id = %s
    """, (traceroute_id,))
    
    traceroute_data = cursor.fetchone()
    if not traceroute_data:
        abort(404)
    
    # Format the forward route data
    route = []
    if traceroute_data['route']:
        route = [int(hop) for hop in traceroute_data['route'].split(';')]
    
    # Format the return route data
    route_back = []
    if traceroute_data['route_back']:
        route_back = [int(hop) for hop in traceroute_data['route_back'].split(';')]
    
    # Format the forward SNR values
    snr_towards = []
    if traceroute_data['snr_towards']:
        snr_towards = [float(s) for s in traceroute_data['snr_towards'].split(';')]
    
    # Format the return SNR values
    snr_back = []
    if traceroute_data['snr_back']:
        snr_back = [float(s) for s in traceroute_data['snr_back'].split(';')]
    
    # Create a clean traceroute object for the template
    traceroute = {
        'id': traceroute_data['traceroute_id'],
        'from_id': traceroute_data['from_id'],
        'from_id_hex': utils.convert_node_id_from_int_to_hex(traceroute_data['from_id']),
        'to_id': traceroute_data['to_id'],
        'to_id_hex': utils.convert_node_id_from_int_to_hex(traceroute_data['to_id']),
        'ts_created': traceroute_data['ts_created'],
        'route': route,
        'route_back': route_back,
        'snr_towards': snr_towards,
        'snr_back': snr_back,
        'success': traceroute_data['success']
    }
    
    cursor.close()
    
    return render_template(
        "traceroute_map.html.j2",
        auth=auth(),
        config=config,
        nodes=nodes,
        traceroute=traceroute,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now()
    )

@app.route('/graph.html')
@cache.cached(timeout=60, query_string=True) # Cache based on query string (view type)
def graph():
    view_type = request.args.get('view', 'merged') # Default to merged view
    md = get_meshdata()
    if not md:
        abort(503, description="Database connection unavailable")

    # Get graph data using the new method
    graph_data = md.get_graph_data(view_type=view_type)

    # Log graph data size for debugging
    logging.debug(f"Graph data for view '{view_type}': {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges.")

    return render_template(
        "graph.html.j2",
        auth=auth(),
        config=config,
        nodes=md.get_nodes(),  # Pass full nodes list for lookups in template
        graph=graph_data,
        view_type=view_type,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )

@app.route('/graph2.html')
@cache.cached(timeout=60, query_string=True)  # Cache based on query string (view type)
def graph2():
    view_type = request.args.get('view', 'merged')  # Default to merged view
    md = get_meshdata()
    if not md:
        abort(503, description="Database connection unavailable")

    # Get graph data using the new method
    graph_data = md.get_graph_data(view_type=view_type)

    # Log graph data size for debugging
    logging.debug(f"Graph data for view '{view_type}': {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges.")

    return render_template(
        "graph2.html.j2",
        auth=auth(),
        config=config,
        nodes=md.get_nodes(),  # Pass full nodes list for lookups in template
        graph=graph_data,
        view_type=view_type,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )

@app.route('/graph3.html')
@cache.cached(timeout=60, query_string=True)  # Cache based on query string (view type)
def graph3():
    view_type = request.args.get('view', 'merged')  # Default to merged view
    md = get_meshdata()
    if not md:
        abort(503, description="Database connection unavailable")

    # Get graph data using the new method
    graph_data = md.get_graph_data(view_type=view_type)

    # Log graph data size for debugging
    logging.debug(f"Graph data for view '{view_type}': {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges.")

    return render_template(
        "graph3.html.j2",
        auth=auth(),
        config=config,
        nodes=md.get_nodes(),  # Pass full nodes list for lookups in template
        graph=graph_data,
        view_type=view_type,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )

@app.route('/graph4.html')
@cache.cached(timeout=60, query_string=True)  # Cache based on query string (view type)
def graph4():
    view_type = request.args.get('view', 'merged')  # Default to merged view
    md = get_meshdata()
    if not md:
        abort(503, description="Database connection unavailable")

    # Get graph data using the new method
    graph_data = md.get_graph_data(view_type=view_type)

    # Log graph data size for debugging
    logging.debug(f"Graph data for view '{view_type}': {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges.")

    return render_template(
        "graph4.html.j2",
        auth=auth(),
        config=config,
        nodes=md.get_nodes(),  # Pass full nodes list for lookups in template
        graph=graph_data,
        view_type=view_type,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )

@app.route('/map.html')
def map():
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    nodes = md.get_nodes()
    
    # Get timeout from config
    zero_hop_timeout = int(config.get("server", "zero_hop_timeout", fallback=43200))
    cutoff_time = int(time.time()) - zero_hop_timeout
    
    # Get zero-hop data for all nodes
    cursor = md.db.cursor(dictionary=True)
    zero_hop_data = {}
    
    # Query for all zero-hop messages
    cursor.execute("""
        SELECT 
            r.from_id,
            r.received_by_id,
            COUNT(*) AS count,
            MAX(r.rx_snr) AS best_snr,
            AVG(r.rx_snr) AS avg_snr,
            MAX(r.rx_time) AS last_rx_time
        FROM 
            message_reception r
        WHERE
            (
                (r.hop_limit IS NULL AND r.hop_start IS NULL)
                OR
                (r.hop_start - r.hop_limit = 0)
            )
            AND r.rx_time > %s
        GROUP BY 
            r.from_id, r.received_by_id
        ORDER BY
            last_rx_time DESC
    """, (cutoff_time,))
    
    for row in cursor.fetchall():
        from_id = utils.convert_node_id_from_int_to_hex(row['from_id'])
        received_by_id = utils.convert_node_id_from_int_to_hex(row['received_by_id'])
        
        if from_id not in zero_hop_data:
            zero_hop_data[from_id] = {'heard': [], 'heard_by': []}
        if received_by_id not in zero_hop_data:
            zero_hop_data[received_by_id] = {'heard': [], 'heard_by': []}
            
        # Add to heard_by list of sender
        zero_hop_data[from_id]['heard_by'].append({
            'node_id': received_by_id,
            'count': row['count'],
            'best_snr': row['best_snr'],
            'avg_snr': row['avg_snr'],
            'last_rx_time': row['last_rx_time']
        })
        
        # Add to heard list of receiver
        zero_hop_data[received_by_id]['heard'].append({
            'node_id': from_id,
            'count': row['count'],
            'best_snr': row['best_snr'],
            'avg_snr': row['avg_snr'],
            'last_rx_time': row['last_rx_time']
        })
    
    cursor.close()
    
    return render_template(
        "map.html.j2",
        auth=auth(),
        config=config,
        nodes=nodes,
        zero_hop_data=zero_hop_data,
        zero_hop_timeout=zero_hop_timeout,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now()
    )


@app.route('/neighbors.html')
def neighbors():
    view_type = request.args.get('view', 'neighbor_info') # Default to neighbor_info
    md = get_meshdata()
    if not md:
        abort(503, description="Database connection unavailable")

    # Get base node data (already optimized)
    nodes = md.get_nodes()
    if not nodes:
        # Handle case with no nodes gracefully
        return render_template(
            "neighbors.html.j2",
            auth=auth(), config=config, nodes={},
            active_nodes_with_connections={}, view_type=view_type,
            utils=utils, datetime=datetime.datetime, timestamp=datetime.datetime.now()
        )

    # Get neighbors data using the new method
    active_nodes_data = md.get_neighbors_data(view_type=view_type)

    # Sort final results by last heard time
    active_nodes_data = dict(sorted(
        active_nodes_data.items(),
        key=lambda item: item[1].get('last_heard', datetime.datetime.min),
        reverse=True
    ))

    return render_template(
        "neighbors.html.j2",
        auth=auth(),
        config=config,
        nodes=nodes, # Pass full nodes list for lookups in template
        active_nodes_with_connections=active_nodes_data, # Pass the processed data
        view_type=view_type,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )

@app.route('/telemetry.html')
def telemetry():
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    nodes = md.get_nodes()
    telemetry = md.get_telemetry_all()
    return render_template(
        "telemetry.html.j2",
        auth=auth(),
        config=config,
        nodes=nodes,
        telemetry=telemetry,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now()
    )


@app.route('/traceroutes.html')
def traceroutes():
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    page = request.args.get('page', 1, type=int)
    per_page = 100
    
    nodes = md.get_nodes()
    traceroute_data = md.get_traceroutes(page=page, per_page=per_page)
    
    # Calculate pagination info
    total = traceroute_data['total']
    start_item = (page - 1) * per_page + 1 if total > 0 else 0
    end_item = min(page * per_page, total)
    
    # Create pagination info
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'items': traceroute_data['items'],
        'pages': (total + per_page - 1) // per_page,
        'has_prev': page > 1,
        'has_next': page * per_page < total,
        'prev_num': page - 1,
        'next_num': page + 1,
        'start_item': start_item,
        'end_item': end_item
    }
    
    return render_template(
        "traceroutes.html.j2",
        auth=auth(),
        config=config,
        nodes=nodes,
        traceroutes=traceroute_data['items'],
        pagination=pagination,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )


@app.route('/logs.html')
def logs():
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    logs = md.get_logs()
    return render_template(
        "logs.html.j2",
        auth=auth(),
        config=config,
        logs=logs,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
        json=json
    )


@app.route('/monday.html')
def monday():
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    nodes = md.get_nodes()
    chat = md.get_chat()
    monday = MeshtasticMonday(chat).get_data()
    return render_template(
        "monday.html.j2",
        auth=auth(),
        config=config,
        nodes=nodes,
        monday=monday,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )


@app.route('/mynodes.html')
def mynodes():
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    nodes = md.get_nodes()
    owner = auth()
    if not owner:
        return redirect(url_for('login'))
    mynodes = utils.get_owner_nodes(nodes, owner["email"])
    return render_template(
        "mynodes.html.j2",
        auth=owner,
        config=config,
        nodes=mynodes,
        show_inactive=True,
        hardware=meshtastic_support.HardwareModel,
        meshtastic_support=meshtastic_support,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
    )


@app.route('/linknode.html')
def link_node():
    owner = auth()
    if not owner:
        return redirect(url_for('login'))
    reg = Register()
    otp = reg.get_otp(
        owner["email"]
    )
    return render_template(
        "link_node.html.j2",
        auth=owner,
        otp=otp,
        config=config
    )


@app.route('/register.html', methods=['GET', 'POST'])
def register():
    error_message = None
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        reg = Register()
        res = reg.register(username, email, password)
        if "error" in res:
            error_message = res["error"]
        elif "success" in res:
            return serve_index(success_message=res["success"])

    return render_template(
        "register.html.j2",
        auth=auth(),
        config=config,
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now(),
        error_message=error_message
    )


@app.route('/login.html', methods=['GET', 'POST'])
def login(success_message=None, error_message=None):
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        reg = Register()
        res = reg.authenticate(email, password)
        if "error" in res:
            error_message = res["error"]
        elif "success" in res:
            jwt = res["success"]
            resp = make_response(redirect(url_for('mynodes')))
            resp.set_cookie("jwt", jwt)
            return resp
    return render_template(
            "login.html.j2",
            auth=auth(),
            config=config,
            datetime=datetime.datetime,
            timestamp=datetime.datetime.now(),
            success_message=success_message,
            error_message=error_message
        )


@app.route('/logout.html')
def logout():
    resp = make_response(redirect(url_for('serve_index')))
    resp.set_cookie('jwt', '', expires=0)
    return resp


@app.route('/verify')
def verify():
    code = request.args.get('c')
    reg = Register()
    res = reg.verify_account(code)
    if "error" in res:
        return serve_index(error_message=res["error"])
    elif "success" in res:
        return login(success_message=res["success"])
    return serve_index()


@app.route('/<path:filename>')
def serve_static(filename):
    nodep = r"node\_(\w{8})\.html"
    userp = r"user\_(\w+)\.html"

    if re.match(nodep, filename):
        md = get_meshdata()
        if not md: # Check if MeshData failed to initialize
            abort(503, description="Database connection unavailable")
        match = re.match(nodep, filename)
        node = match.group(1)
        nodes = md.get_nodes()
        if node not in nodes:
            abort(404)
        node_id = utils.convert_node_id_from_hex_to_int(node)
        node_telemetry = md.get_node_telemetry(node_id)
        node_route = md.get_route_coordinates(node_id)
        telemetry_graph = draw_graph(node_telemetry)
        lp = LOSProfile(nodes, node_id, config, cache)

        # Get the max_distance from config, default to 5000 meters (5 km)
        max_distance_km = int(config.get("los", "max_distance", fallback=5000)) / 1000  # Convert to kilometers

        # Check if LOS Profile rendering is enabled
        los_enabled = config.getboolean("los", "enabled", fallback=False)

        # Get timeout from config
        zero_hop_timeout = int(config.get("server", "zero_hop_timeout", fallback=43200))  # Default 12 hours
        cutoff_time = int(time.time()) - zero_hop_timeout
        
        # Query for zero-hop messages heard by this node (within timeout period)
        db = md.db
        zero_hop_heard = []
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                r.from_id,
                COUNT(*) AS count,
                MAX(r.rx_snr) AS best_snr,
                AVG(r.rx_snr) AS avg_snr,
                MAX(r.rx_time) AS last_rx_time
            FROM 
                message_reception r
            WHERE
                r.received_by_id = %s
                AND (
                    (r.hop_limit IS NULL AND r.hop_start IS NULL)
                    OR
                    (r.hop_start - r.hop_limit = 0)
                )
                AND r.rx_time > %s
            GROUP BY 
                r.from_id
            ORDER BY
                last_rx_time DESC
        """, (node_id, cutoff_time))
        zero_hop_heard = cursor.fetchall()
        
        # Query for zero-hop messages sent by this node and heard by others (within timeout period)
        zero_hop_heard_by = []
        cursor.execute("""
            SELECT 
                r.received_by_id,
                COUNT(*) AS count,
                MAX(r.rx_snr) AS best_snr,
                AVG(r.rx_snr) AS avg_snr,
                MAX(r.rx_time) AS last_rx_time
            FROM 
                message_reception r
            WHERE
                r.from_id = %s
                AND (
                    (r.hop_limit IS NULL AND r.hop_start IS NULL)
                    OR
                    (r.hop_start - r.hop_limit = 0)
                )
                AND r.rx_time > %s
            GROUP BY 
                r.received_by_id
            ORDER BY
                last_rx_time DESC
        """, (node_id, cutoff_time))
        zero_hop_heard_by = cursor.fetchall()
        cursor.close()
        
        return render_template(
            f"node.html.j2",
            auth=auth(),
            config=config,
            node=nodes[node],
            nodes=nodes,
            hardware=meshtastic_support.HardwareModel,
            meshtastic_support=meshtastic_support,
            los_profiles=lp.get_profiles() if los_enabled else {},  # Render only if enabled
            telemetry_graph=telemetry_graph,
            node_route=node_route,
            utils=utils,
            datetime=datetime.datetime,
            timestamp=datetime.datetime.now(),
            zero_hop_heard=zero_hop_heard,
            zero_hop_heard_by=zero_hop_heard_by,
            zero_hop_timeout=zero_hop_timeout,
            max_distance=max_distance_km
        )

    if re.match(userp, filename):
        match = re.match(userp, filename)
        username = match.group(1)
        md = get_meshdata()
        if not md: # Check if MeshData failed to initialize
            abort(503, description="Database connection unavailable")
        owner = md.get_user(username)
        if not owner:
            abort(404)
        nodes = md.get_nodes()
        owner_nodes = utils.get_owner_nodes(nodes, owner["email"])
        return render_template(
            "user.html.j2",
            auth=auth(),
            username=username,
            config=config,
            nodes=owner_nodes,
            show_inactive=True,
            hardware=meshtastic_support.HardwareModel,
            meshtastic_support=meshtastic_support,
            utils=utils,
            datetime=datetime.datetime,
            timestamp=datetime.datetime.now(),
        )

    return send_from_directory("www", filename)


@app.route('/metrics.html')
@cache.cached(timeout=60)  # Cache for 60 seconds
def metrics():
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    return render_template(
        "metrics.html.j2",
        auth=auth(),
        config=config,
        this_page="metrics",
        utils=utils,
        datetime=datetime.datetime,
        timestamp=datetime.datetime.now()
    )

@app.route('/api/metrics')
def get_metrics():
    md = get_meshdata()
    if not md: # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    
    try:
        # Get time range from request parameters
        time_range = request.args.get('time_range', 'day')  # day, week, month, year, all
        
        # Set time range based on parameter
        end_time = datetime.datetime.now()
        if time_range == 'week':
            start_time = end_time - datetime.timedelta(days=7)
            bucket_size = 180  # 3 hours in minutes
        elif time_range == 'month':
            start_time = end_time - datetime.timedelta(days=30)
            bucket_size = 720  # 12 hours in minutes
        elif time_range == 'year':
            start_time = end_time - datetime.timedelta(days=365)
            bucket_size = 2880  # 2 days in minutes
        elif time_range == 'all':
            # For 'all', we'll first check the data range in the database
            cursor = md.db.cursor(dictionary=True)
            cursor.execute("SELECT MIN(ts_created) as min_time FROM telemetry")
            min_time = cursor.fetchone()['min_time']
            cursor.close()
            
            if min_time:
                start_time = min_time
            else:
                # Default to 1 year if no data
                start_time = end_time - datetime.timedelta(days=365)
            
            bucket_size = 10080  # 7 days in minutes
        else:  # Default to 'day'
            start_time = end_time - datetime.timedelta(hours=24)
            bucket_size = 30  # 30 minutes
        
        logging.info(f"Fetching metrics data from {start_time} to {end_time} with bucket size {bucket_size} minutes")
        
        # Check if we have any data in the tables
        cursor = md.db.cursor(dictionary=True)
        
        # Get the actual time range of data in the database
        cursor.execute("SELECT MIN(ts_created) as min_time, MAX(ts_created) as max_time FROM telemetry")
        telemetry_time_range = cursor.fetchone()
        logging.info(f"Telemetry data time range: {telemetry_time_range['min_time']} to {telemetry_time_range['max_time']}")
        
        cursor.execute("SELECT MIN(ts_created) as min_time, MAX(ts_created) as max_time FROM text")
        text_time_range = cursor.fetchone()
        logging.info(f"Text data time range: {text_time_range['min_time']} to {text_time_range['max_time']}")
        
        cursor.execute("SELECT MIN(ts_created) as min_time, MAX(ts_created) as max_time FROM message_reception")
        reception_time_range = cursor.fetchone()
        logging.info(f"Message reception data time range: {reception_time_range['min_time']} to {reception_time_range['max_time']}")
        
        # Check if tables exist and have data
        cursor.execute("SELECT COUNT(*) as count FROM telemetry")
        telemetry_count = cursor.fetchone()['count']
        logging.info(f"Telemetry table has {telemetry_count} records")
        
        cursor.execute("SELECT COUNT(*) as count FROM text")
        text_count = cursor.fetchone()['count']
        logging.info(f"Text table has {text_count} records")
        
        cursor.execute("SELECT COUNT(*) as count FROM message_reception")
        reception_count = cursor.fetchone()['count']
        logging.info(f"Message_reception table has {reception_count} records")
        
        # Add warnings for metrics with incomplete data
        warnings = []
        if telemetry_time_range['min_time'] and telemetry_time_range['min_time'] > start_time:
            warnings.append(
                f"Telemetry data (nodes online, channel utilization, battery, temperature) "
                f"only available from {telemetry_time_range['min_time'].strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        # Convert timestamps to the correct format for MySQL
        start_timestamp = start_time.strftime('%Y-%m-%d %H:%M:%S')
        end_timestamp = end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        logging.info(f"Querying with timestamps: {start_timestamp} to {end_timestamp}")
        
        # Format string for time buckets based on bucket size
        if bucket_size >= 10080:  # 7 days or more
            time_format = '%Y-%m-%d'  # Daily format
        elif bucket_size >= 1440:  # 1 day or more
            time_format = '%Y-%m-%d %H:00'  # Hourly format
        else:
            time_format = '%Y-%m-%d %H:%i'  # Minute format
        
        # Nodes Online
        nodes_online_query = f"""
            SELECT 
                DATE_FORMAT(
                    DATE_ADD(
                        ts_created,
                        INTERVAL -MOD(MINUTE(ts_created), {bucket_size}) MINUTE
                    ),
                    '{time_format}'
                ) as time_slot,
                COUNT(DISTINCT id) as node_count
            FROM telemetry
            WHERE ts_created >= %s AND ts_created <= %s
            GROUP BY time_slot
            ORDER BY time_slot
        """
        logging.debug(f"Executing nodes online query with params: {start_timestamp}, {end_timestamp}")
        cursor.execute(nodes_online_query, (start_timestamp, end_timestamp))
        nodes_online = cursor.fetchall()
        logging.debug(f"Nodes online query returned {len(nodes_online)} records. First record: {nodes_online[0] if nodes_online else 'None'}")
        
        # Message Traffic
        # First, generate a series of time slots
        time_slots_query = f"""
            WITH RECURSIVE time_slots AS (
                SELECT DATE_FORMAT(
                    DATE_ADD(%s, INTERVAL -MOD(MINUTE(%s), {bucket_size}) MINUTE),
                    '{time_format}'
                ) as time_slot
                UNION ALL
                SELECT DATE_FORMAT(
                    DATE_ADD(
                        STR_TO_DATE(time_slot, '{time_format}'),
                        INTERVAL {bucket_size} MINUTE
                    ),
                    '{time_format}'
                )
                FROM time_slots
                WHERE STR_TO_DATE(time_slot, '{time_format}') < %s
            )
            SELECT t.time_slot,
                   COALESCE(m.message_count, 0) as message_count
            FROM time_slots t
            LEFT JOIN (
                SELECT DATE_FORMAT(
                    DATE_ADD(
                        ts_created,
                        INTERVAL -MOD(MINUTE(ts_created), {bucket_size}) MINUTE
                    ),
                    '{time_format}'
                ) as time_slot,
                COUNT(*) as message_count
                FROM text
                WHERE ts_created >= %s AND ts_created <= %s
                GROUP BY time_slot
            ) m ON t.time_slot = m.time_slot
            ORDER BY t.time_slot;
        """
        logging.debug(f"Executing message traffic query with params: {start_timestamp}, {end_timestamp}")
        cursor.execute(time_slots_query, (start_timestamp, start_timestamp, end_timestamp, start_timestamp, end_timestamp))
        message_traffic = cursor.fetchall()
        logging.debug(f"Message traffic query returned {len(message_traffic)} records. First record: {message_traffic[0] if message_traffic else 'None'}")
        
        # Channel Utilization
        channel_util_query = f"""
            SELECT 
                DATE_FORMAT(
                    DATE_ADD(
                        ts_created,
                        INTERVAL -MOD(MINUTE(ts_created), {bucket_size}) MINUTE
                    ),
                    '{time_format}'
                ) as time_slot,
                AVG(channel_utilization) as avg_util
            FROM telemetry
            WHERE ts_created >= %s AND ts_created <= %s
            GROUP BY time_slot
            ORDER BY time_slot
        """
        logging.debug(f"Executing channel utilization query with params: {start_timestamp}, {end_timestamp}")
        cursor.execute(channel_util_query, (start_timestamp, end_timestamp))
        channel_util = cursor.fetchall()
        logging.debug(f"Channel utilization query returned {len(channel_util)} records. First record: {channel_util[0] if channel_util else 'None'}")
        
        # Average Battery Level
        battery_query = f"""
            SELECT 
                DATE_FORMAT(
                    DATE_ADD(
                        ts_created,
                        INTERVAL -MOD(MINUTE(ts_created), {bucket_size}) MINUTE
                    ),
                    '{time_format}'
                ) as time_slot,
                AVG(battery_level) as avg_battery
            FROM telemetry
            WHERE ts_created >= %s AND ts_created <= %s
            GROUP BY time_slot
            ORDER BY time_slot
        """
        logging.debug(f"Executing battery level query with params: {start_timestamp}, {end_timestamp}")
        cursor.execute(battery_query, (start_timestamp, end_timestamp))
        battery_levels = cursor.fetchall()
        logging.debug(f"Battery level query returned {len(battery_levels)} records. First record: {battery_levels[0] if battery_levels else 'None'}")
        
        # Average Temperature
        temperature_query = f"""
            SELECT 
                DATE_FORMAT(
                    DATE_ADD(
                        ts_created,
                        INTERVAL -MOD(MINUTE(ts_created), {bucket_size}) MINUTE
                    ),
                    '{time_format}'
                ) as time_slot,
                AVG(temperature) as avg_temp
            FROM telemetry
            WHERE ts_created >= %s AND ts_created <= %s
            GROUP BY time_slot
            ORDER BY time_slot
        """
        logging.debug(f"Executing temperature query with params: {start_timestamp}, {end_timestamp}")
        cursor.execute(temperature_query, (start_timestamp, end_timestamp))
        temperature = cursor.fetchall()
        logging.debug(f"Temperature query returned {len(temperature)} records. First record: {temperature[0] if temperature else 'None'}")
        
        # Signal Strength (SNR)
        snr_query = f"""
            SELECT 
                DATE_FORMAT(
                    DATE_ADD(
                        ts_created,
                        INTERVAL -MOD(MINUTE(ts_created), {bucket_size}) MINUTE
                    ),
                    '{time_format}'
                ) as time_slot,
                AVG(rx_snr) as avg_snr
            FROM message_reception
            WHERE ts_created >= %s AND ts_created <= %s
            GROUP BY time_slot
            ORDER BY time_slot
        """
        logging.debug(f"Executing SNR query with params: {start_timestamp}, {end_timestamp}")
        cursor.execute(snr_query, (start_timestamp, end_timestamp))
        snr = cursor.fetchall()
        logging.debug(f"SNR query returned {len(snr)} records. First record: {snr[0] if snr else 'None'}")
        
        cursor.close()
        
        # If we have no data, return a more informative response
        if not any([nodes_online, message_traffic, channel_util, battery_levels, temperature, snr]):
            logging.warning("No data found for any metrics in the specified time range")
            return jsonify({
                'error': 'No data available for the specified time range',
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'selected': time_range
                },
                'table_counts': {
                    'telemetry': telemetry_count,
                    'text': text_count,
                    'message_reception': reception_count
                },
                'data_ranges': {
                    'telemetry': {
                        'min': telemetry_time_range['min_time'].isoformat() if telemetry_time_range['min_time'] else None,
                        'max': telemetry_time_range['max_time'].isoformat() if telemetry_time_range['max_time'] else None
                    },
                    'text': {
                        'min': text_time_range['min_time'].isoformat() if text_time_range['min_time'] else None,
                        'max': text_time_range['max_time'].isoformat() if text_time_range['max_time'] else None
                    },
                    'message_reception': {
                        'min': reception_time_range['min_time'].isoformat() if reception_time_range['min_time'] else None,
                        'max': reception_time_range['max_time'].isoformat() if reception_time_range['max_time'] else None
                    }
                }
            })
        
        return jsonify({
            'nodes_online': {
                'labels': [row['time_slot'] for row in nodes_online],
                'data': [row['node_count'] for row in nodes_online]
            },
            'message_traffic': {
                'labels': [row['time_slot'] for row in message_traffic],
                'data': [row['message_count'] for row in message_traffic]
            },
            'channel_util': {
                'labels': [row['time_slot'] for row in channel_util],
                'data': [row['avg_util'] for row in channel_util]
            },
            'battery_levels': {
                'labels': [row['time_slot'] for row in battery_levels],
                'data': [row['avg_battery'] for row in battery_levels]
            },
            'temperature': {
                'labels': [row['time_slot'] for row in temperature],
                'data': [row['avg_temp'] for row in temperature]
            },
            'snr': {
                'labels': [row['time_slot'] for row in snr],
                'data': [row['avg_snr'] for row in snr]
            },
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'selected': time_range,
                'data_ranges': {
                    'telemetry': {
                        'min': telemetry_time_range['min_time'].isoformat() if telemetry_time_range['min_time'] else None,
                        'max': telemetry_time_range['max_time'].isoformat() if telemetry_time_range['max_time'] else None
                    },
                    'text': {
                        'min': text_time_range['min_time'].isoformat() if text_time_range['min_time'] else None,
                        'max': text_time_range['max_time'].isoformat() if text_time_range['max_time'] else None
                    },
                    'message_reception': {
                        'min': reception_time_range['min_time'].isoformat() if reception_time_range['min_time'] else None,
                        'max': reception_time_range['max_time'].isoformat() if reception_time_range['max_time'] else None
                    }
                }
            },
            'warnings': warnings
        })
    except Exception as e:
        logging.error(f"Error fetching metrics data: {str(e)}")
        return jsonify({
            'error': f'Error fetching metrics data: {str(e)}'
        }), 500

@app.route('/api/chattiest-nodes')
def get_chattiest_nodes():
    md = get_meshdata()
    if not md:  # Check if MeshData failed to initialize
        abort(503, description="Database connection unavailable")
    
    # Get filter parameters from request
    time_frame = request.args.get('time_frame', 'day')  # day, week, month, year, all
    message_type = request.args.get('message_type', 'all')  # all, text, position, telemetry
    
    try:
        cursor = md.db.cursor(dictionary=True)
        
        # Build the time frame condition
        time_condition = ""
        if time_frame == 'year':
            time_condition = "WHERE ts_created >= DATE_SUB(NOW(), INTERVAL 1 YEAR)"
        elif time_frame == 'month':
            time_condition = "WHERE ts_created >= DATE_SUB(NOW(), INTERVAL 1 MONTH)"
        elif time_frame == 'week':
            time_condition = "WHERE ts_created >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        elif time_frame == 'day':
            time_condition = "WHERE ts_created >= DATE_SUB(NOW(), INTERVAL 24 HOUR)"
        
        # Build the message type query based on the selected type
        if message_type == 'all':
            message_query = """
                SELECT from_id as node_id, ts_created
                FROM message_reception
                {time_condition}
            """.format(time_condition=time_condition)
        elif message_type == 'text':
            message_query = """
                SELECT from_id as node_id, ts_created
                FROM text
                {time_condition}
            """.format(time_condition=time_condition)
        elif message_type == 'position':
            message_query = """
                SELECT id as node_id, ts_created
                FROM positionlog
                {time_condition}
            """.format(time_condition=time_condition)
        elif message_type == 'telemetry':
            message_query = """
                SELECT id as node_id, ts_created
                FROM telemetry
                {time_condition}
            """.format(time_condition=time_condition)
        else:
            return jsonify({
                'error': f'Invalid message type: {message_type}'
            }), 400
        
        # Query to get the top 20 nodes by message count, including node names
        query = """
            WITH messages AS ({message_query})
            SELECT 
                m.node_id as from_id,
                n.long_name,
                n.short_name,
                COUNT(*) as message_count,
                COUNT(DISTINCT DATE_FORMAT(m.ts_created, '%Y-%m-%d')) as active_days,
                MIN(m.ts_created) as first_message,
                MAX(m.ts_created) as last_message
            FROM 
                messages m
            LEFT JOIN
                nodeinfo n ON m.node_id = n.id
            GROUP BY 
                m.node_id, n.long_name
            ORDER BY 
                message_count DESC
            LIMIT 20
        """.format(message_query=message_query)
        
        cursor.execute(query)
        chattiest_nodes = cursor.fetchall()
        cursor.close()
        
        # Format the data for the response
        formatted_nodes = []
        for node in chattiest_nodes:
            # Convert node ID to hex format for the link
            node_id_hex = utils.convert_node_id_from_int_to_hex(node['from_id'])
            
            formatted_nodes.append({
                'node_id': node['from_id'],
                'node_id_hex': node_id_hex,
                'long_name': node['long_name'] or f"Node {node['from_id']}",  # Fallback if no long name
                'short_name': node['short_name'] or f"Node {node['from_id']}",  # Fallback if no short name
                'message_count': node['message_count'],
                'active_days': node['active_days'],
                'first_message': node['first_message'].isoformat() if node['first_message'] else None,
                'last_message': node['last_message'].isoformat() if node['last_message'] else None
            })
        
        return jsonify({
            'chattiest_nodes': formatted_nodes,
            'filters': {
                'time_frame': time_frame,
                'message_type': message_type
            }
        })
    except Exception as e:
        logging.error(f"Error fetching chattiest nodes: {str(e)}")
        return jsonify({
            'error': f'Error fetching chattiest nodes: {str(e)}'
        }), 500

def run():
    # Enable Waitress logging
    config = configparser.ConfigParser()
    config.read('config.ini')
    port = int(config["webserver"]["port"])

    waitress_logger = logging.getLogger("waitress")
    waitress_logger.setLevel(logging.DEBUG)  # Enable all logs from Waitress
    #  serve(app, host="0.0.0.0", port=port)
    serve(
        TransLogger(
            app,
            setup_console_handler=False,
            logger=waitress_logger
        ),
        port=port
    )


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.ini')
    port = int(config["webserver"]["port"])
    app.run(debug=True, port=port)
