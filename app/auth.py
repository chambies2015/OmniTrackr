"""
Authentication utilities for the OmniTrackr API.
Handles password hashing, JWT token creation and validation.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from jwt import InvalidTokenError
import bcrypt
import re
import hashlib
import hmac
import os
from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if ENVIRONMENT == "production":
        raise ValueError("SECRET_KEY must be set in production environment")
    SECRET_KEY = "dev-secret-key-change-in-production"
    import warnings
    warnings.warn("Using default SECRET_KEY - not for production!")

ALGORITHM = "HS256"
# Members stay signed in for 30 days; a password change or reset ends every other session.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30
AUTH_COOKIE_NAME = "omnitrackr_session"
AUTH_COOKIE_MAX_AGE_SECONDS = ACCESS_TOKEN_EXPIRE_MINUTES * 60


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    try:
        password_bytes = plain_password.encode("utf-8")
        if len(password_bytes) > 72:
            # Existing bcrypt hashes may have been created when the library
            # silently truncated inputs. Keep those accounts usable; all new
            # and changed passwords are limited by validate_password_strength.
            password_bytes = password_bytes[:72]
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def validate_password_strength(password: str, username: str = "", email: str = "") -> tuple[bool, str]:
    """
    Validate a newly chosen password.

    Follows current guidance (NIST SP 800-63B): a minimum length and a check
    against common passwords, instead of symbol/uppercase rules that push people
    toward predictable passwords. Existing passwords are never re-checked.

    Returns:
        (is_valid, error_message)
    """
    from .signup_rules import password_problem
    if len(password.encode("utf-8")) > 72:
        return False, "Password must be no more than 72 UTF-8 bytes long"
    if ENVIRONMENT != "production":
        return True, ""
    problem = password_problem(password, username, email)
    return (False, problem) if problem else (True, "")
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if len(password) > 128:
        return False, "Password must be no more than 128 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"
    return True, ""


def get_password_hash(password: str) -> str:
    """Hash a password for storing."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(token.encode('utf-8'), salt).decode('utf-8')


def verify_token_hash(token: str, hashed_token: str) -> bool:
    """Verify a token against its hash using constant-time comparison."""
    try:
        return bcrypt.checkpw(token.encode('utf-8'), hashed_token.encode('utf-8'))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary of data to encode in the token
        expires_delta: Optional custom expiration time
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_user_access_token(user) -> str:
    """Session token for a user.

    `uid` is the stable identity; `sub` (the username at sign-in) is kept for
    older clients. Keying sessions on the id means renaming an account keeps
    it signed in, and a token issued before a rename can never authenticate as
    someone who later registers the old username.
    """
    return create_access_token(data={
        "sub": user.username,
        "uid": user.id,
        "pv": password_fingerprint(user.hashed_password),
    })


def password_fingerprint(hashed_password: Optional[str]) -> str:
    """A keyed, one-way marker of the current password hash.

    Tokens carry it so changing or resetting a password signs out every other
    session, which matters now that sessions last 30 days.
    """
    digest = hmac.new(SECRET_KEY.encode(), (hashed_password or "").encode(), hashlib.sha256)
    return digest.hexdigest()[:16]


def set_auth_cookie(response, access_token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_token,
        max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=ENVIRONMENT == "production",
        samesite="lax",
        path="/",
    )


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.
    
    Args:
        token: The JWT token string to decode
    
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except InvalidTokenError:
        return None
