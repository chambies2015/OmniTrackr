"""
Passkeys: sign in with a fingerprint, face or device PIN instead of a password
(WebAuthn, the standard behind Apple, Google and Microsoft passkeys).

A member adds one from Settings > Sign-in. The browser asks the device to make a
key pair for this site; we keep the public half and the credential id in
`user_passkeys`. Logging in later is a signed challenge: the device proves it
holds the private half, and the browser only ever offers passkeys made for this
site's own domain, which is what makes it phishing-proof.

Every passkey is made and used with user verification (the fingerprint, face or
PIN), so a passkey sign-in counts as both factors and skips the authenticator
code. Passwords, Google and two-factor keep working exactly as before; members
without a passkey row never see a difference.

This file does the WebAuthn checks itself with the `cryptography` package that
is already installed: a small CBOR reader, the authenticator data layout, COSE
public keys (ES256, RS256 and Ed25519) and the signature over
authenticatorData + sha256(clientDataJSON). Attestation statements are not
checked, which is the usual choice for a consumer site: the member picked the
device, and its manufacturer certificate adds nothing for them.

Settings (both optional):
  PASSKEY_RP_ID    the relying party id, normally the bare domain (omnitrackr.xyz).
                   Defaults to the site's own host with any www. removed, so one
                   passkey works on omnitrackr.xyz and www.omnitrackr.xyz alike.
  PASSKEY_ORIGINS  extra allowed origins, comma separated (for a staging host).
"""
import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from . import auth, models

RP_NAME = "OmniTrackr"
DEFAULT_RP_ID = "omnitrackr.xyz"

CHALLENGE_COOKIE = "omnitrackr_passkey_challenge"
CHALLENGE_MAX_AGE_SECONDS = 5 * 60
REGISTER_COOKIE_PATH = "/account/passkeys"
LOGIN_COOKIE_PATH = "/auth/passkey"
PROMPT_TIMEOUT_MS = 90 * 1000

MAX_PASSKEYS_PER_MEMBER = 10
NAME_MAX_LENGTH = 60
MAX_FIELD_BYTES = 64 * 1024

# COSE algorithm identifiers, in the order we offer them to the browser.
ALG_ES256 = -7
ALG_EDDSA = -8
ALG_RS256 = -257
SUPPORTED_ALGORITHMS = (ALG_ES256, ALG_EDDSA, ALG_RS256)

FLAG_USER_PRESENT = 0x01
FLAG_USER_VERIFIED = 0x04
FLAG_BACKUP_ELIGIBLE = 0x08
FLAG_BACKED_UP = 0x10
FLAG_ATTESTED_CREDENTIAL = 0x40

KNOWN_TRANSPORTS = ("usb", "nfc", "ble", "internal", "hybrid", "smart-card")


class PasskeyError(Exception):
    """A response the browser sent that we can't accept; the message is safe to show."""


# ---------------------------------------------------------------- encoding

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64url(text, what: str = "response") -> bytes:
    if not isinstance(text, str) or not text or len(text) > MAX_FIELD_BYTES:
        raise PasskeyError(f"The passkey {what} was missing or we couldn't read it.")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (ValueError, binascii.Error):
        raise PasskeyError(f"The passkey {what} was missing or we couldn't read it.")


def canonical_credential_id(text) -> Optional[str]:
    """The id as we store it (base64url, no padding), whatever padding the browser used."""
    try:
        raw = unb64url(text, "id")
    except PasskeyError:
        return None
    return b64url(raw) if 16 <= len(raw) <= 1023 else None


# ---------------------------------------------------------------- where we are

def _hostname(netloc: str) -> str:
    host = (netloc or "").strip().lower()
    if host.startswith("["):
        return host.split("]")[0] + "]"
    return host.split(":")[0]


def _site_hosts() -> set[str]:
    from .google_signin import _known_hosts
    return {_hostname(host) for host in _known_hosts()}


def _request_host(request) -> str:
    if request is None:
        return ""
    return _hostname(request.headers.get("host") or "")


