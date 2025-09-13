import configparser
import mysql.connector
import bcrypt
import utils
import re
import jwt
import time
import logging

logger = logging.getLogger(__name__)


class Register:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.config = config
        self.db = mysql.connector.connect(
            host=self.config["database"]["host"],
            user=self.config["database"]["username"],
            password=self.config["database"]["password"],
            database=self.config["database"]["database"],
            charset="utf8mb4"
        )
        cur = self.db.cursor()
        cur.execute("SET NAMES utf8mb4;")

    def verify(self, username, email):
        sql = "SELECT 1 FROM meshuser WHERE username=%s OR email=%s"
        params = (username, email.lower())
        cur = self.db.cursor()
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
        cur = self.db.cursor()
        cur.execute(sql, params)
        cur.close()
        self.db.commit()

    def register(self, username, email, password):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        username_regex = r'^\w+$'
        if not email or not re.match(email_regex, email):
            return {"error": "Invalid email."}
        elif not password or len(password) < 6:
            return {"error": "Invalid password."}
        elif not username or not re.match(username_regex, username):
            return {"error": "Invalid username."}
        elif not self.verify(username, email):  # Fixed: was (username, password)
            return {"error": "Username or email already exist."}
        code = utils.generate_random_code(4)
        self.add_user(
           username,
           email.lower(),
           utils.hash_password(password),
           code
        )
        # Use meshinfo_url if specified, otherwise fall back to url
        base_url = self.config["mesh"].get("meshinfo_url", self.config["mesh"]["url"])
        utils.send_email(
            email,
            "MeshInfo Verify Account",
            f"Please visit {base_url}/verify?c={code} to verify your account."
        )
        return {"success": "Please check your email to verify your account."}
    
    def update_password(self, email, newpass):
        hashed = utils.hash_password(newpass)
        sql = """UPDATE meshuser SET password = %s
WHERE email = %s"""
        params = (hashed, email.lower())
        cur = self.db.cursor()
        cur.execute(sql, params)
        cur.close()
        self.db.commit()

    def authenticate(self, email, password):
        sql = """SELECT password, username FROM meshuser
WHERE status='VERIFIED' AND email = %s"""
        params = (email.lower(), )
        cur = self.db.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        hashed_password = row[0] if row else None
        cur.close()
        if hashed_password and \
                utils.check_password(password, hashed_password):
            encoded_jwt = jwt.encode(
                {
                    "email": email.lower(),  # Fixed: use lowercase email consistently
                    "username": row[1],
                    "time": int(time.time())
                },
                self.config["registrations"]["jwt_secret"],
                algorithm="HS256"
            )
            return {"success": encoded_jwt}

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
        cur = self.db.cursor()
        cur.execute(sql, params)
        verified = True if cur.rowcount else False
        cur.close()
        self.db.commit()
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
        cur = self.db.cursor()
        cur.execute(sql, params)
        cur.close()
        self.db.commit()
        return otp

    def request_password_reset(self, email):
        """
        Request a password reset for the given email address.
        Generates a reset token and sends an email if the address is in the database.
        """
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not email or not re.match(email_regex, email):
            return {"error": "Invalid email address."}
        
        # Check if email exists and is verified
        sql = "SELECT username FROM meshuser WHERE status='VERIFIED' AND email = %s"
        params = (email.lower(),)
        cur = self.db.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        
        if not row:
            # Return success message even if email doesn't exist (security best practice)
            return {"success": "If your email is in our system, you will receive a password reset link."}
        
        # Generate reset token with expiration (24 hours)
        reset_token = jwt.encode(
            {
                "email": email.lower(),
                "purpose": "password_reset",
                "exp": int(time.time()) + 86400  # 24 hours
            },
            self.config["registrations"]["jwt_secret"],
            algorithm="HS256"
        )
        
        # Use meshinfo_url if specified, otherwise fall back to url
        base_url = self.config["mesh"].get("meshinfo_url", self.config["mesh"]["url"])
        
        # Send reset email
        utils.send_email(
            email,
            "MeshInfo Password Reset",
            f"Please visit {base_url}/reset-password?token={reset_token} to reset your password. This link will expire in 24 hours."
        )
        
        return {"success": "If your email is in our system, you will receive a password reset link."}
    
    def reset_password(self, token, new_password):
        """
        Reset password using a valid reset token.
        """
        if not new_password or len(new_password) < 8:
            return {"error": "Password must be at least 8 characters long."}
        if not re.search(r'[A-Z]', new_password):
            return {"error": "Password must contain at least one uppercase letter."}
        if not re.search(r'[a-z]', new_password):
            return {"error": "Password must contain at least one lowercase letter."}
        if not re.search(r'\d', new_password):
            return {"error": "Password must contain at least one number."}
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            return {"error": "Password must contain at least one special character."}
        try:
            # Decode and validate the reset token
            payload = jwt.decode(
                token,
                self.config["registrations"]["jwt_secret"],
                algorithms=["HS256"]
            )
            
            # Verify token purpose and extract email
            if payload.get("purpose") != "password_reset":
                return {"error": "Invalid reset token."}
            
            email = payload.get("email")
            if not email:
                return {"error": "Invalid reset token."}
            
            # Update password
            self.update_password(email, new_password)
            
            return {"success": "Password successfully reset. You can now log in with your new password."}
            
        except jwt.ExpiredSignatureError:
            return {"error": "Reset link has expired. Please request a new password reset."}
        except jwt.InvalidTokenError:
            return {"error": "Invalid reset token."}
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return {"error": "An error occurred while resetting your password."}

    def __del__(self):
        if self.db:
            self.db.close()
