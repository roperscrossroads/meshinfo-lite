def ensure_packet_id_column(cur, table_name='telemetry'):
    cur.execute(f"SHOW COLUMNS FROM {table_name} LIKE 'packet_id';")
    if not cur.fetchone():
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN packet_id BIGINT;")

def migrate(db):
    cur = db.cursor()
    # Ensure packet_id column exists before any operation
    ensure_packet_id_column(cur, 'telemetry')

    # Get column names for telemetry table, excluding 'rn' if present
    cur.execute("SHOW COLUMNS FROM telemetry;")
    columns = [row[0] for row in cur.fetchall() if row[0] != 'rn']
    colnames = ', '.join(columns)

    # Drop intermediate tables if they exist (idempotency)
    cur.execute("DROP TABLE IF EXISTS telemetry_new;")
    # Create intermediate table with same schema
    cur.execute("CREATE TABLE telemetry_new LIKE telemetry;")
    ensure_packet_id_column(cur, 'telemetry_new')
    # Deduplicate by (id, telemetry_time)
    cur.execute(f"""
        INSERT INTO telemetry_new ({colnames})
        SELECT {colnames} FROM (
            SELECT {colnames}, ROW_NUMBER() OVER (PARTITION BY id, telemetry_time ORDER BY ts_created ASC) AS rn
            FROM telemetry
        ) t
        WHERE rn = 1;
    """)
    cur.execute("TRUNCATE telemetry;")
    ensure_packet_id_column(cur, 'telemetry')
    cur.execute(f"INSERT INTO telemetry ({colnames}) SELECT {colnames} FROM telemetry_new;")
    cur.execute("DROP TABLE telemetry_new;")

    # Set packet_id to a synthetic value with randomness for legacy rows
    cur.execute("""
        UPDATE telemetry
        SET packet_id = id + UNIX_TIMESTAMP(telemetry_time) + FLOOR(RAND() * 1000000)
        WHERE packet_id IS NULL;
    """)

    # Drop intermediate tables if they exist (idempotency)
    cur.execute("DROP TABLE IF EXISTS telemetry_new2;")
    # Create intermediate table with same schema
    cur.execute("CREATE TABLE telemetry_new2 LIKE telemetry;")
    ensure_packet_id_column(cur, 'telemetry_new2')
    # Final deduplication by (id, packet_id)
    cur.execute(f"""
        INSERT INTO telemetry_new2 ({colnames})
        SELECT {colnames} FROM (
            SELECT {colnames}, ROW_NUMBER() OVER (PARTITION BY id, packet_id ORDER BY ts_created ASC) AS rn
            FROM telemetry
        ) t
        WHERE rn = 1;
    """)
    cur.execute("TRUNCATE telemetry;")
    ensure_packet_id_column(cur, 'telemetry')
    cur.execute(f"INSERT INTO telemetry ({colnames}) SELECT {colnames} FROM telemetry_new2;")
    cur.execute("DROP TABLE telemetry_new2;")

    # Add unique constraint on (id, packet_id)
    try:
        cur.execute("""
            ALTER TABLE telemetry
            ADD UNIQUE KEY unique_telemetry (id, packet_id);
        """)
    except Exception as e:
        # If the unique key already exists, ignore
        if 'Duplicate key name' not in str(e):
            raise
    cur.close() 
    