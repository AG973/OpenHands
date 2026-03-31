"""CODEIT authentication — JWT tokens + password hashing."""

import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional

from openhands.core.logger import openhands_logger as logger
from openhands.server.codeit.database import get_db

# JWT secret — generated once per install, persisted in DB dir
_SECRET_FILE = os.path.join(
    os.environ.get("CODEIT_DATA_DIR", os.path.expanduser("~/.codeit")),
    ".jwt_secret",
)

# Token expiry: 7 days
TOKEN_EXPIRY_SECONDS = 7 * 24 * 60 * 60


def _get_jwt_secret() -> str:
    """Get or create a persistent JWT secret."""
    if os.path.exists(_SECRET_FILE):
        with open(_SECRET_FILE) as f:
            return f.read().strip()
    secret = secrets.token_hex(32)
    os.makedirs(os.path.dirname(_SECRET_FILE), exist_ok=True)
    with open(_SECRET_FILE, "w") as f:
        f.write(secret)
    os.chmod(_SECRET_FILE, 0o600)
    return secret


def hash_password(password: str) -> str:
    """Hash password with salt using PBKDF2."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}:{dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash."""
    try:
        salt, dk_hex = stored_hash.split(":", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, AttributeError):
        return False


def create_token(user_id: int, username: str) -> str:
    """Create a simple JWT-like token (HMAC-SHA256 signed)."""
    secret = _get_jwt_secret()
    payload = {
        "sub": user_id,
        "username": username,
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS,
        "iat": int(time.time()),
    }
    payload_b64 = _b64_encode(json.dumps(payload))
    header_b64 = _b64_encode(json.dumps({"alg": "HS256", "typ": "JWT"}))
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).hexdigest()
    return f"{signing_input}.{signature}"


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a token. Returns payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, signature = parts
        secret = _get_jwt_secret()
        signing_input = f"{header_b64}.{payload_b64}"
        expected = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_b64_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception as e:
        logger.debug(f"Token verification failed: {e}")
        return None


def _b64_encode(data: str) -> str:
    import base64
    return base64.urlsafe_b64encode(data.encode()).rstrip(b"=").decode()


def _b64_decode(data: str) -> str:
    import base64
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data).decode()


def get_or_create_default_user() -> tuple[int, str]:
    """Ensure a default admin user exists. Returns (user_id, username)."""
    default_user = os.environ.get("CODEIT_ADMIN_USER", "admin")
    default_pass = os.environ.get("CODEIT_ADMIN_PASS", "codeit")

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username FROM users WHERE username = ?", (default_user,)
        ).fetchone()
        if row:
            return row["id"], row["username"]

        pw_hash = hash_password(default_pass)
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
            (default_user, pw_hash, "Admin", "admin"),
        )
        user_id = cursor.lastrowid
        logger.info(f"CODEIT: Created default admin user '{default_user}' (id={user_id})")
        return user_id, default_user


def authenticate_user(username: str, password: str) -> Optional[tuple[int, str]]:
    """Authenticate user by username/password. Returns (user_id, username) or None."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return row["id"], row["username"]
