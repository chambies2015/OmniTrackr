"""Short-lived, anonymous proof for the optional Welcome Back Deck."""
import hashlib
import hmac
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import auth


RETURN_PROMPT_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24
_TOKEN_SALT = "omnitrackr-return-prompt-v1"


def _return_prompt_subject(user_id: int, nonce: str) -> str:
    """Create a per-proof, non-reversible account binding."""
    return hmac.new(
        auth.SECRET_KEY.encode("utf-8"),
        f"return-prompt-user:{int(user_id)}:{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_return_prompt_token(days_away: int, user_id: int) -> str:
    """Create an unlinkable, signed token for one eligible return experience."""
    bounded_days_away = max(3, min(int(days_away), 90))
    nonce = secrets.token_urlsafe(24)
    serializer = URLSafeTimedSerializer(auth.SECRET_KEY, salt=_TOKEN_SALT)
    return serializer.dumps({
        "nonce": nonce,
        "days_away": bounded_days_away,
        "subject": _return_prompt_subject(user_id, nonce),
    })


def return_prompt_days_away(token: str | None, user_id: int) -> int | None:
    """Return the server-issued absence window for a valid, fresh token."""
    if not token or len(token) > 512:
        return None
    serializer = URLSafeTimedSerializer(auth.SECRET_KEY, salt=_TOKEN_SALT)
    try:
        payload = serializer.loads(token, max_age=RETURN_PROMPT_TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    nonce = payload.get("nonce") if isinstance(payload, dict) else None
    days_away = payload.get("days_away") if isinstance(payload, dict) else None
    subject = payload.get("subject") if isinstance(payload, dict) else None
    if not isinstance(nonce, str) or not 24 <= len(nonce) <= 128:
        return None
    if not isinstance(days_away, int) or not 3 <= days_away <= 90:
        return None
    if not isinstance(subject, str) or not hmac.compare_digest(
        subject, _return_prompt_subject(user_id, nonce)
    ):
        return None
    return days_away


def return_prompt_token_digest(token: str) -> str:
    """Create the non-reversible value used only to reject duplicate events."""
    return hmac.new(
        auth.SECRET_KEY.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
