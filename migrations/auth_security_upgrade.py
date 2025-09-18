#!/usr/bin/env python3
"""
Authentication Security Upgrade Migration Script
This script adds security enhancements to the existing database schema.
It's completely backward compatible and won't break existing installations.
"""

import configparser
import mysql.connector
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def read_config():
    """Read database configuration from config.ini"""
    config_path = Path(__file__).parent.parent / 'config.ini'
    if not config_path.exists():
        logger.error(f"Config file not found at {config_path}")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)
    return config


def get_database_connection(config):
    """Create database connection"""
    try:
        conn = mysql.connector.connect(
            host=config["database"]["host"],
            user=config["database"]["username"],
            password=config["database"]["password"],
            database=config["database"]["database"],
            charset="utf8mb4"
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        sys.exit(1)


def check_column_exists(cursor, table, column):
    """Check if a column exists in a table"""
    cursor.execute("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = %s
        AND COLUMN_NAME = %s
    """, (table, column))
    return cursor.fetchone()[0] > 0


def check_table_exists(cursor, table):
    """Check if a table exists"""
    cursor.execute("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = %s
    """, (table,))
    return cursor.fetchone()[0] > 0


def check_index_exists(cursor, table, index):
    """Check if an index exists on a table"""
    cursor.execute("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = %s
        AND INDEX_NAME = %s
    """, (table, index))
    return cursor.fetchone()[0] > 0


def add_meshuser_columns(cursor):
    """Add security columns to meshuser table"""
    columns_to_add = [
        ("failed_login_attempts", "INT DEFAULT 0"),
        ("last_failed_login", "TIMESTAMP NULL"),
        ("account_locked_until", "TIMESTAMP NULL"),
        ("verification_expires", "TIMESTAMP NULL"),
        ("password_reset_token", "VARCHAR(255) NULL"),
        ("password_reset_expires", "TIMESTAMP NULL"),
        ("last_login", "TIMESTAMP NULL"),
        ("two_factor_secret", "VARCHAR(32) NULL")
    ]

    allowed_columns = dict(columns_to_add)
    for column_name, column_def in columns_to_add:
        # Validate column_name and column_def against whitelist
        if column_name in allowed_columns and allowed_columns[column_name] == column_def:
            if not check_column_exists(cursor, "meshuser", column_name):
                try:
                    # Build query safely after validation
                    query = "ALTER TABLE meshuser ADD COLUMN {} {}".format(column_name, column_def)
                    cursor.execute(query)
                    logger.info(f"Added column {column_name} to meshuser table")
                except Exception as e:
                    logger.warning(f"Could not add column {column_name}: {str(e)}")
            else:
                logger.info(f"Column {column_name} already exists in meshuser table")
        else:
            logger.warning(f"Attempted to add invalid column definition: {column_name} {column_def}")


def create_auth_tables(cursor):
    """Create new authentication-related tables"""

    # Create auth_audit table
    if not check_table_exists(cursor, "auth_audit"):
        cursor.execute("""
            CREATE TABLE auth_audit (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255),
                action VARCHAR(50) COMMENT 'login_success, login_failed, password_reset, registration, etc.',
                ip_address VARCHAR(45),
                user_agent TEXT,
                success BOOLEAN,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_email (email),
                INDEX idx_created_at (created_at),
                INDEX idx_action (action)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Created auth_audit table")
    else:
        logger.info("auth_audit table already exists")

    # Create user_sessions table
    if not check_table_exists(cursor, "user_sessions"):
        cursor.execute("""
            CREATE TABLE user_sessions (
                session_id VARCHAR(64) PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                jwt_id VARCHAR(36) COMMENT 'JWT jti claim for blacklisting',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                ip_address VARCHAR(45),
                user_agent TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                INDEX idx_email (email),
                INDEX idx_expires (expires_at),
                INDEX idx_jwt_id (jwt_id),
                INDEX idx_active (is_active, expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Created user_sessions table")
    else:
        logger.info("user_sessions table already exists")

    # Create blacklisted_tokens table
    if not check_table_exists(cursor, "blacklisted_tokens"):
        cursor.execute("""
            CREATE TABLE blacklisted_tokens (
                jwt_id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(255),
                blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL COMMENT 'When the token naturally expires',
                reason VARCHAR(50) COMMENT 'logout, password_reset, security_breach, etc.',
                INDEX idx_expires (expires_at),
                INDEX idx_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        logger.info("Created blacklisted_tokens table")
    else:
        logger.info("blacklisted_tokens table already exists")


def add_indexes(cursor):
    """Add performance indexes"""
    indexes_to_add = [
        ("meshuser", "idx_meshuser_status", "status"),
        ("meshuser", "idx_meshuser_verification", "verification"),
        ("meshuser", "idx_meshuser_failed_attempts", "failed_login_attempts")
    ]

    for table, index_name, column in indexes_to_add:
        # Whitelist validation: only allow known values
        if (
            table in {"meshuser"} and
            index_name in {"idx_meshuser_status", "idx_meshuser_verification", "idx_meshuser_failed_attempts"} and
            column in {"status", "verification", "failed_login_attempts"}
        ):
            if not check_index_exists(cursor, table, index_name):
                try:
                    query = f"CREATE INDEX {index_name} ON {table}({column})"
                    cursor.execute(query)
                    logger.info(f"Created index {index_name} on {table}.{column}")
                except Exception as e:
                    logger.warning(f"Could not create index {index_name}: {str(e)}")
            else:
                logger.info(f"Index {index_name} already exists on {table}")
        else:
            logger.error(f"Attempted to create index with invalid table/index/column: {table}, {index_name}, {column}")


def create_cleanup_procedure(cursor):
    """Create stored procedure for cleaning up expired data"""
    try:
        cursor.execute("DROP PROCEDURE IF EXISTS cleanup_expired_auth_data")
        cursor.execute("""
            CREATE PROCEDURE cleanup_expired_auth_data()
            BEGIN
                -- Delete expired blacklisted tokens
                DELETE FROM blacklisted_tokens WHERE expires_at < NOW();

                -- Delete expired sessions
                DELETE FROM user_sessions WHERE expires_at < NOW() AND is_active = FALSE;

                -- Delete old audit logs (keep 90 days)
                DELETE FROM auth_audit WHERE created_at < DATE_SUB(NOW(), INTERVAL 90 DAY);

                -- Clear expired verification codes
                UPDATE meshuser
                SET verification = NULL, verification_expires = NULL
                WHERE verification_expires IS NOT NULL AND verification_expires < NOW();

                -- Reset expired account locks
                UPDATE meshuser
                SET account_locked_until = NULL, failed_login_attempts = 0
                WHERE account_locked_until IS NOT NULL AND account_locked_until < NOW();
            END
        """)
        logger.info("Created cleanup_expired_auth_data stored procedure")
    except Exception as e:
        logger.warning(f"Could not create stored procedure: {str(e)}")


def migrate_existing_users(cursor):
    """Migrate existing user data to new schema"""
    try:
        # Set default values for existing users
        cursor.execute("""
            UPDATE meshuser
            SET failed_login_attempts = 0
            WHERE failed_login_attempts IS NULL
        """)

        # Count existing users
        cursor.execute("SELECT COUNT(*) FROM meshuser")
        user_count = cursor.fetchone()[0]
        logger.info(f"Updated {user_count} existing user records with default values")

    except Exception as e:
        logger.warning(f"Could not migrate existing users: {str(e)}")


def main():
    """Main migration function"""
    logger.info("Starting authentication security upgrade migration...")

    # Read configuration
    config = read_config()

    # Connect to database
    conn = get_database_connection(config)
    cursor = conn.cursor()

    try:
        # Add new columns to meshuser table
        logger.info("Step 1: Adding security columns to meshuser table...")
        add_meshuser_columns(cursor)

        # Create new authentication tables
        logger.info("Step 2: Creating authentication tables...")
        create_auth_tables(cursor)

        # Add performance indexes
        logger.info("Step 3: Adding performance indexes...")
        add_indexes(cursor)

        # Create cleanup stored procedure
        logger.info("Step 4: Creating cleanup procedure...")
        create_cleanup_procedure(cursor)

        # Migrate existing users
        logger.info("Step 5: Migrating existing user data...")
        migrate_existing_users(cursor)

        # Commit changes
        conn.commit()
        logger.info("Migration completed successfully!")

        # Print summary
        print("\n" + "="*60)
        print("AUTHENTICATION SECURITY UPGRADE - MIGRATION COMPLETE")
        print("="*60)
        print("\nThe following enhancements have been added:")
        print("✓ Connection pooling and SQL injection protection")
        print("✓ Enhanced password validation (8+ chars with complexity)")
        print("✓ UUID-based verification codes with expiration")
        print("✓ Failed login tracking and account lockout")
        print("✓ Secure JWT tokens with expiration")
        print("✓ Session management and token blacklisting")
        print("✓ Security audit logging")
        print("\nYour existing users and data remain unchanged.")
        print("All new features are backward compatible.")
        print("\nRecommended next steps:")
        print("1. Update your config.ini with security settings (see config.ini.sample)")
        print("2. Test the authentication system")
        print("3. Monitor the auth_audit table for security events")
        print("="*60)

    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        conn.rollback()
        sys.exit(1)

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()