import logging

def ensure_packet_id_column(cur, table_name='telemetry'):
    cur.execute(f"SHOW COLUMNS FROM {table_name} LIKE 'packet_id';")
    if not cur.fetchone():
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN packet_id BIGINT;")

def check_migration_completed(cur):
    """Check if this migration has already been completed"""
    # Check if unique constraint exists
    cur.execute("""
        SELECT COUNT(*)
        FROM information_schema.STATISTICS
        WHERE TABLE_NAME = 'telemetry'
        AND INDEX_NAME = 'unique_telemetry'
    """)
    has_unique_constraint = cur.fetchone()[0] > 0
    
    # Check if all rows have packet_id values
    cur.execute("SELECT COUNT(*) FROM telemetry WHERE packet_id IS NULL")
    has_null_packet_ids = cur.fetchone()[0] > 0
    
    return has_unique_constraint and not has_null_packet_ids

def migrate(db):
    cur = db.cursor()
    
    # Check if migration has already been completed
    if check_migration_completed(cur):
        logging.info("Telemetry packet_id migration already completed, skipping...")
        cur.close()
        return
    
    logging.info("Starting telemetry packet_id migration...")
    
    # Ensure packet_id column exists before any operation
    ensure_packet_id_column(cur, 'telemetry')

    # Get column names for telemetry table, excluding 'rn' if present
    cur.execute("SHOW COLUMNS FROM telemetry;")
    columns = [row[0] for row in cur.fetchall() if row[0] != 'rn']
    colnames = ', '.join(columns)

    # Check if we need to deduplicate by (id, telemetry_time)
    cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT id, telemetry_time, COUNT(*) as cnt
            FROM telemetry
            GROUP BY id, telemetry_time
            HAVING cnt > 1
        ) t
    """)
    has_duplicates_by_time = cur.fetchone()[0] > 0
    
    if has_duplicates_by_time:
        logging.info("Deduplicating telemetry by (id, telemetry_time)...")
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
        logging.info("Deduplication by (id, telemetry_time) completed")

    # Set packet_id to a synthetic value with randomness for legacy rows
    cur.execute("SELECT COUNT(*) FROM telemetry WHERE packet_id IS NULL")
    null_packet_ids = cur.fetchone()[0]
    
    if null_packet_ids > 0:
        logging.info(f"Setting packet_id for {null_packet_ids} rows...")
        cur.execute("""
            UPDATE telemetry
            SET packet_id = id + UNIX_TIMESTAMP(telemetry_time) + FLOOR(RAND() * 1000000)
            WHERE packet_id IS NULL;
        """)
        logging.info("packet_id values set successfully")

    # Check if we need to deduplicate by (id, packet_id)
    cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT id, packet_id, COUNT(*) as cnt
            FROM telemetry
            WHERE packet_id IS NOT NULL
            GROUP BY id, packet_id
            HAVING cnt > 1
        ) t
    """)
    has_duplicates_by_packet_id = cur.fetchone()[0] > 0
    
    if has_duplicates_by_packet_id:
        logging.info("Deduplicating telemetry by (id, packet_id)...")
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
        logging.info("Deduplication by (id, packet_id) completed")

    # Add unique constraint on (id, packet_id)
    try:
        cur.execute("""
            ALTER TABLE telemetry
            ADD UNIQUE KEY unique_telemetry (id, packet_id);
        """)
        logging.info("Added unique constraint on (id, packet_id)")
    except Exception as e:
        # If the unique key already exists, ignore
        if 'Duplicate key name' not in str(e):
            raise
    
    logging.info("Telemetry packet_id migration completed successfully")
    cur.close() 
    