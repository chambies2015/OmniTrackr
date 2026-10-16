"""Sign in with Google (OAuth 2.0 authorization-code flow, no Google script on our pages).

The button only appears once the owner sets GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
(see the README). Pressing it goes to /auth/google/start, which sends the visitor to
Google's own account chooser; Google returns them to /auth/google/callback.

What we receive and keep: the Google account id ("sub"), the email address and the
first name, used once to suggest a username. No Google token is stored.

Account rules:
- A Google account already linked to a member signs that member in.
- Otherwise a member whose email matches Google's verified email is linked and signed in.
  If that member had never verified the address, Google has now proved who owns it, so
  the account is marked verified and its unproven password is replaced (whoever chose
  it never showed they own the inbox; the owner can set a new one with "Forgot password").
- Otherwise a new, already-verified account is created with a random password the
  member can replace through "Forgot password".
"""
from __future__ import annotations

import os
import re
import secrets
import time
from typing import Optional
from urllib.parse import urlencode

import jwt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import auth, models

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = ("accounts.google.com", "https://accounts.google.com")
STATE_COOKIE = "omnitrackr_google_state"
STATE_COOKIE_PATH = "/auth/google"
STATE_MAX_AGE_SECONDS = 600
_STATE_SALT = "omnitrackr-google-signin-v1"
_INVITE_RE = re.compile(r"[A-Za-z0-9_-]{16,32}")

# Error codes put in the redirect back to the homepage. The page maps each to its own
# sentence, so nothing Google or a visitor sends is ever shown as text.
ERRORS = ("cancelled", "expired", "failed", "unverified", "deactivated", "unavailable")


class SignInError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code if code in ERRORS else "failed"


def client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip()


def client_secret() -> str:
    return os.getenv("GOOGLE_CLIENT_SECRET", "").strip()


def configured() -> bool:
    return bool(client_id() and client_secret())


CALLBACK_PATH = "/auth/google/callback"


def _known_hosts() -> set[str]:
    """The site's own host names (from APP_URL and SITE_URL), with and without www."""
    from urllib.parse import urlparse

    hosts = {"omnitrackr.xyz"}
    for name in ("APP_URL", "SITE_URL"):
        host = urlparse(os.getenv(name, "")).netloc.lower()
        if host:
            hosts.add(host)
    return hosts | {h[4:] for h in hosts if h.startswith("www.")} | {"www." + h for h in hosts if not h.startswith("www.")}


def redirect_uri(request=None) -> str:
    """Where Google sends the visitor back.

    It must be the host the visitor started on, because the state cookie belongs to
    that host (omnitrackr.xyz and www.omnitrackr.xyz don't share cookies). Only the
    site's own host names are used; anything else falls back to APP_URL.
    """
    override = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    if override:
        return override
    if request is not None:
        host = (request.headers.get("host") or "").strip().lower()
        if host and host in _known_hosts():
            # Render ends TLS before the app, so the app itself only sees http.
            scheme = "https" if auth.ENVIRONMENT == "production" else request.url.scheme
            return f"{scheme}://{host}{CALLBACK_PATH}"
    from .email import APP_URL
    return f"{APP_URL.rstrip('/')}{CALLBACK_PATH}"


# ---------------------------------------------------------------- state cookie

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(auth.SECRET_KEY, salt=_STATE_SALT)


def valid_invite(value) -> Optional[str]:
    return value if isinstance(value, str) and _INVITE_RE.fullmatch(value) else None


def new_state(invite: Optional[str] = None, return_to: Optional[str] = None) -> tuple[dict, str]:
    """A fresh {state, nonce, redirect_uri, invite} and its signed cookie value."""
    data = {"state": secrets.token_urlsafe(24), "nonce": secrets.token_urlsafe(24),
            "redirect_uri": return_to or redirect_uri()}
    if valid_invite(invite):
        data["invite"] = invite
    return data, _serializer().dumps(data)


def read_state(cookie_value: Optional[str]) -> dict:
    if not cookie_value or len(cookie_value) > 1024:
        raise SignInError("expired")
    try:
        data = _serializer().loads(cookie_value, max_age=STATE_MAX_AGE_SECONDS)
    except SignatureExpired:
        raise SignInError("expired")
    except BadSignature:
        raise SignInError("failed")
    if not isinstance(data, dict) or not isinstance(data.get("state"), str) or not isinstance(data.get("nonce"), str):
        raise SignInError("failed")
    if not isinstance(data.get("redirect_uri"), str):
        data["redirect_uri"] = redirect_uri()
    return data


def authorize_url(state: dict) -> str:
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": client_id(),
        "redirect_uri": state["redirect_uri"],
        "response_type": "code",
        "scope": "openid email profile",
        "state": state["state"],
        "nonce": state["nonce"],
        "prompt": "select_account",
        "access_type": "online",
    })


