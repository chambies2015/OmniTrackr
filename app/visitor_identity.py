"""Signed, pseudonymous browser identity for public abuse controls.

The token is stored in an HTTP-only cookie and only its keyed hash is persisted.
No IP address or browser fingerprint is stored with reactions or reports.
"""
import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import OrderedDict

from fastapi import Request
from slowapi.util import get_remote_address

from . import auth


# Keep the original collection cookie name so existing browsers retain their
# deduplicated identity as the control expands to public reviews.
VISITOR_COOKIE = "omnitrackr_collection_visitor"


def sign_visitor_token(payload: str) -> str:
    signature = hmac.new(auth.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def visitor_identity(request: Request) -> tuple[str, str | None, bool]:
    """Return a signed pseudonymous identity and whether the browser retained it."""
    supplied_token = request.cookies.get(VISITOR_COOKIE, "")
    if 80 <= len(supplied_token) <= 160 and "." in supplied_token:
        payload, supplied_signature = supplied_token.rsplit(".", 1)
        expected = hmac.new(
            auth.SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        signature_is_hex = (
            len(supplied_signature) == 64
            and supplied_signature.isascii()
            and all(character in "0123456789abcdef" for character in supplied_signature)
        )
        if payload and signature_is_hex and hmac.compare_digest(supplied_signature, expected):
            digest = hashlib.sha256(
                f"{auth.SECRET_KEY}:{supplied_token}".encode("utf-8")
            ).hexdigest()
            return digest, None, True

    new_token = sign_visitor_token(secrets.token_urlsafe(32))
    digest = hashlib.sha256(f"{auth.SECRET_KEY}:{new_token}".encode("utf-8")).hexdigest()
    return digest, new_token, False


def set_visitor_cookie(response, token: str | None) -> None:
    if token:
        response.set_cookie(
            VISITOR_COOKIE,
            token,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=os.getenv("ENVIRONMENT", "development").lower() == "production",
            samesite="lax",
        )


def client_address(request: Request) -> str:
    """The visitor's network address, for rate limits and report counting.

    On Render every request reaches the app from an internal load balancer, so
    the socket address is shared by all visitors. Render sits behind Cloudflare,
    which sets True-Client-IP / CF-Connecting-IP to the real visitor and
    overwrites any value a client sends. Those headers are trusted only when
    running on Render (RENDER=true, set by Render itself).
    """
    if os.getenv("RENDER", "").lower() == "true":
        for header in ("true-client-ip", "cf-connecting-ip"):
            value = (request.headers.get(header) or "").strip()
            if value:
                return value[:64]
    return get_remote_address(request)


# A public review or collection is unlisted after reports from three different
# visitors. A visitor is only a cookie, though, so one person could clear it
# between reports and file all three alone. Each network address therefore
# counts once per report target as well. The address is never stored: only a
# keyed hash of (target, address) is held in this process's memory for a week.
# Tests turn this off (like the rate limiter) so they can file several reports
# from the one test client; tests of this guard turn it back on.
REPORT_ADDRESS_GUARD = os.getenv("TESTING", "").lower() != "true"
REPORT_ADDRESS_TTL_SECONDS = 7 * 24 * 3600
REPORT_ADDRESS_MAX_ENTRIES = 50_000
_report_addresses: "OrderedDict[str, float]" = OrderedDict()
_report_lock = threading.Lock()


def first_report_from_address(request: Request, target: str, now: float | None = None) -> bool:
    """True the first time this network address reports `target`; False for a repeat.

    `target` should include the reported content's hash, so an edited review or
    collection starts with a clean slate, as its stored reports do.
    """
    if not REPORT_ADDRESS_GUARD:
        return True
    now = time.time() if now is None else now
    material = f"report:{target}:{client_address(request)}".encode("utf-8")
    key = hmac.new(auth.SECRET_KEY.encode("utf-8"), material, hashlib.sha256).hexdigest()
    with _report_lock:
        while _report_addresses:
            oldest_key, seen_at = next(iter(_report_addresses.items()))
            if now - seen_at < REPORT_ADDRESS_TTL_SECONDS:
                break
            _report_addresses.popitem(last=False)
        if key in _report_addresses:
            return False
        _report_addresses[key] = now
        while len(_report_addresses) > REPORT_ADDRESS_MAX_ENTRIES:
            _report_addresses.popitem(last=False)
    return True


def clear_report_addresses() -> None:
    with _report_lock:
        _report_addresses.clear()
