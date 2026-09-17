"""Signed, pseudonymous browser identity for public abuse controls.

The token is stored in an HTTP-only cookie and only its keyed hash is persisted.
No IP address or browser fingerprint is stored with reactions or reports.
"""
import hashlib
import hmac
import os
import secrets

from fastapi import Request

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