# ---------------------------------------------------------------- talking to Google

async def exchange_code(code: str, http_client=None, return_to: Optional[str] = None) -> str:
    """Trade the one-time code for Google's ID token (a JWT).

    return_to must be the same redirect_uri the visitor was sent to Google with.
    """
    import httpx

    payload = {
        "code": code,
        "client_id": client_id(),
        "client_secret": client_secret(),
        "redirect_uri": return_to or redirect_uri(),
        "grant_type": "authorization_code",
    }
    try:
        if http_client is not None:
            response = await http_client.post(TOKEN_URL, data=payload, timeout=10)
        else:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(TOKEN_URL, data=payload)
    except Exception:
        raise SignInError("failed")
    if response.status_code != 200:
        raise SignInError("expired" if response.status_code == 400 else "failed")
    try:
        id_token = response.json().get("id_token")
    except Exception:
        id_token = None
    if not isinstance(id_token, str) or len(id_token) > 8192:
        raise SignInError("failed")
    return id_token


def read_id_token(id_token: str, nonce: str, now: Optional[float] = None) -> dict:
    """Check the ID token's claims and return {sub, email, name}.

    The token comes straight from Google's token endpoint over TLS, in exchange for
    our client secret, so Google's guidance is that its signature need not be checked
    again; the claims still are.
    """
    try:
        claims = jwt.decode(id_token, options={"verify_signature": False})
    except Exception:
        raise SignInError("failed")
    now = time.time() if now is None else now
    aud = claims.get("aud")
    audiences = aud if isinstance(aud, list) else [aud]
    if claims.get("iss") not in ISSUERS or client_id() not in audiences:
        raise SignInError("failed")
    try:
        if float(claims.get("exp", 0)) < now - 60:
            raise SignInError("expired")
    except (TypeError, ValueError):
        raise SignInError("failed")
    if not isinstance(claims.get("nonce"), str) or not secrets.compare_digest(claims["nonce"], nonce):
        raise SignInError("failed")
    sub = claims.get("sub")
    email = claims.get("email")
    if not isinstance(sub, str) or not sub or len(sub) > 255:
        raise SignInError("failed")
    if not isinstance(email, str) or "@" not in email or len(email) > 254:
        raise SignInError("failed")
    if claims.get("email_verified") not in (True, "true"):
        raise SignInError("unverified")
    name = claims.get("given_name") or claims.get("name") or ""
    return {"sub": sub, "email": email.strip(), "name": name if isinstance(name, str) else ""}


# ---------------------------------------------------------------- accounts

def _username_base(name: str, email: str) -> str:
    for source in (name, email.split("@", 1)[0]):
        cleaned = re.sub(r"[^A-Za-z0-9_.-]", "", source or "")
        cleaned = re.sub(r"^[^A-Za-z0-9]+", "", cleaned)[:24].rstrip("._-")
        if len(cleaned) >= 3:
            return cleaned
    return "member"


def suggest_username(db: Session, name: str, email: str) -> str:
    """A free username from the Google first name or email, e.g. "dan" or "dan4821"."""
    from .signup_rules import username_problem, username_taken

    base = _username_base(name, email)
    candidates = [base] + [f"{base}{secrets.randbelow(9000) + 1000}" for _ in range(20)]
    for candidate in candidates:
        if not username_problem(candidate) and not username_taken(db, candidate):
            return candidate
    return f"member{secrets.token_hex(5)}"


def _random_password_hash() -> str:
    return auth.get_password_hash(secrets.token_urlsafe(32))


def find_or_create_user(db: Session, profile: dict) -> tuple[models.User, str]:
    """Return (user, outcome) where outcome is "signed_in", "linked" or "created"."""
    user = db.query(models.User).filter(models.User.google_sub == profile["sub"]).first()
    if user is not None:
        outcome = "signed_in"
    else:
        user = (db.query(models.User)
                .filter(func.lower(models.User.email) == profile["email"].lower())
                .order_by(models.User.id).first())
        if user is not None:
            if not user.is_active:
                raise SignInError("deactivated")  # Leave a deactivated account exactly as it was.
            if user.google_sub and user.google_sub != profile["sub"]:
                raise SignInError("failed")  # Already linked to a different Google account.
            user.google_sub = profile["sub"]
            if not user.is_verified:
                user.is_verified = True
                user.verification_token = None
                user.hashed_password = _random_password_hash()
                user.password_set = False
            db.commit()
            db.refresh(user)
            outcome = "linked"
        else:
            user = models.User(
                email=profile["email"],
                username=suggest_username(db, profile.get("name", ""), profile["email"]),
                hashed_password=_random_password_hash(),
                is_verified=True,
                google_sub=profile["sub"],
                password_set=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            outcome = "created"
    if not user.is_active:
        raise SignInError("deactivated")
    return user, outcome
