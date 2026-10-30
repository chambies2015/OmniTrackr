"""
Optional two-factor sign-in: a six-digit code from an authenticator app
(RFC 6238 TOTP), with one-time recovery codes for a lost phone.

Nothing changes for a member until they turn it on in Settings. Once it is on,
a correct password (or a Google sign-in) only gets as far as a short-lived,
signed challenge cookie; the session cookie is set after the code checks out.

The authenticator secret is stored encrypted and the recovery codes as keyed
hashes, both derived from SECRET_KEY. Changing SECRET_KEY already signs every
member out; with this it also invalidates authenticator setups, so members
would need a recovery code to get back in.
"""
import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from . import auth, models

ISSUER = "OmniTrackr"
STEP_SECONDS = 30
DIGITS = 6
# One step either side covers a phone clock that's up to 30 seconds off.
DRIFT_STEPS = 1
RECOVERY_CODE_COUNT = 10
# Crockford base32: no i, l, o or u, so codes read back without mix-ups.
RECOVERY_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
RECOVERY_CODE_LENGTH = 10

CHALLENGE_COOKIE = "omnitrackr_2fa_challenge"
CHALLENGE_MAX_AGE_SECONDS = 10 * 60
DEVICE_COOKIE = "omnitrackr_2fa_device"
DEVICE_MAX_AGE_SECONDS = 30 * 24 * 3600
COOKIE_PATH = "/auth"


# ---------------------------------------------------------------- keys

def _derived_key(purpose: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=b"omnitrackr two-factor " + purpose).derive(auth.SECRET_KEY.encode("utf-8"))


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_derived_key(b"secret")))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_secret(stored: str) -> Optional[str]:
    try:
        return _fernet().decrypt(stored.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError, AttributeError):
        return None


# ---------------------------------------------------------------- authenticator codes

def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def grouped_secret(secret: str) -> str:
    """ABCD EFGH ... for people typing the key in by hand."""
    return " ".join(secret[i:i + 4] for i in range(0, len(secret), 4))


def otpauth_uri(secret: str, account_name: str) -> str:
    label = quote(f"{ISSUER}:{account_name}", safe="")
    return (f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}"
            f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}")


def current_step(now: Optional[float] = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10 ** DIGITS)).zfill(DIGITS)


def matching_step(secret: str, code: str, last_used_step: Optional[int] = None,
                  now: Optional[float] = None) -> Optional[int]:
    """The time step the code belongs to, or None. A step already used can't be used again."""
    if len(code) != DIGITS or not code.isdigit():
        return None
    middle = current_step(now)
    found = None
    for step in range(middle - DRIFT_STEPS, middle + DRIFT_STEPS + 1):
        if last_used_step is not None and step <= last_used_step:
            continue
        if hmac.compare_digest(code_at(secret, step), code):
            found = step
    return found


def qr_data_uri(text: str) -> str:
    """An SVG QR code as a data: URI, so the secret never leaves this server."""
    import qrcode
    import qrcode.image.svg

    image = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    svg = image.to_string()
    return "data:image/svg+xml;base64," + base64.b64encode(svg).decode("ascii")


# ---------------------------------------------------------------- recovery codes

def normalize_code(raw: str) -> str:
    """Lowercase, no spaces or dashes, and the letters people mistake for digits mapped back."""
    cleaned = "".join(ch for ch in (raw or "").strip().lower() if ch not in " -\t")
    return cleaned.translate(str.maketrans({"o": "0", "i": "1", "l": "1"}))


def new_recovery_codes() -> list[str]:
    codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(RECOVERY_CODE_LENGTH))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def _recovery_hash(normalized: str) -> str:
    return hmac.new(_derived_key(b"recovery"), normalized.encode("ascii"), hashlib.sha256).hexdigest()


def hash_recovery_codes(codes: list[str]) -> str:
    return json.dumps([_recovery_hash(normalize_code(code)) for code in codes])


def _stored_hashes(row: models.UserTwoFactor) -> list[str]:
    try:
        hashes_ = json.loads(row.recovery_codes or "[]")
    except (TypeError, ValueError):
        return []
    return [h for h in hashes_ if isinstance(h, str)] if isinstance(hashes_, list) else []


def recovery_codes_left(row: Optional[models.UserTwoFactor]) -> int:
    return len(_stored_hashes(row)) if row is not None else 0


# ---------------------------------------------------------------- per-member state

def setup_for(db: Session, user_id: int) -> Optional[models.UserTwoFactor]:
    return db.query(models.UserTwoFactor).filter(models.UserTwoFactor.user_id == user_id).first()