def _bare(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def rp_id(request=None) -> str:
    """The relying party id: the domain a passkey is tied to."""
    override = os.getenv("PASSKEY_RP_ID", "").strip().lower()
    if override:
        return override
    host = _request_host(request)
    if host and host in _site_hosts():
        return _bare(host)
    if host and auth.ENVIRONMENT != "production":
        return host  # localhost and friends while developing
    from .email import APP_URL
    return _bare(_hostname(urlparse(APP_URL).netloc)) or DEFAULT_RP_ID


def expected_origins(request=None) -> set[str]:
    """Origins a passkey response may come from: the site's own hosts over https."""
    origins = set()
    for host in _site_hosts():
        origins.add(f"https://{host}")
    extra = os.getenv("PASSKEY_ORIGINS", "")
    origins.update(item.strip().rstrip("/").lower() for item in extra.split(",") if item.strip())
    if request is not None:
        host = (request.headers.get("host") or "").strip().lower()
        if host and auth.ENVIRONMENT != "production":
            origins.add(f"{request.url.scheme}://{host}")
        elif host and _hostname(host) in _site_hosts():
            origins.add(f"https://{host}")
    return origins


# ---------------------------------------------------------------- challenge cookie

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(auth.SECRET_KEY, salt="passkey-challenge")


def new_challenge() -> bytes:
    return secrets.token_bytes(32)


def challenge_cookie_value(kind: str, challenge: bytes, user_id: Optional[int] = None) -> str:
    return _serializer().dumps({"k": kind, "c": b64url(challenge), "uid": user_id})


def read_challenge(value: Optional[str], kind: str, user_id: Optional[int] = None) -> Optional[bytes]:
    """The challenge we issued for this kind of prompt (and this member), or None."""
    if not value or len(value) > 1024:
        return None
    try:
        data = _serializer().loads(value, max_age=CHALLENGE_MAX_AGE_SECONDS)
    except (BadSignature, ValueError):
        return None
    if not isinstance(data, dict) or data.get("k") != kind or data.get("uid") != user_id:
        return None
    try:
        challenge = unb64url(data.get("c"), "challenge")
    except PasskeyError:
        return None
    return challenge if len(challenge) == 32 else None


def set_challenge_cookie(response, value: str, path: str) -> None:
    response.set_cookie(key=CHALLENGE_COOKIE, value=value, max_age=CHALLENGE_MAX_AGE_SECONDS,
                        httponly=True, secure=auth.ENVIRONMENT == "production", samesite="lax", path=path)


def clear_challenge_cookie(response, path: str) -> None:
    response.delete_cookie(key=CHALLENGE_COOKIE, path=path, samesite="lax",
                           secure=auth.ENVIRONMENT == "production", httponly=True)


# ---------------------------------------------------------------- CBOR (RFC 8949, the subset authenticators use)

_CBOR_MAX_ITEMS = 10_000


def _cbor_item(data: bytes, pos: int, depth: int = 0):
    if depth > 16 or pos >= len(data):
        raise PasskeyError("We couldn't read what your device sent. Try again.")
    initial = data[pos]
    major, info = initial >> 5, initial & 0x1F
    pos += 1
    if info < 24:
        argument = info
    elif info in (24, 25, 26, 27):
        width = 1 << (info - 24)
        if pos + width > len(data):
            raise PasskeyError("We couldn't read what your device sent. Try again.")
        argument = int.from_bytes(data[pos:pos + width], "big")
        pos += width
    else:
        raise PasskeyError("We couldn't read what your device sent. Try again.")  # indefinite lengths aren't used here

    if major == 0:
        return argument, pos
    if major == 1:
        return -1 - argument, pos
    if major in (2, 3):
        end = pos + argument
        if argument > len(data) or end > len(data):
            raise PasskeyError("We couldn't read what your device sent. Try again.")
        chunk = bytes(data[pos:end])
        if major == 3:
            try:
                return chunk.decode("utf-8"), end
            except UnicodeDecodeError:
                raise PasskeyError("We couldn't read what your device sent. Try again.")
        return chunk, end
    if major == 4:
        if argument > _CBOR_MAX_ITEMS:
            raise PasskeyError("We couldn't read what your device sent. Try again.")
        items = []
        for _ in range(argument):
            item, pos = _cbor_item(data, pos, depth + 1)
            items.append(item)
        return items, pos
    if major == 5:
        if argument > _CBOR_MAX_ITEMS:
            raise PasskeyError("We couldn't read what your device sent. Try again.")
        mapping = {}
        for _ in range(argument):
            key, pos = _cbor_item(data, pos, depth + 1)
            value, pos = _cbor_item(data, pos, depth + 1)
            if not isinstance(key, (int, str, bytes)):
                raise PasskeyError("We couldn't read what your device sent. Try again.")
            mapping[key] = value
        return mapping, pos
    if major == 7:
        if info == 20:
            return False, pos
        if info == 21:
            return True, pos
        if info in (22, 23):
            return None, pos
    raise PasskeyError("We couldn't read what your device sent. Try again.")


def cbor_decode(data: bytes):
    """(value, bytes consumed) for the first CBOR item in data."""
    return _cbor_item(bytes(data), 0)


# ---------------------------------------------------------------- authenticator data and keys

def parse_authenticator_data(raw: bytes, *, need_credential: bool) -> dict:
    if len(raw) < 37:
        raise PasskeyError("We couldn't read what your device sent. Try again.")
    flags = raw[32]
    out = {
        "rp_id_hash": bytes(raw[:32]),
        "user_present": bool(flags & FLAG_USER_PRESENT),
        "user_verified": bool(flags & FLAG_USER_VERIFIED),
        "backup_eligible": bool(flags & FLAG_BACKUP_ELIGIBLE),
        "backed_up": bool(flags & FLAG_BACKED_UP),
        "sign_count": int.from_bytes(raw[33:37], "big"),
        "aaguid": None,
        "credential_id": None,
        "public_key": None,
    }
    pos = 37
    if flags & FLAG_ATTESTED_CREDENTIAL:
        if len(raw) < pos + 18:
            raise PasskeyError("We couldn't read what your device sent. Try again.")
        out["aaguid"] = str(uuid.UUID(bytes=bytes(raw[pos:pos + 16])))
        pos += 16
        length = int.from_bytes(raw[pos:pos + 2], "big")
        pos += 2
        if length < 16 or length > 1023 or len(raw) < pos + length:
            raise PasskeyError("We couldn't read what your device sent. Try again.")
        out["credential_id"] = bytes(raw[pos:pos + length])
        pos += length
        _, consumed = cbor_decode(raw[pos:])
        out["public_key"] = bytes(raw[pos:pos + consumed])
    elif need_credential:
        raise PasskeyError("The passkey response didn't include a new key.")
    return out


def load_public_key(cose: bytes):
    """(public key object, algorithm) from a COSE_Key, for the algorithms we offer."""
    key, _ = cbor_decode(cose)
    if not isinstance(key, dict):
        raise PasskeyError("That kind of passkey isn't supported here.")
    kty, alg = key.get(1), key.get(3)
    try:
        if kty == 2 and alg == ALG_ES256:
            x, y = key.get(-2), key.get(-3)
            if key.get(-1) != 1 or not (isinstance(x, bytes) and isinstance(y, bytes) and len(x) == 32 and len(y) == 32):
                raise PasskeyError("That kind of passkey isn't supported here.")
            numbers = ec.EllipticCurvePublicNumbers(int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1())
            return numbers.public_key(), alg
        if kty == 3 and alg == ALG_RS256:
            n, e = key.get(-1), key.get(-2)
            if not (isinstance(n, bytes) and isinstance(e, bytes) and 256 <= len(n) <= 1024):
                raise PasskeyError("That kind of passkey isn't supported here.")
            numbers = rsa.RSAPublicNumbers(int.from_bytes(e, "big"), int.from_bytes(n, "big"))
            return numbers.public_key(), alg
        if kty == 1 and alg == ALG_EDDSA:
            x = key.get(-2)
            if key.get(-1) != 6 or not (isinstance(x, bytes) and len(x) == 32):
                raise PasskeyError("That kind of passkey isn't supported here.")
            return ed25519.Ed25519PublicKey.from_public_bytes(x), alg
    except ValueError:
        raise PasskeyError("That kind of passkey isn't supported here.")
    raise PasskeyError("That kind of passkey isn't supported here.")


def verify_signature(cose: bytes, signed: bytes, signature: bytes) -> bool:
    key, alg = load_public_key(cose)
    try:
        if alg == ALG_ES256:
            key.verify(signature, signed, ec.ECDSA(hashes.SHA256()))
        elif alg == ALG_RS256:
            key.verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
        else:
            key.verify(signature, signed)
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def _client_data(raw: bytes, expected_type: str, challenge: bytes, origins: set[str]) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise PasskeyError("We couldn't read what your device sent. Try again.")
    if not isinstance(data, dict) or data.get("type") != expected_type:
        raise PasskeyError("We couldn't read what your device sent. Try again.")
    got = data.get("challenge")
    if not isinstance(got, str) or not hmac.compare_digest(unb64url(got, "challenge"), challenge):
        raise PasskeyError("That passkey prompt expired. Try again.")
    origin = data.get("origin")
    if not isinstance(origin, str) or origin.rstrip("/").lower() not in origins or data.get("crossOrigin") is True:
        raise PasskeyError("That passkey request didn't come from this site's own address.")
    return data


def _check_rp(auth_data: dict, rp: str) -> None:
    if not hmac.compare_digest(auth_data["rp_id_hash"], hashlib.sha256(rp.encode("utf-8")).digest()):
        raise PasskeyError("That passkey was made for a different site.")
    if not auth_data["user_present"]:
        raise PasskeyError("The device didn't confirm you were there. Try again.")
    if not auth_data["user_verified"]:
        raise PasskeyError("Passkeys here need your fingerprint, face or device PIN. Turn on a screen lock, then try again.")


def _transports(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item in KNOWN_TRANSPORTS][:6]


def verify_registration(credential: dict, challenge: bytes, rp: str, origins: set[str]) -> dict:
    """Check a navigator.credentials.create() result; returns what to store."""
    if not isinstance(credential, dict) or credential.get("type", "public-key") != "public-key":
        raise PasskeyError("We couldn't read what your device sent. Try again.")
    response = credential.get("response") if isinstance(credential.get("response"), dict) else {}
    client_raw = unb64url(response.get("clientDataJSON"), "response")
    _client_data(client_raw, "webauthn.create", challenge, origins)
    attestation, _ = cbor_decode(unb64url(response.get("attestationObject"), "response"))
    if not isinstance(attestation, dict) or not isinstance(attestation.get("authData"), bytes):
        raise PasskeyError("We couldn't read what your device sent. Try again.")
    auth_data = parse_authenticator_data(attestation["authData"], need_credential=True)
    _check_rp(auth_data, rp)
    credential_id = auth_data["credential_id"]
    for field in ("rawId", "id"):
        if credential.get(field) is not None and unb64url(credential.get(field), "id") != credential_id:
            raise PasskeyError("We couldn't read what your device sent. Try again.")
    load_public_key(auth_data["public_key"])  # a key type we can check later, or an error now
    return {
        "credential_id": b64url(credential_id),
        "public_key": b64url(auth_data["public_key"]),
        "sign_count": auth_data["sign_count"],
        "aaguid": auth_data["aaguid"],
        "backup_eligible": auth_data["backup_eligible"],
        "backed_up": auth_data["backed_up"],
        "transports": _transports(response.get("transports")),
    }


def verify_assertion(row: models.UserPasskey, credential: dict, challenge: bytes, rp: str, origins: set[str]) -> dict:
    """Check a navigator.credentials.get() result against a stored passkey."""
    if not isinstance(credential, dict) or credential.get("type", "public-key") != "public-key":
        raise PasskeyError("We couldn't read what your device sent. Try again.")
    response = credential.get("response") if isinstance(credential.get("response"), dict) else {}
    client_raw = unb64url(response.get("clientDataJSON"), "response")
    _client_data(client_raw, "webauthn.get", challenge, origins)
    auth_raw = unb64url(response.get("authenticatorData"), "response")
    auth_data = parse_authenticator_data(auth_raw, need_credential=False)
    _check_rp(auth_data, rp)
    signed = auth_raw + hashlib.sha256(client_raw).digest()
    if not verify_signature(unb64url(row.public_key, "key"), signed, unb64url(response.get("signature"), "signature")):
        raise PasskeyError("That passkey didn't check out. Try again, or log in with your password.")
    new_count, old_count = auth_data["sign_count"], int(row.sign_count or 0)
    if (new_count or old_count) and new_count <= old_count:
        # A counter that went backwards means a copy of the key is in use somewhere.
        raise PasskeyError("That passkey looks like it was copied. Remove it in Settings and add a new one.")
    return {"sign_count": new_count, "backed_up": auth_data["backed_up"], "backup_eligible": auth_data["backup_eligible"]}


# ---------------------------------------------------------------- what the browser gets

def user_handle(user: models.User) -> bytes:
    """A stable, opaque id for the authenticator; it never contains the email or username."""
    return hashlib.sha256(f"omnitrackr passkey user {int(user.id)}".encode("utf-8")).digest()


def registration_options(user: models.User, rows: list, challenge: bytes, rp: str) -> dict:
    return {
        "rp": {"id": rp, "name": RP_NAME},
        "user": {"id": b64url(user_handle(user)), "name": user.username, "displayName": user.username},
        "challenge": b64url(challenge),
        "pubKeyCredParams": [{"type": "public-key", "alg": alg} for alg in SUPPORTED_ALGORITHMS],
        "timeout": PROMPT_TIMEOUT_MS,
        "excludeCredentials": [
            {"type": "public-key", "id": row.credential_id, "transports": transports_of(row)} for row in rows
        ],
        "authenticatorSelection": {
            "residentKey": "required",
            "requireResidentKey": True,
            "userVerification": "required",
        },
        "attestation": "none",
    }


def login_options(challenge: bytes, rp: str) -> dict:
    # No allowCredentials: the browser lists the member's passkeys for this site itself.
    return {
        "challenge": b64url(challenge),
        "rpId": rp,
        "timeout": PROMPT_TIMEOUT_MS,
        "userVerification": "required",
        "allowCredentials": [],
    }


# ---------------------------------------------------------------- per-member state

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def passkeys_for(db: Session, user_id: int) -> list:
    return (db.query(models.UserPasskey).filter(models.UserPasskey.user_id == user_id)
            .order_by(models.UserPasskey.created_at.asc(), models.UserPasskey.id.asc()).all())


def find_by_credential_id(db: Session, credential_id: str) -> Optional[models.UserPasskey]:
    return db.query(models.UserPasskey).filter(models.UserPasskey.credential_id == credential_id).first()


def has_passkeys(db: Session, user_id: int) -> bool:
    return db.query(models.UserPasskey.id).filter(models.UserPasskey.user_id == user_id).first() is not None


def transports_of(row) -> list[str]:
    try:
        value = json.loads(row.transports or "[]")
    except (TypeError, ValueError):
        return []
    return _transports(value)


def clean_name(raw) -> str:
    text = " ".join(str(raw or "").split())
    return text[:NAME_MAX_LENGTH]


def suggested_name(transports: list[str], backed_up: bool, taken: list[str]) -> str:
    """A readable default when the member doesn't name the passkey."""
    if "hybrid" in transports and "internal" not in transports:
        base = "Phone passkey"
    elif transports and "internal" not in transports and "hybrid" not in transports:
        base = "Security key"
    elif backed_up:
        base = "Synced passkey"
    else:
        base = "Passkey"
    lowered = {name.lower() for name in taken}
    if base.lower() not in lowered:
        return base
    number = 2
    while f"{base} {number}".lower() in lowered:
        number += 1
    return f"{base} {number}"


def to_public(row: models.UserPasskey) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        "last_used_at": row.last_used_at.isoformat() + "Z" if row.last_used_at else None,
        "backed_up": bool(row.backed_up),
        "transports": transports_of(row),
    }


