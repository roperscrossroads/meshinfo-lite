import logging

def migrate(db):
    """
    Add an auto-increment log_id column as the new primary key to the positionlog table,
    allowing duplicate (id, ts_created) entries. If log_id already exists, do nothing.
    Add a secondary index on (id, ts_created) for fast lookups.
    """
    try:
        cursor = db.cursor()
        # Check if log_id column already exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_NAME = 'positionlog'
            AND COLUMN_NAME = 'log_id'
        """)
        column_exists = cursor.fetchone()[0] > 0

        if not column_exists:
            logging.info("Adding log_id column to positionlog table...")
            # Drop old primary key
            cursor.execute("ALTER TABLE positionlog DROP PRIMARY KEY")
            # Add log_id as auto-increment primary key
            cursor.execute("""
                ALTER TABLE positionlog
                ADD COLUMN log_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST
            """)
            logging.info("Added log_id column as primary key to positionlog table.")
        else:
            logging.info("log_id column already exists in positionlog table.")

        # Add secondary index for (id, ts_created) if not exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.STATISTICS
            WHERE TABLE_NAME = 'positionlog'
            AND INDEX_NAME = 'idx_positionlog_id_ts'
        """)
        index_exists = cursor.fetchone()[0] > 0
        if not index_exists:
            cursor.execute("CREATE INDEX idx_positionlog_id_ts ON positionlog(id, ts_created)")
            logging.info("Added index idx_positionlog_id_ts on (id, ts_created) to positionlog table.")
        else:
            logging.info("Index idx_positionlog_id_ts already exists on positionlog table.")

        db.commit()
    except Exception as e:
        logging.error(f"Error adding log_id column to positionlog: {e}")
        raise
    finally:
        cursor.close() 