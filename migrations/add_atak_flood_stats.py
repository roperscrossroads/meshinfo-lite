#!/usr/bin/env python3
"""
Add ATAK flood statistics table
This migration creates a table to track periodic ATAK message flood patterns
"""

import logging
import sys
import os
import configparser

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meshdata import MeshData

def get_database_connection():
    """Get database connection using config"""
    config = configparser.ConfigParser()
    config.read('config.ini')

    try:
        mesh_data = MeshData()
        return mesh_data
    except Exception as e:
        logging.error(f"Failed to connect to database: {e}")
        return None

def migration_already_applied(mesh_data):
    """Check if migration has already been applied"""
    try:
        cursor = mesh_data.db.cursor()
        cursor.execute("DESCRIBE atak_flood_stats")
        cursor.fetchall()
        cursor.close()
        return True
    except Exception:
        return False

def apply_migration(mesh_data):
    """Apply the migration to add atak_flood_stats table"""
    try:
        cursor = mesh_data.db.cursor()

        # Create atak_flood_stats table
        create_table_sql = """
        CREATE TABLE atak_flood_stats (
            id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            minute_period DATETIME NOT NULL,
            atak_message_count INT NOT NULL DEFAULT 0,
            total_message_count INT NOT NULL DEFAULT 0,
            flood_percentage DECIMAL(5,2) NOT NULL DEFAULT 0.0,
            INDEX idx_minute_period (minute_period),
            INDEX idx_timestamp (timestamp)
        )
        """

        cursor.execute(create_table_sql)
        mesh_data.db.commit()
        cursor.close()

        logging.info("Successfully created atak_flood_stats table")
        return True

    except Exception as e:
        logging.error(f"Failed to create atak_flood_stats table: {e}")
        mesh_data.db.rollback()
        return False

def main():
    """Main migration function"""
    logging.basicConfig(level=logging.INFO)

    # Get database connection
    mesh_data = get_database_connection()
    if not mesh_data:
        logging.error("Could not establish database connection")
        sys.exit(1)

    # Check if migration already applied
    if migration_already_applied(mesh_data):
        logging.info("Migration already applied - atak_flood_stats table exists")
        return

    # Apply migration
    if apply_migration(mesh_data):
        logging.info("ATAK flood stats migration completed successfully")
    else:
        logging.error("ATAK flood stats migration failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
