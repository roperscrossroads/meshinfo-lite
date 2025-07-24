import logging
import configparser

def migrate(db):
    """
    Migrate database to add relay_node column to message_reception table
    """
    try:
        cursor = db.cursor()
        
        # Ensure we're in the correct database
        cursor.execute("SELECT DATABASE()")
        current_db = cursor.fetchone()[0]
        if not current_db:
            raise Exception("No database selected")
        
        # Check if message_reception table exists
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.TABLES 
            WHERE TABLE_NAME = 'message_reception'
        """)
        has_reception_table = cursor.fetchone()[0] > 0
        
        if not has_reception_table:
            logging.info("message_reception table does not exist, skipping relay_node column addition")
            return
            
        # Check if relay_node column exists in message_reception table
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS 
            WHERE TABLE_NAME = 'message_reception'
            AND COLUMN_NAME = 'relay_node'
        """)
        has_relay_node = cursor.fetchone()[0] > 0

        if not has_relay_node:
            logging.info("Adding relay_node column to message_reception table...")
            cursor.execute("""
                ALTER TABLE message_reception
                ADD COLUMN relay_node VARCHAR(4) DEFAULT NULL,
                ADD INDEX idx_message_reception_relay_node (relay_node)
            """)
            db.commit()
            logging.info("Added relay_node column successfully")
        else:
            logging.info("relay_node column already exists in message_reception table")
            
    except Exception as e:
        logging.error(f"Error during relay_node migration: {e}")
        db.rollback()
        raise 