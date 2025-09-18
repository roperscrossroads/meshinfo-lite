#!/usr/bin/env python3
"""
Docker Setup Script for MeshInfo-Lite

This script sets up the database with proper privileges for Docker Compose installations.
It should be run after the Docker containers are started.

Usage:
    python setup_docker.py
    python setup_docker.py --startup

Requirements:
    - Docker Compose services running
    - config.ini file with database configuration
"""

import configparser
import logging
import sys
import os
import time

# Import mysql.connector only when needed to avoid import errors during --help
def get_mysql_connector():
    try:
        import mysql.connector
        return mysql.connector
    except ImportError:
        logging.error("mysql.connector package is required but not installed.")
        logging.error("Please install it with: pip install mysql-connector-python")
        sys.exit(1)

def setup_logging():
    """Setup basic logging for the setup script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def check_config():
    """Check if config.ini exists and has required database settings."""
    if not os.path.exists('config.ini'):
        logging.error("config.ini not found! Please create it first.")
        return False
    
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    required_sections = ['database']
    required_keys = ['host', 'username', 'password', 'database']
    
    for section in required_sections:
        if section not in config:
            logging.error(f"Missing [{section}] section in config.ini")
            return False
        
        for key in required_keys:
            if key not in config[section]:
                logging.error(f"Missing {key} in [{section}] section of config.ini")
                return False
    
    return True

def wait_for_database(config, max_attempts=30):
    """Wait for the database to become available."""
    mysql_connector = get_mysql_connector()
    logging.info("Waiting for database to become available...")
    
    for attempt in range(max_attempts):
        try:
            # Try to connect as root first
            root_password = config.get("database", "root_password", fallback="passw0rd")
            db = mysql_connector.connect(
                host=config["database"]["host"],
                user="root",
                password=root_password,
                connection_timeout=5
            )
            db.close()
            logging.info("✓ Database is available")
            return True
        except mysql_connector.Error as e:
            if attempt < max_attempts - 1:
                logging.info(f"Database not ready yet (attempt {attempt + 1}/{max_attempts})...")
                time.sleep(2)
            else:
                logging.error(f"Database failed to become available: {e}")
                return False
    
    return False

def setup_database_privileges(config):
    """Set up database privileges for the application user."""
    mysql_connector = get_mysql_connector()
    root_password = config.get("database", "root_password", fallback="passw0rd")
    
    try:
        # Connect as root
        db = mysql_connector.connect(
            host=config["database"]["host"],
            user="root",
            password=root_password,
        )
        
        logging.info("Setting up database privileges...")
        
        # Grant RELOAD privilege for query cache operations
        cur = db.cursor()
        cur.execute(f"""GRANT RELOAD ON *.* TO '{config["database"]["username"]}'@'%'""")
        cur.close()
        logging.info("✓ Granted RELOAD privilege for query cache operations")
        
        # Grant PROCESS privilege for monitoring
        cur = db.cursor()
        cur.execute(f"""GRANT PROCESS ON *.* TO '{config["database"]["username"]}'@'%'""")
        cur.close()
        logging.info("✓ Granted PROCESS privilege for monitoring")
        
        # Flush privileges to apply changes
        cur = db.cursor()
        cur.execute("FLUSH PRIVILEGES")
        cur.close()
        logging.info("✓ Privileges flushed")
        
        db.commit()
        db.close()
        
        logging.info("✓ Database privileges setup completed successfully!")
        return True
        
    except mysql_connector.Error as e:
        logging.error(f"Error setting up database privileges: {e}")
        return False

def test_user_connection(config):
    """Test connection with the application user."""
    mysql_connector = get_mysql_connector()
    try:
        db = mysql_connector.connect(
            host=config["database"]["host"],
            user=config["database"]["username"],
            password=config["database"]["password"],
            database=config["database"]["database"],
        )
        db.close()
        logging.info("✓ Successfully connected with application user")
        return True
    except mysql_connector.Error as e:
        logging.error(f"Failed to connect with application user: {e}")
        return False

def test_privileges(config):
    """Test if the user has the required privileges."""
    mysql_connector = get_mysql_connector()
    try:
        db = mysql_connector.connect(
            host=config["database"]["host"],
            user=config["database"]["username"],
            password=config["database"]["password"],
            database=config["database"]["database"],
        )
        cur = db.cursor()
        
        # Test RELOAD privilege
        try:
            cur.execute("FLUSH QUERY CACHE")
            logging.info("✓ RELOAD privilege verified")
        except mysql_connector.Error as e:
            logging.warning(f"RELOAD privilege test failed: {e}")
        
        # Test PROCESS privilege
        try:
            cur.execute("SHOW PROCESSLIST")
            logging.info("✓ PROCESS privilege verified")
        except mysql_connector.Error as e:
            logging.warning(f"PROCESS privilege test failed: {e}")
        
        cur.close()
        db.close()
        return True
        
    except mysql_connector.Error as e:
        logging.error(f"Error testing privileges: {e}")
        return False

def main():
    """Main setup function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup database privileges for MeshInfo-Lite")
    parser.add_argument("--startup", action="store_true", 
                       help="Run in startup mode (non-failing, suitable for container initialization)")
    args = parser.parse_args()
    
    setup_logging()
    
    logging.info("=== MeshInfo-Lite Docker Setup ===")
    
    # Check configuration
    if not check_config():
        if args.startup:
            logging.warning("Configuration check failed, but continuing in startup mode")
            return
        sys.exit(1)
    
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    # Wait for database to become available
    if not wait_for_database(config):
        if args.startup:
            logging.warning("Database is not available, but continuing in startup mode")
            logging.warning("The application will start but may have limited functionality")
            return
        logging.error("Database is not available. Please ensure Docker Compose services are running.")
        logging.error("Run: docker-compose up -d")
        sys.exit(1)
    
    # Set up database privileges
    if not setup_database_privileges(config):
        if args.startup:
            logging.warning("Database privilege setup failed, but continuing in startup mode")
            return
        sys.exit(1)
    
    # Test user connection
    if not test_user_connection(config):
        if args.startup:
            logging.warning("User connection test failed, but continuing in startup mode")
            return
        logging.error("Setup completed but user connection test failed")
        sys.exit(1)
    
    # Test privileges
    test_privileges(config)
    
    logging.info("=== Docker Setup Complete ===")
    logging.info("The MeshInfo-Lite application should now have full functionality")
    if not args.startup:
        logging.info("Check the application logs for any remaining issues")

if __name__ == "__main__":
    main() 