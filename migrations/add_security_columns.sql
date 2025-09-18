-- Migration script to add security columns to existing databases
-- This script is backward compatible and will not break existing installations

-- Add security columns to meshuser table (if they don't exist)
ALTER TABLE meshuser
ADD COLUMN IF NOT EXISTS failed_login_attempts INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_failed_login TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS account_locked_until TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS verification_expires TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255) NULL,
ADD COLUMN IF NOT EXISTS password_reset_expires TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS last_login TIMESTAMP NULL,
ADD COLUMN IF NOT EXISTS two_factor_secret VARCHAR(32) NULL;

-- Create auth audit log table for security events
CREATE TABLE IF NOT EXISTS auth_audit (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create session management table for JWT tracking
CREATE TABLE IF NOT EXISTS user_sessions (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create blacklisted tokens table for logout functionality
CREATE TABLE IF NOT EXISTS blacklisted_tokens (
    jwt_id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255),
    blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL COMMENT 'When the token naturally expires',
    reason VARCHAR(50) COMMENT 'logout, password_reset, security_breach, etc.',
    INDEX idx_expires (expires_at),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add indexes for better performance on existing columns
CREATE INDEX IF NOT EXISTS idx_meshuser_status ON meshuser(status);
CREATE INDEX IF NOT EXISTS idx_meshuser_verification ON meshuser(verification);
CREATE INDEX IF NOT EXISTS idx_meshuser_failed_attempts ON meshuser(failed_login_attempts);

-- Create stored procedure for cleaning up expired data (optional)
DELIMITER //

CREATE PROCEDURE IF NOT EXISTS cleanup_expired_auth_data()
BEGIN
    -- Delete expired blacklisted tokens
    DELETE FROM blacklisted_tokens WHERE expires_at < NOW();

    -- Delete expired sessions
    DELETE FROM user_sessions WHERE expires_at < NOW() AND is_active = FALSE;

    -- Delete old audit logs (keep 90 days)
    DELETE FROM auth_audit WHERE created_at < DATE_SUB(NOW(), INTERVAL 90 DAY);

    -- Clear expired verification codes (if verification_expires is populated)
    UPDATE meshuser
    SET verification = NULL, verification_expires = NULL
    WHERE verification_expires IS NOT NULL AND verification_expires < NOW();

    -- Reset expired account locks
    UPDATE meshuser
    SET account_locked_until = NULL, failed_login_attempts = 0
    WHERE account_locked_until IS NOT NULL AND account_locked_until < NOW();
END//

DELIMITER ;

-- Create event to run cleanup daily (optional - requires EVENT scheduler)
-- Uncomment if you want automatic cleanup
-- CREATE EVENT IF NOT EXISTS auth_cleanup_event
-- ON SCHEDULE EVERY 1 DAY
-- STARTS CURRENT_TIMESTAMP
-- DO CALL cleanup_expired_auth_data();

-- Grant necessary permissions (adjust username as needed)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON meshdata.auth_audit TO 'meshdata'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON meshdata.user_sessions TO 'meshdata'@'%';
-- GRANT SELECT, INSERT, UPDATE, DELETE ON meshdata.blacklisted_tokens TO 'meshdata'@'%';