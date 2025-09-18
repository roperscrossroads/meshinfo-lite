import configparser
import mysql.connector
import mysql.connector.pooling
from contextlib import contextmanager
import bcrypt
import utils
import re
import jwt
import time
import datetime
import logging
import uuid
import secrets

logger = logging.getLogger(__name__)


class Register:
    _pool = None

    def __init__(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.config = config
        # Initialize connection pool on first use
        if not Register._pool:
            Register._pool = self._create_pool()

    def _create_pool(self):
        """Create a connection pool for database connections."""
        try:
            return mysql.connector.pooling.MySQLConnectionPool(
                pool_name="auth_pool",
                pool_size=5,
                pool_reset_session=True,
                host=self.config["database"]["host"],
                user=self.config["database"]["username"],
                password=self.config["database"]["password"],
                database=self.config["database"]["database"],
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
                autocommit=False,
                use_unicode=True
            )
        except Exception as e:
            logger.error(f"Failed to create connection pool: {str(e)}")
            # Fallback to single connection if pool fails
            return None

    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            if Register._pool:
                conn = Register._pool.get_connection()
            else:
                # Fallback to direct connection if pool not available
                conn = mysql.connector.connect(
                    host=self.config["database"]["host"],
                    user=self.config["database"]["username"],
                    password=self.config["database"]["password"],
                    database=self.config["database"]["database"],
                    charset="utf8mb4"
                )

            # Set UTF8MB4 for proper Unicode support
            cursor = conn.cursor()
            cursor.execute("SET NAMES utf8mb4")
            cursor.close()

            yield conn

        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    def validate_password(self, password):
        """
        Validates password against security requirements.
        Returns (bool, str) - (is_valid, error_message)
        """
        # Check if security settings are configured
        try:
            if self.config.has_section('security'):
                min_length = int(self.config.get('security', 'password_min_length', fallback='8'))
                require_upper = self.config.getboolean('security', 'password_require_uppercase', fallback=True)
                require_lower = self.config.getboolean('security', 'password_require_lowercase', fallback=True)
                require_numbers = self.config.getboolean('security', 'password_require_numbers', fallback=True)
                require_special = self.config.getboolean('security', 'password_require_special', fallback=True)
            else:
                # Default security settings
                min_length = 8
                require_upper = True
                require_lower = True
                require_numbers = True
                require_special = True
        except:
            # Fallback to secure defaults if config parsing fails
            min_length = 8
            require_upper = True
            require_lower = True
            require_numbers = True
            require_special = True

        if len(password) < min_length:
            return False, f"Password must be at least {min_length} characters long"
        if require_upper and not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        if require_lower and not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        if require_numbers and not re.search(r'\d', password):
            return False, "Password must contain at least one number"
        if require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"

        return True, ""

    def generate_verification_code(self):
        """
        Generate a secure verification code.
        Uses UUID for new registrations, maintaining backward compatibility.
        """
        # Check if we should use legacy 4-char codes (for backward compatibility)
        use_legacy = self.config.getboolean('security', 'use_legacy_verification', fallback=False) \
                     if self.config.has_section('security') else False

        if use_legacy:
            return utils.generate_random_code(4)
        else:
            # Use secure UUID-based verification
            return str(uuid.uuid4())

    def verify(self, username, email):
        """Check if username or email already exists."""
        with self.get_db_connection() as conn:
            cur = conn.cursor()
            sql = "SELECT 1 FROM meshuser WHERE username=%s OR email=%s"
            params = (username, email.lower())
            cur.execute(sql, params)
            result = cur.fetchone()
            cur.close()
            return not bool(result)  # Return True if user doesn't exist

    def add_user(self, username, email, password, code):
        """Add new user to database with verification code."""
        with self.get_db_connection() as conn:
            cur = conn.cursor()

            # Check if verification_expires column exists (for backward compatibility)
            cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'meshuser'
                AND COLUMN_NAME = 'verification_expires'
            """)
            has_expiry_column = cur.fetchone() is not None

            if has_expiry_column:
                # Use new schema with expiration
                sql = """INSERT INTO meshuser
                        (email, username, password, verification, verification_expires)
                        VALUES (%s, %s, %s, %s, %s)"""
                expires = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
                params = (email.lower(), username, password, code, expires)
            else:
                # Use legacy schema without expiration
                sql = """INSERT INTO meshuser
                        (email, username, password, verification)
                        VALUES (%s, %s, %s, %s)"""
                params = (email.lower(), username, password, code)

            cur.execute(sql, params)
            conn.commit()
            cur.close()

    def register(self, username, email, password, confirm_password=None):
        """Register a new user with enhanced validation."""
        # Email validation
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not email or not re.match(email_regex, email):
            return {"error": "Invalid email address."}

        # Username validation
        username_regex = r'^\w{3,20}$'  # 3-20 alphanumeric characters
        if not username or not re.match(username_regex, username):
            return {"error": "Username must be 3-20 characters, letters, numbers, and underscores only."}

        # Password validation using unified validation function
        is_valid, error_msg = self.validate_password(password)
        if not is_valid:
            return {"error": error_msg}

        # Confirm password check (if provided)
        if confirm_password is not None and password != confirm_password:
            return {"error": "Passwords do not match."}

        # Check if user already exists
        if not self.verify(username, email):
            return {"error": "Username or email already exists."}

        try:
            # Generate secure verification code
            code = self.generate_verification_code()

            # Hash password and add user
            hashed_password = utils.hash_password(password)
            self.add_user(username, email.lower(), hashed_password, code)

            # Send verification email
            base_url = self.config["mesh"].get("meshinfo_url", self.config["mesh"]["url"])
            utils.send_email(
                email,
                "MeshInfo Account Verification",
                f"Welcome to MeshInfo!\n\n"
                f"Please verify your account by clicking the link below:\n"
                f"{base_url}/verify?c={code}\n\n"
                f"This link will expire in 24 hours.\n\n"
                f"If you didn't create this account, please ignore this email."
            )

            return {"success": "Registration successful! Please check your email to verify your account."}

        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return {"error": "An error occurred during registration. Please try again."}

    def check_account_lockout(self, email):
        """Check if account is locked due to failed login attempts."""
        with self.get_db_connection() as conn:
            cur = conn.cursor()

            # Check if lockout columns exist (backward compatibility)
            cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'meshuser'
                AND COLUMN_NAME IN ('failed_login_attempts', 'account_locked_until')
            """)
            columns = [row[0] for row in cur.fetchall()]

            if 'account_locked_until' not in columns:
                # Legacy database without lockout support
                return False, None

            sql = """SELECT failed_login_attempts, account_locked_until
                     FROM meshuser WHERE email = %s"""
            cur.execute(sql, (email.lower(),))
            result = cur.fetchone()
            cur.close()

            if not result:
                return False, None

            failed_attempts, locked_until = result

            # Check if account is currently locked
            if locked_until and locked_until > datetime.datetime.now():
                remaining = (locked_until - datetime.datetime.now()).seconds // 60
                return True, f"Account locked. Try again in {remaining} minutes."

            return False, None

    def record_failed_login(self, email):
        """Record failed login attempt and potentially lock account."""
        with self.get_db_connection() as conn:
            cur = conn.cursor()

            # Check if security columns exist
            cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'meshuser'
                AND COLUMN_NAME = 'failed_login_attempts'
            """)

            if not cur.fetchone():
                # Legacy database, skip failed login tracking
                cur.close()
                return

            # Get max attempts from config
            max_attempts = 5
            lockout_minutes = 30

            if self.config.has_section('security'):
                max_attempts = int(self.config.get('security', 'max_login_attempts', fallback='5'))
                lockout_minutes = int(self.config.get('security', 'lockout_duration_minutes', fallback='30'))

            sql = """UPDATE meshuser
                     SET failed_login_attempts = failed_login_attempts + 1,
                         last_failed_login = NOW(),
                         account_locked_until = IF(failed_login_attempts >= %s,
                                                  DATE_ADD(NOW(), INTERVAL %s MINUTE),
                                                  account_locked_until)
                     WHERE email = %s"""

            cur.execute(sql, (max_attempts - 1, lockout_minutes, email.lower()))
            conn.commit()
            cur.close()

    def reset_failed_attempts(self, email):
        """Reset failed login attempts on successful login."""
        with self.get_db_connection() as conn:
            cur = conn.cursor()

            # Check if security columns exist
            cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'meshuser'
                AND COLUMN_NAME = 'failed_login_attempts'
            """)

            if not cur.fetchone():
                # Legacy database, skip
                cur.close()
                return

            sql = """UPDATE meshuser
                     SET failed_login_attempts = 0,
                         last_failed_login = NULL,
                         account_locked_until = NULL,
                         last_login = NOW()
                     WHERE email = %s"""

            cur.execute(sql, (email.lower(),))
            conn.commit()
            cur.close()

    def authenticate(self, email, password):
        """Authenticate user with enhanced security checks."""
        if not email or not password:
            return {"error": "Email and password are required."}

        # Check account lockout
        is_locked, lock_message = self.check_account_lockout(email)
        if is_locked:
            return {"error": lock_message}

        with self.get_db_connection() as conn:
            cur = conn.cursor()
            sql = """SELECT password, username, status FROM meshuser
                     WHERE email = %s"""
            cur.execute(sql, (email.lower(),))
            row = cur.fetchone()
            cur.close()

            if not row:
                # User doesn't exist, but don't reveal this
                self.record_failed_login(email)
                return {"error": "Invalid email or password."}

            hashed_password, username, status = row

            # Check if account is verified
            if status != 'VERIFIED':
                return {"error": "Please verify your email before logging in."}

            # Verify password
            if not utils.check_password(password, hashed_password):
                self.record_failed_login(email)
                return {"error": "Invalid email or password."}

            # Successful login - reset failed attempts
            self.reset_failed_attempts(email)

            # Create JWT token with expiration
            encoded_jwt = jwt.encode(
                {
                    "email": email.lower(),
                    "username": username,
                    "iat": int(time.time()),
                    "exp": int(time.time()) + 86400,  # 24 hours
                    "jti": str(uuid.uuid4())  # JWT ID for potential blacklisting
                },
                self.config["registrations"]["jwt_secret"],
                algorithm="HS256"
            )

            return {"success": encoded_jwt}

    def auth(self, encoded_jwt):
        """Validate JWT token with expiration check."""
        try:
            # Decode and verify token
            payload = jwt.decode(
                encoded_jwt,
                self.config["registrations"]["jwt_secret"],
                algorithms=["HS256"]
            )

            # Additional validation could go here (e.g., check blacklist)

            return payload

        except jwt.ExpiredSignatureError:
            logger.debug("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid JWT token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"JWT validation error: {str(e)}")
            return None

    def verify_account(self, code):
        """Verify user account with code expiration check."""
        with self.get_db_connection() as conn:
            cur = conn.cursor()

            # Check if verification_expires column exists
            cur.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'meshuser'
                AND COLUMN_NAME = 'verification_expires'
            """)
            has_expiry = cur.fetchone() is not None

            if has_expiry:
                # Check with expiration
                sql = """UPDATE meshuser
                        SET status='VERIFIED',
                            ts_updated = NOW(),
                            verification = NULL,
                            verification_expires = NULL
                        WHERE verification=%s
                        AND (verification_expires IS NULL OR verification_expires > NOW())"""
            else:
                # Legacy without expiration
                sql = """UPDATE meshuser
                        SET status='VERIFIED',
                            ts_updated = NOW(),
                            verification = NULL
                        WHERE verification=%s"""

            cur.execute(sql, (code,))
            verified = cur.rowcount > 0
            conn.commit()
            cur.close()

            if verified:
                return {"success": "Email verified! You can now log in."}
            else:
                return {"error": "Invalid or expired verification link."}

    def update_password(self, email, newpass):
        """Update user password."""
        with self.get_db_connection() as conn:
            cur = conn.cursor()
            hashed = utils.hash_password(newpass)
            sql = """UPDATE meshuser
                     SET password = %s,
                         ts_updated = NOW()
                     WHERE email = %s"""
            cur.execute(sql, (hashed, email.lower()))
            conn.commit()
            cur.close()

    def get_otp(self, email):
        """Generate and store OTP for user (backward compatibility)."""
        with self.get_db_connection() as conn:
            cur = conn.cursor()
            otp = utils.generate_random_otp()
            sql = """UPDATE meshuser SET otp = %s WHERE email = %s"""
            cur.execute(sql, (otp, email.lower()))
            conn.commit()
            cur.close()
            return otp

    def request_password_reset(self, email):
        """Request password reset with secure token generation."""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not email or not re.match(email_regex, email):
            return {"error": "Invalid email address."}

        with self.get_db_connection() as conn:
            cur = conn.cursor()

            # Check if email exists and is verified
            sql = "SELECT username FROM meshuser WHERE status='VERIFIED' AND email = %s"
            cur.execute(sql, (email.lower(),))
            row = cur.fetchone()
            cur.close()

            if not row:
                # Don't reveal if email exists (security best practice)
                return {"success": "If your email is in our system, you will receive a password reset link."}

            # Generate secure reset token
            reset_token = jwt.encode(
                {
                    "email": email.lower(),
                    "purpose": "password_reset",
                    "exp": int(time.time()) + 86400,  # 24 hours
                    "jti": str(uuid.uuid4())
                },
                self.config["registrations"]["jwt_secret"],
                algorithm="HS256"
            )

            # Send reset email
            base_url = self.config["mesh"].get("meshinfo_url", self.config["mesh"]["url"])
            utils.send_email(
                email,
                "MeshInfo Password Reset",
                f"You requested a password reset for your MeshInfo account.\n\n"
                f"Click the link below to reset your password:\n"
                f"{base_url}/reset-password?token={reset_token}\n\n"
                f"This link will expire in 24 hours.\n\n"
                f"If you didn't request this reset, please ignore this email."
            )

            return {"success": "If your email is in our system, you will receive a password reset link."}

    def reset_password(self, token, new_password):
        """Reset password using secure token."""
        # Validate new password
        is_valid, error_msg = self.validate_password(new_password)
        if not is_valid:
            return {"error": error_msg}

        try:
            # Decode and validate token
            payload = jwt.decode(
                token,
                self.config["registrations"]["jwt_secret"],
                algorithms=["HS256"]
            )

            # Verify token purpose
            if payload.get("purpose") != "password_reset":
                return {"error": "Invalid reset token."}

            email = payload.get("email")
            if not email:
                return {"error": "Invalid reset token."}

            # Update password
            self.update_password(email, new_password)

            # Reset any failed login attempts
            self.reset_failed_attempts(email)

            return {"success": "Password successfully reset! You can now log in with your new password."}

        except jwt.ExpiredSignatureError:
            return {"error": "Reset link has expired. Please request a new password reset."}
        except jwt.InvalidTokenError:
            return {"error": "Invalid reset token."}
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return {"error": "An error occurred while resetting your password."}