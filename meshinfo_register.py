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
import string
import secrets

logger = logging.getLogger(__name__)


class Register:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.config = config

        # Use connection pooling for better security and performance
        try:
            pool_config = {
                'host': self.config["database"]["host"],
                'user': self.config["database"]["username"],
                'password': self.config["database"]["password"],
                'database': self.config["database"]["database"],
                'charset': "utf8mb4",
                'pool_name': 'meshinfo_pool',
                'pool_size': 5,
                'pool_reset_session': True,
                'autocommit': False
            }
            self.db_pool = mysql.connector.pooling.MySQLConnectionPool(**pool_config)
            # Test the connection
            test_conn = self.db_pool.get_connection()
            test_conn.close()
        except mysql.connector.Error as err:
            logger.error(f"Database connection pool error: {err}")
            # Fallback to single connection
            self.db_pool = None
            self.db = mysql.connector.connect(
                host=self.config["database"]["host"],
                user=self.config["database"]["username"],
                password=self.config["database"]["password"],
                database=self.config["database"]["database"],
                charset="utf8mb4"
            )
            cur = self.db.cursor()
            cur.execute("SET NAMES utf8mb4;")

    @contextmanager
    def get_db_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            if self.db_pool:
                conn = self.db_pool.get_connection()
            else:
                conn = self.db

            # Set UTF8MB4 for proper Unicode support
            cursor = conn.cursor()
            cursor.execute("SET NAMES utf8mb4")
            cursor.close()

            yield conn

        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            if conn and self.db_pool:
                conn.rollback()
            raise
        finally:
            if conn and self.db_pool:
                try:
                    conn.close()
                except:
                    pass

    def validate_password(self, password):
        """Validate password against security policy."""
        # Get password policy from config, with defaults
        min_length = int(self.config.get("registrations", "password_min_length", fallback="8"))
        require_uppercase = self.config.getboolean("registrations", "password_require_uppercase", fallback=True)
        require_lowercase = self.config.getboolean("registrations", "password_require_lowercase", fallback=True)
        require_numbers = self.config.getboolean("registrations", "password_require_numbers", fallback=True)
        require_special = self.config.getboolean("registrations", "password_require_special", fallback=True)

        if len(password) < min_length:
            return False, f"Password must be at least {min_length} characters long"

        if require_uppercase and not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"

        if require_lowercase and not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"

        if require_numbers and not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"

        if require_special and not any(c in string.punctuation for c in password):
            return False, "Password must contain at least one special character"

        return True, "Password is valid"

    def record_failed_login(self, email, ip_address=None):
        """Record a failed login attempt."""
        if self.db_pool:
            conn = self.db_pool.get_connection()
        else:
            conn = self.db

        try:
            sql = """INSERT INTO failed_logins (email, ip_address, attempt_time)
                     VALUES (%s, %s, NOW())"""
            cur = conn.cursor()
            cur.execute(sql, (email.lower(), ip_address))
            conn.commit()
            cur.close()
        except mysql.connector.Error as err:
            logger.error(f"Failed to record failed login: {err}")
        finally:
            if self.db_pool:
                conn.close()

    def get_failed_login_count(self, email, minutes=30):
        """Get the count of failed login attempts for an email in the specified time window."""
        if self.db_pool:
            conn = self.db_pool.get_connection()
        else:
            conn = self.db

        try:
            sql = """SELECT COUNT(*) FROM failed_logins
                     WHERE email = %s AND attempt_time > DATE_SUB(NOW(), INTERVAL %s MINUTE)"""
            cur = conn.cursor()
            cur.execute(sql, (email.lower(), minutes))
            count = cur.fetchone()[0]
            cur.close()
            return count
        except mysql.connector.Error as err:
            logger.error(f"Failed to get failed login count: {err}")
            return 0
        finally:
            if self.db_pool:
                conn.close()

    def clear_failed_logins(self, email):
        """Clear failed login attempts for a successful login."""
        if self.db_pool:
            conn = self.db_pool.get_connection()
        else:
            conn = self.db

        try:
            sql = "DELETE FROM failed_logins WHERE email = %s"
            cur = conn.cursor()
            cur.execute(sql, (email.lower(),))
            conn.commit()
            cur.close()
        except mysql.connector.Error as err:
            logger.error(f"Failed to clear failed logins: {err}")
        finally:
            if self.db_pool:
                conn.close()

    def generate_secure_code(self, length=32):
        """Generate a cryptographically secure random code."""
        return secrets.token_urlsafe(length)

    def verify(self, username, email):
        sql = "SELECT 1 FROM meshuser WHERE username=%s OR email=%s"
        params = (username, email.lower())

        with self.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            okay = True if not cur.fetchone() else False
            cur.close()
        return okay

    def add_user(self, username, email, password, code):
        sql = """INSERT INTO meshuser
(email, username, password, verification)
VALUES (%s, %s, %s, %s)"""
        params = (
            email.lower(),
            username,
            password,
            code
        )

        with self.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            cur.close()
            conn.commit()

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

        # Password validation
        password_valid, password_message = self.validate_password(password)
        if not password_valid:
            return {"error": password_message}

        # Confirm password check (if provided)
        if confirm_password is not None and password != confirm_password:
            return {"error": "Passwords do not match."}

        # Check if user already exists
        if not self.verify(username, email):
            return {"error": "Username or email already exists."}

        # Use secure code generation
        code = utils.generate_random_code(4)  # Matches CHAR(4) database column size
        self.add_user(
           username,
           email.lower(),
           utils.hash_password(password),
           code
        )
        base_url = self.config["mesh"]["url"]
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
    
    def update_password(self, email, newpass):
        hashed = utils.hash_password(newpass)
        sql = """UPDATE meshuser SET password = %s
WHERE email = %s"""
        params = (hashed, email.lower())

        with self.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            cur.close()
            conn.commit()

    def authenticate(self, email, password, ip_address=None):
        # Check for account lockout
        max_failed_attempts = int(self.config.get("registrations", "max_failed_login_attempts", fallback="5"))
        lockout_duration = int(self.config.get("registrations", "login_lockout_duration_minutes", fallback="30"))

        failed_count = self.get_failed_login_count(email, lockout_duration)
        if failed_count >= max_failed_attempts:
            return {"error": f"Account temporarily locked due to too many failed login attempts. Try again in {lockout_duration} minutes."}

        sql = """SELECT password, username FROM meshuser
WHERE status='VERIFIED' AND email = %s"""
        params = (email.lower(), )

        with self.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            row = cur.fetchone()
            hashed_password = row[0] if row else None
            cur.close()

        if hashed_password and utils.check_password(password, hashed_password):
            # Clear any failed login attempts on successful login
            self.clear_failed_logins(email)

            encoded_jwt = jwt.encode(
                {
                    "email": email.lower(),
                    "username": row[1],
                    "iat": int(time.time()),  # Issued at
                    "exp": int(time.time()) + 86400,  # Expires in 24 hours
                    "jti": str(uuid.uuid4())  # JWT ID for potential blacklisting
                },
                self.config["registrations"]["jwt_secret"],
                algorithm="HS256"
            )
            return {"success": encoded_jwt}
        else:
            # Record failed login attempt
            self.record_failed_login(email, ip_address)
            return {"error": "Login failed."}

    def auth(self, encoded_jwt):
        try:
            return jwt.decode(
                encoded_jwt,
                self.config["registrations"]["jwt_secret"],
                algorithms=["HS256"]
            )
        except Exception as e:
            logger.error(str(e))
            return None

    def verify_account(self, code):
        sql = """UPDATE meshuser
SET status='VERIFIED',
ts_updated = NOW(),
verification = NULL
WHERE verification=%s
"""
        params = (code, )
        with self.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            verified = True if cur.rowcount else False
            cur.close()
            conn.commit()

        if verified:
            return {"success": "Email verified. You can now log in."}
        else:
            return {"error": "Expired or invalid link."}

    def get_otp(self, email):
        otp = utils.generate_random_otp()
        sql = """UPDATE meshuser SET otp = %s
WHERE email = %s"""
        params = (
            otp,
            email.lower()
        )

        with self.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            cur.close()
            conn.commit()
        return otp

    def request_password_reset(self, email):
        """Request password reset with secure token generation."""
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not email or not re.match(email_regex, email):
            return {"error": "Invalid email address."}

        # Check if email exists and is verified
        sql = "SELECT username FROM meshuser WHERE status='VERIFIED' AND email = %s"

        with self.get_db_connection() as conn:
            cur = conn.cursor()
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
            f"{base_url}/reset-password.html?token={reset_token}\n\n"
            f"This link will expire in 24 hours.\n\n"
            f"If you didn't request this reset, please ignore this email."
        )

        return {"success": "If your email is in our system, you will receive a password reset link."}

    def reset_password(self, token, new_password):
        """Reset password using secure token."""
        # Use enhanced password validation
        password_valid, password_message = self.validate_password(new_password)
        if not password_valid:
            return {"error": password_message}

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
            password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
            sql = "UPDATE meshuser SET password = %s WHERE email = %s"

            with self.get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(sql, (password_hash, email.lower()))
                conn.commit()
                cur.close()

            return {"success": "Password successfully reset! You can now log in with your new password."}

        except jwt.ExpiredSignatureError:
            return {"error": "Reset link has expired. Please request a new password reset."}
        except jwt.InvalidTokenError:
            return {"error": "Invalid reset token."}
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return {"error": "An error occurred while resetting your password."}

    def __del__(self):
        if hasattr(self, 'db') and self.db:
            self.db.close()
