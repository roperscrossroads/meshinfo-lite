import logging

def migrate(db):
    """
    Create relay_edges table for inferred relay network paths.
    """
    try:
        cursor = db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relay_edges (
                from_node VARCHAR(8) NOT NULL,
                relay_suffix VARCHAR(2) NOT NULL,
                to_node VARCHAR(8) NOT NULL,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                count INT DEFAULT 1,
                PRIMARY KEY (from_node, relay_suffix, to_node)
            )
        """)
        db.commit()
        logging.info("relay_edges table created or already exists.")
    except Exception as e:
        logging.error(f"Error creating relay_edges table: {e}")
        db.rollback()
        raise 