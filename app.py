@app.route('/metrics.html')
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
    db = MeshData()
    
    # Get the last 24 hours of data
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)
    
    # Nodes Online (per hour)
    nodes_online = db.execute("""
        SELECT 
            strftime('%Y-%m-%d %H:00', datetime(timestamp, 'unixepoch')) as hour,
            COUNT(DISTINCT id) as node_count
        FROM telemetry
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY hour
        ORDER BY hour
    """, (int(start_time.timestamp()), int(end_time.timestamp())))
    
    # Message Traffic (per hour)
    message_traffic = db.execute("""
        SELECT 
            strftime('%Y-%m-%d %H:00', datetime(timestamp, 'unixepoch')) as hour,
            COUNT(*) as message_count
        FROM text
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY hour
        ORDER BY hour
    """, (int(start_time.timestamp()), int(end_time.timestamp())))
    
    # Channel Utilization
    channel_util = db.execute("""
        SELECT 
            strftime('%Y-%m-%d %H:00', datetime(timestamp, 'unixepoch')) as hour,
            AVG(channel_utilization) as avg_util
        FROM telemetry
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY hour
        ORDER BY hour
    """, (int(start_time.timestamp()), int(end_time.timestamp())))
    
    # Battery Levels (for each node)
    battery_levels = db.execute("""
        SELECT 
            id,
            strftime('%Y-%m-%d %H:00', datetime(timestamp, 'unixepoch')) as hour,
            AVG(battery_level) as avg_battery
        FROM telemetry
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY id, hour
        ORDER BY hour
    """, (int(start_time.timestamp()), int(end_time.timestamp())))
    
    # Temperature Readings
    temperature = db.execute("""
        SELECT 
            id,
            strftime('%Y-%m-%d %H:00', datetime(timestamp, 'unixepoch')) as hour,
            AVG(temperature) as avg_temp
        FROM telemetry
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY id, hour
        ORDER BY hour
    """, (int(start_time.timestamp()), int(end_time.timestamp())))
    
    # Signal Strength (SNR)
    snr = db.execute("""
        SELECT 
            strftime('%Y-%m-%d %H:00', datetime(timestamp, 'unixepoch')) as hour,
            AVG(snr) as avg_snr
        FROM message_reception
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY hour
        ORDER BY hour
    """, (int(start_time.timestamp()), int(end_time.timestamp())))
    
    # Process battery levels data
    battery_data = {}
    for row in battery_levels:
        if row['id'] not in battery_data:
            battery_data[row['id']] = {'hours': [], 'levels': []}
        battery_data[row['id']]['hours'].append(row['hour'])
        battery_data[row['id']]['levels'].append(row['avg_battery'])
    
    # Process temperature data
    temp_data = {}
    for row in temperature:
        if row['id'] not in temp_data:
            temp_data[row['id']] = {'hours': [], 'temps': []}
        temp_data[row['id']]['hours'].append(row['hour'])
        temp_data[row['id']]['temps'].append(row['avg_temp'])
    
    return jsonify({
        'nodes_online': {
            'labels': [row['hour'] for row in nodes_online],
            'data': [row['node_count'] for row in nodes_online]
        },
        'message_traffic': {
            'labels': [row['hour'] for row in message_traffic],
            'data': [row['message_count'] for row in message_traffic]
        },
        'channel_util': {
            'labels': [row['hour'] for row in channel_util],
            'data': [row['avg_util'] for row in channel_util]
        },
        'battery_levels': {
            'labels': list(set([hour for data in battery_data.values() for hour in data['hours']])),
            'datasets': [
                {
                    'node_id': node_id,
                    'data': data['levels']
                }
                for node_id, data in battery_data.items()
            ]
        },
        'temperature': {
            'labels': list(set([hour for data in temp_data.values() for hour in data['hours']])),
            'datasets': [
                {
                    'node_id': node_id,
                    'data': data['temps']
                }
                for node_id, data in temp_data.items()
            ]
        },
        'snr': {
            'labels': [row['hour'] for row in snr],
            'data': [row['avg_snr'] for row in snr]
        }
    }) 