def enabled_for(db: Session, user: models.User) -> Optional[models.UserTwoFactor]:
    """The member's two-factor setup when it is switched on, else None."""
    row = setup_for(db, user.id)
    return row if row is not None and row.enabled_at is not None else None


def check_code(row: models.UserTwoFactor, raw: str, *, allow_recovery: bool = True,
               now: Optional[float] = None) -> Optional[str]:
    """Check an authenticator or recovery code and use it up.

    Returns "app" or "recovery" on success (the caller commits), None otherwise.
    """
    code = normalize_code(raw)
    if len(code) == DIGITS and code.isdigit():
        secret = decrypt_secret(row.secret_encrypted)
        step = matching_step(secret, code, row.last_used_step, now) if secret else None
        if step is None:
            return None
        row.last_used_step = step
        return "app"
    if allow_recovery and len(code) == RECOVERY_CODE_LENGTH and all(ch in RECOVERY_ALPHABET for ch in code):
        wanted = _recovery_hash(code)
        stored = _stored_hashes(row)
        for index, candidate in enumerate(stored):
            if hmac.compare_digest(candidate, wanted):
                row.recovery_codes = json.dumps(stored[:index] + stored[index + 1:])
                return "recovery"
    return None


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------- sign-in challenge

def _challenge_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(auth.SECRET_KEY, salt="two-factor-challenge")


def new_challenge(user: models.User, via: str) -> str:
    return _challenge_serializer().dumps({
        "uid": int(user.id), "pv": auth.password_fingerprint(user.hashed_password), "via": via,
    })


def read_challenge(value: Optional[str]) -> Optional[dict]:
    """{uid, pv, via} from a challenge cookie, or None if absent, expired or tampered."""
    if not value or len(value) > 1024:
        return None
    try:
        data = _challenge_serializer().loads(value, max_age=CHALLENGE_MAX_AGE_SECONDS)
    except (BadSignature, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("uid"), int) or not isinstance(data.get("pv"), str):
        return None
    return data


def set_challenge_cookie(response, value: str) -> None:
    response.set_cookie(key=CHALLENGE_COOKIE, value=value, max_age=CHALLENGE_MAX_AGE_SECONDS,
                        httponly=True, secure=auth.ENVIRONMENT == "production", samesite="lax",
                        path=COOKIE_PATH)


def clear_challenge_cookie(response) -> None:
    response.delete_cookie(key=CHALLENGE_COOKIE, path=COOKIE_PATH, samesite="lax",
                           secure=auth.ENVIRONMENT == "production", httponly=True)


# ---------------------------------------------------------------- remembered browsers

def _device_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(auth.SECRET_KEY, salt="two-factor-device")


def _device_marker(user: models.User, row: models.UserTwoFactor) -> str:
    # A new password, turning two-factor off and on, or "forget remembered browsers"
    # all change the marker, so every remembered browser asks for a code again.
    material = f"{user.id}:{row.enabled_at.isoformat() if row.enabled_at else ''}:{row.trusted_epoch or 0}:" \
               f"{auth.password_fingerprint(user.hashed_password)}"
    return hmac.new(_derived_key(b"device"), material.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def remembered_device(value: Optional[str], user: models.User, row: models.UserTwoFactor) -> bool:
    if not value or len(value) > 1024:
        return False
    try:
        data = _device_serializer().loads(value, max_age=DEVICE_MAX_AGE_SECONDS)
    except (BadSignature, ValueError):
        return False
    return (isinstance(data, dict) and data.get("uid") == user.id
            and isinstance(data.get("m"), str) and hmac.compare_digest(data["m"], _device_marker(user, row)))


def set_device_cookie(response, user: models.User, row: models.UserTwoFactor) -> None:
    value = _device_serializer().dumps({"uid": int(user.id), "m": _device_marker(user, row)})
    response.set_cookie(key=DEVICE_COOKIE, value=value, max_age=DEVICE_MAX_AGE_SECONDS,
                        httponly=True, secure=auth.ENVIRONMENT == "production", samesite="lax",
                        path=COOKIE_PATH)


def code_needed(db: Session, request, user: models.User) -> bool:
    """True when this sign-in must stop for a code: two-factor is on and this browser isn't remembered."""
    row = enabled_for(db, user)
    if row is None:
        return False
    cookie = request.cookies.get(DEVICE_COOKIE) if request is not None else None
    return not remembered_device(cookie, user, row)