# ---------------------------------------------------------------- notices

async def send_change_email(email: str, username: str, added: bool, name: str) -> None:
    """A heads-up when a passkey is added or removed, in case it wasn't the member."""
    from . import email as email_utils

    settings_url = f"{email_utils.APP_URL}/#settings-signin"
    safe_name = email_utils._escape_html(name or "A passkey")
    if added:
        subject = "A passkey was added to your OmniTrackr account"
        headline = "New passkey"
        body = (f"<strong>{safe_name}</strong> can now log in to your library with a fingerprint, face or device PIN. "
                "Your password and any two-factor codes still work as before.")
    else:
        subject = "A passkey was removed from your OmniTrackr account"
        headline = "Passkey removed"
        body = f"<strong>{safe_name}</strong> no longer opens your library. Your other ways to log in are unchanged."

    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">{headline}</h1>
            </div>
            <div style="padding: 30px; background-color: #f9f9f9;">
                <h2>Hi {email_utils._escape_html(username)},</h2>
                <p>{body}</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{settings_url}"
                       style="background-color: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                        Open sign-in settings
                    </a>
                </div>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
                <p style="color: #666; font-size: 12px;">
                    If this wasn't you, remove the passkey in Settings, change your password, and email omnitrackr@gmail.com.
                </p>
            </div>
        </body>
    </html>
    """
    message = email_utils.html_message(subject, [email], html)
    if email_utils.conf.MAIL_USERNAME and email_utils.conf.MAIL_PASSWORD:
        import asyncio
        await asyncio.wait_for(email_utils.FastMail(email_utils.conf).send_message(message), timeout=30.0)
    else:
        print(f"INFO: Passkey {'added' if added else 'removed'} notice for {email} (email not configured)")
