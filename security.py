"""
security.py — MIIM HRM Security Module
=======================================
இந்த file-ல் இருக்கும் fixes:
  1. JWT-based session tokens (header spoofing fix)
  2. bcrypt password hashing (plain text password fix)
  3. Rate limiting on login (brute force fix)
  4. Secure CORS (wildcard fix)
  5. Environment variables for secrets (hardcoded credential fix)
  6. Server-side role verification (client-side role trust fix)
  7. Input sanitization helpers

Usage in app.py:
  from security import (
      hash_password, verify_password,
      create_token, verify_token,
      require_auth, require_role,
      limiter, get_allowed_origins
  )
"""

import os
import secrets
import datetime
import functools
import bcrypt
import jwt
from flask import request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ─────────────────────────────────────────────
# 1. SECRET KEY — Load from environment variable
#    Never hardcode in source code!
#    Set in terminal: export MIIM_SECRET_KEY="your-very-long-random-key"
#    Or in .env file (use python-dotenv)
# ─────────────────────────────────────────────
SECRET_KEY = os.environ.get('MIIM_SECRET_KEY', None)
if not SECRET_KEY:
    # Generate a random key on first run — warn the developer
    SECRET_KEY = secrets.token_hex(32)
    print("⚠️  WARNING: MIIM_SECRET_KEY environment variable not set!")
    print(f"   Using temporary key. Set permanently: export MIIM_SECRET_KEY='{SECRET_KEY}'")
    print("   (Users will be logged out on every server restart)")

# ─────────────────────────────────────────────
# 2. SMTP CREDENTIALS — Load from environment
#    Set: export MIIM_SMTP_USER="your@email.com"
#         export MIIM_SMTP_PASS="yourpassword"
# ─────────────────────────────────────────────
SMTP_USER  = os.environ.get('MIIM_SMTP_USER', '')
SMTP_PASS  = os.environ.get('MIIM_SMTP_PASS', '')
ADMIN_EMAIL = os.environ.get('MIIM_ADMIN_EMAIL', SMTP_USER)

if not SMTP_USER or not SMTP_PASS:
    print("⚠️  WARNING: MIIM_SMTP_USER / MIIM_SMTP_PASS not set.")
    print("   Email features will not work until you set these.")

# ─────────────────────────────────────────────
# 3. ALLOWED ORIGINS — Restrict CORS
#    Only allow your own domain / localhost
# ─────────────────────────────────────────────
ALLOWED_ORIGINS_ENV = os.environ.get('MIIM_ALLOWED_ORIGINS', '')
if ALLOWED_ORIGINS_ENV:
    ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS_ENV.split(',')]
else:
    # Default: only localhost (development mode)
    ALLOWED_ORIGINS = [
        'http://localhost:5000',
        'http://127.0.0.1:5000',
        'http://localhost:3000',
    ]

def get_allowed_origins():
    return ALLOWED_ORIGINS

# ─────────────────────────────────────────────
# 4. RATE LIMITER — Prevent brute force attacks
# ─────────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri="memory://"
)

# Login endpoint: max 10 attempts per 15 minutes per IP
LOGIN_LIMIT = "10 per 15 minutes"

# ─────────────────────────────────────────────
# 5. PASSWORD HASHING — bcrypt (replaces plain text)
# ─────────────────────────────────────────────
DEFAULT_PASSWORD = 'miim@123'
DEFAULT_PASSWORD_HASH = bcrypt.hashpw(DEFAULT_PASSWORD.encode(), bcrypt.gensalt()).decode()

def hash_password(plain_password: str) -> str:
    """Hash a plain password with bcrypt. Store this in DB."""
    if not plain_password:
        raise ValueError("Password cannot be empty")
    return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, stored_hash: str) -> bool:
    """
    Verify a plain password against a stored hash.
    Handles both:
      - New bcrypt hashes (start with $2b$)
      - Legacy plain-text passwords (temporary, for migration)
    """
    if not plain_password or not stored_hash:
        return False
    
    # New bcrypt hashes
    if stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$'):
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), stored_hash.encode('utf-8'))
        except Exception:
            return False
    
    # Legacy: plain text comparison (for old accounts not yet migrated)
    # After login, migrate to bcrypt automatically (done in login() route)
    return plain_password == stored_hash

def needs_bcrypt_upgrade(stored_hash: str) -> bool:
    """Check if password needs to be upgraded to bcrypt."""
    return not (stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$'))

# ─────────────────────────────────────────────
# 6. JWT TOKEN — Session management
# ─────────────────────────────────────────────
TOKEN_EXPIRY_HOURS = 8  # Token valid for 8 hours

def create_token(user_id: int, username: str, role: str, emp_id: str = '') -> str:
    """Create a signed JWT token. Return this after successful login."""
    payload = {
        'user_id':  user_id,
        'username': username,
        'role':     role,
        'emp_id':   emp_id,
        'iat':      datetime.datetime.utcnow(),
        'exp':      datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_EXPIRY_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token: str) -> dict | None:
    """
    Verify a JWT token. Returns payload dict or None if invalid/expired.
    """
    if not token:
        return None
    try:
        # Strip 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None   # Token expired
    except jwt.InvalidTokenError:
        return None   # Token tampered or invalid

def get_token_from_request() -> str | None:
    """Extract JWT from Authorization header or cookie."""
    # Try Authorization header first: "Bearer <token>"
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    # Try cookie fallback
    return request.cookies.get('miim_token')

def get_current_user() -> dict | None:
    """Get current logged-in user from JWT token. Returns None if not logged in."""
    token = get_token_from_request()
    return verify_token(token)

# ─────────────────────────────────────────────
# 7. AUTH DECORATORS — Protect routes
# ─────────────────────────────────────────────
def require_auth(f):
    """
    Decorator: requires valid JWT token.
    Usage:
        @app.route('/api/employees')
        @require_auth
        def get_employees():
            user = get_current_user()  # access user info
            ...
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated

def require_role(*allowed_roles):
    """
    Decorator: requires specific role(s).
    Usage:
        @app.route('/api/employees', methods=['DELETE'])
        @require_role('admin', 'hr')
        def delete_employee():
            ...
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            if user.get('role') not in allowed_roles:
                return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# ─────────────────────────────────────────────
# 8. CORS HELPER — Secure origin check
# ─────────────────────────────────────────────
def is_origin_allowed(origin: str) -> bool:
    """Check if request origin is in our whitelist."""
    if not origin:
        return False
    return origin in ALLOWED_ORIGINS

def apply_cors_headers(response, origin: str):
    """Apply CORS headers only for allowed origins."""
    if is_origin_allowed(origin):
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        # Security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

# ─────────────────────────────────────────────
# 9. INPUT SANITIZATION
# ─────────────────────────────────────────────
def safe_str(value, max_len=500) -> str:
    """Sanitize string input — strip whitespace, limit length."""
    if value is None:
        return ''
    return str(value).strip()[:max_len]

def safe_int(value, default=0) -> int:
    """Safely convert to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

# ─────────────────────────────────────────────
# 10. ERROR RESPONSE — Don't leak internals
# ─────────────────────────────────────────────
def error_response(message: str, status_code: int = 400, log_error: str = None):
    """
    Return a safe error response.
    If log_error is provided, print it server-side but don't expose to client.
    """
    if log_error:
        print(f"[ERROR] {log_error}")  # Log server-side only
    return jsonify({'success': False, 'error': message}), status_code
