import logging

def migrate(db):
    """
    Add indexes to improve message map performance:
    - Index on positionlog for faster position lookups (if not already added by add_positionlog_log_id)
    - Index on message_reception for faster reception detail lookups
    """
    try:
        cursor = db.cursor()
        
        # Check if positionlog index already exists (might have been added by add_positionlog_log_id)
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
            AND table_name = 'positionlog'
            AND index_name = 'idx_positionlog_id_ts'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE INDEX idx_positionlog_id_ts 
                ON positionlog(id, ts_created)
            """)
            logging.info("Added index idx_positionlog_id_ts to positionlog table")
        else:
            logging.info("Index idx_positionlog_id_ts already exists on positionlog table")
        
        # Add index for reception lookups if it doesn't exist
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
            AND table_name = 'message_reception'
            AND index_name = 'idx_messagereception_message_receiver'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                CREATE INDEX idx_messagereception_message_receiver 
                ON message_reception(message_id, received_by_id)
            """)
            logging.info("Added index idx_messagereception_message_receiver to message_reception table")
        else:
            logging.info("Index idx_messagereception_message_receiver already exists on message_reception table")
        
        db.commit()
        logging.info("Successfully added message map performance indexes")
        
    except Exception as e:
        db.rollback()
        logging.error(f"Failed to add message map indexes: {str(e)}")
        raise 