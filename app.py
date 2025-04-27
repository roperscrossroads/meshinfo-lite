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
    node_activity_prune_threshold = int(config.get('server', 'node_activity_prune_threshold', fallback=7200))
    metrics_avg_interval = int(config.get('server', 'metrics_average_interval', fallback=7200))
    metrics_avg_minutes = metrics_avg_interval // 60

    db = MeshData()
    # Get the last 24 hours of data, but extend for smoothing
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)
    extra_minutes = metrics_avg_minutes // 2
    extended_start_time = start_time - timedelta(minutes=extra_minutes)
    extended_end_time = end_time + timedelta(minutes=extra_minutes)

    # Nodes Online (per hour)
    nodes_online = db.execute("""
        SELECT 
            strftime('%Y-%m-%d %H:00', datetime(timestamp, 'unixepoch')) as hour,
            COUNT(DISTINCT id) as node_count
        FROM telemetry
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY hour
        ORDER BY hour
    """, (int(extended_start_time.timestamp()), int(extended_end_time.timestamp())))
    
    # Message Traffic (per hour)
    message_traffic = db.execute("""
        SELECT 
            strftime('%Y-%m-%d %H:00', datetime(timestamp, 'unixepoch')) as hour,
            COUNT(*) as message_count
        FROM text
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY hour
        ORDER BY hour
    """, (int(extended_start_time.timestamp()), int(extended_end_time.timestamp())))
    
    # Channel Utilization
    channel_util = db.execute("""
        SELECT 
            strftime('%Y-%m-%d %H:00', datetime(timestamp, 'unixepoch')) as hour,
            AVG(channel_utilization) as avg_util
        FROM telemetry
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY hour
        ORDER BY hour
    """, (int(extended_start_time.timestamp()), int(extended_end_time.timestamp())))
    
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
    """, (int(extended_start_time.timestamp()), int(extended_end_time.timestamp())))
    
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
    """, (int(extended_start_time.timestamp()), int(extended_end_time.timestamp())))
    
    # Signal Strength (SNR)
    snr = db.execute("""
        SELECT 
            strftime('%Y-%m-%d %H:00', datetime(timestamp, 'unixepoch')) as hour,
            AVG(snr) as avg_snr
        FROM message_reception
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY hour
        ORDER BY hour
    """, (int(extended_start_time.timestamp()), int(extended_end_time.timestamp())))
    
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
    
    # Build extended labels and data for nodes_online
    extended_labels = [row['hour'] for row in nodes_online]
    extended_data = [row['node_count'] for row in nodes_online]

    # Moving average helper (centered)
    def moving_average_centered(data, window):
        n = len(data)
        result = []
        half = window // 2
        for i in range(n):
            left = max(0, i - half)
            right = min(n, i + half + 1)
            window_data = data[left:right]
            result.append(sum(window_data) / len(window_data))
        return result

    # Apply smoothing to extended data
    window_buckets = max(1, metrics_avg_minutes // 60)
    smoothed_data = moving_average_centered(extended_data, window_buckets)

    # Trim to original 24-hour window
    trimmed_labels = []
    trimmed_data = []
    for label, value in zip(extended_labels, smoothed_data):
        label_dt = datetime.strptime(label, '%Y-%m-%d %H:%M')
        if start_time <= label_dt <= end_time:
            trimmed_labels.append(label)
            trimmed_data.append(value)

    return jsonify({
        'nodes_online': {
            'labels': trimmed_labels,
            'data': trimmed_data
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