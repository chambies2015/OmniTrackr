"""Phone and desktop notifications (Web Push) for the bell's notifications.

Members opt in per device from the notification bell. Every notification the
app already creates (friend requests, takes, goal reached, release day alerts
and so on) is then also pushed to that member's devices, so it reaches them
with the site closed. Nothing here changes how the bell works.

Implemented with the standard libraries the app already ships (cryptography,
PyJWT, httpx) rather than a new dependency:

* RFC 8291 message encryption (aes128gcm content coding, RFC 8188)
* RFC 8292 VAPID: a signed token that identifies this site to the push service

The signing key is created once and stored in ``web_push_keys`` unless the
``VAPID_PRIVATE_KEY`` environment variable provides one, so no setup is needed.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional
from urllib.parse import urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models

logger = logging.getLogger(__name__)

RECORD_SIZE = 4096
TTL_SECONDS = 24 * 60 * 60
MAX_DEVICES_PER_MEMBER = 10
MAX_FAILURES = 5
MAX_BODY_CHARS = 240
REQUEST_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# Browsers only hand out endpoints on their vendor's push service. Accepting any
# other host would let a member make the server POST to arbitrary URLs.
PUSH_SERVICE_HOSTS = (
    "fcm.googleapis.com",            # Chrome, Edge (Chromium), Android, Opera, Samsung
    "push.services.mozilla.com",     # Firefox (updates.push.services.mozilla.com)
    "notify.windows.com",            # Legacy Edge / Windows (wns2-*.notify.windows.com)
    "push.apple.com",                # Safari on macOS, iPhone and iPad (web.push.apple.com)
)
B64URL = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")

TITLES = {
    "friend_request_received": "New friend request",
    "friend_request_accepted": "Friend request accepted",
    "recommendation_received": "A friend sent you a recommendation",
    "recommendation_invitation": "A friend wants your recommendations",
    "take_received": "A friend shared their take",
    "goal_reached": "Goal reached",
    "challenge_complete": "Challenge complete",
    "badge_earned": "New badge",
    "release_day": "Out today",
    "review_helpful": "Your review helped someone",
    "shared_list_added": "You're on a shared list",
    "shared_list_joined": "Someone joined your shared list",
    "shared_list_item": "New on a shared list",
    "friend_invite_accepted": "A friend joined",
}


# ---------------------------------------------------------------- encoding

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    value = value.strip()
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _public_bytes(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(payload: bytes, ua_public: bytes, auth_secret: bytes,
            *, sender_key: Optional[ec.EllipticCurvePrivateKey] = None, salt: Optional[bytes] = None) -> bytes:
    """Encrypt ``payload`` for one subscription (RFC 8291, single aes128gcm record).

    ``sender_key`` and ``salt`` are fresh for every message; they are parameters
    only so the RFC's worked example can be checked in tests.
    """
    if len(payload) > RECORD_SIZE - 17 - 86:
        raise ValueError("Push payload is too large")
    sender_key = sender_key or ec.generate_private_key(ec.SECP256R1())
    salt = salt or os.urandom(16)
    as_public = _public_bytes(sender_key.public_key())
    receiver = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    shared = sender_key.exchange(ec.ECDH(), receiver)
    ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    header = salt + RECORD_SIZE.to_bytes(4, "big") + bytes([len(as_public)]) + as_public
    return header + ciphertext


# ---------------------------------------------------------------- VAPID key

_KEY_LOCK = threading.Lock()
_KEY: Optional[ec.EllipticCurvePrivateKey] = None


def _load_env_key(raw: str) -> ec.EllipticCurvePrivateKey:
    raw = raw.strip()
    if "BEGIN" in raw:
        return serialization.load_pem_private_key(raw.replace("\\n", "\n").encode(), password=None)
    return ec.derive_private_key(int.from_bytes(b64url_decode(raw), "big"), ec.SECP256R1())


def signing_key(db: Session) -> ec.EllipticCurvePrivateKey:
    """This site's VAPID key: from the environment, else the stored row, else a new stored one."""
    global _KEY
    if _KEY is not None:
        return _KEY
    with _KEY_LOCK:
        if _KEY is not None:
            return _KEY
        env_key = os.getenv("VAPID_PRIVATE_KEY", "").strip()
        if env_key:
            _KEY = _load_env_key(env_key)
            return _KEY
        row = db.get(models.WebPushKey, 1)
        if row is None:
            key = ec.generate_private_key(ec.SECP256R1())
            pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode("ascii")
            try:
                db.add(models.WebPushKey(id=1, private_pem=pem))
                db.commit()
            except IntegrityError:
                # Another worker stored its key first; everyone uses that one.
                db.rollback()
            row = db.get(models.WebPushKey, 1)
        _KEY = serialization.load_pem_private_key(row.private_pem.encode("ascii"), password=None)
        return _KEY


def public_key(db: Session) -> str:
    """The application server key browsers subscribe with (base64url, uncompressed point)."""
    return b64url_encode(_public_bytes(signing_key(db).public_key()))


def _reset_key_cache() -> None:
    global _KEY
    _KEY = None


def subject() -> str:
    configured = os.getenv("VAPID_SUBJECT", "").strip()
    if configured.startswith(("mailto:", "https://")):
        return configured
    return "mailto:" + os.getenv("MAIL_FROM", "noreply@omnitrackr.xyz")


def vapid_headers(endpoint: str, key: ec.EllipticCurvePrivateKey, now: Optional[int] = None) -> dict:
    parts = urlsplit(endpoint)
    now = int(now if now is not None else time.time())
    token = jwt.encode({"aud": f"{parts.scheme}://{parts.netloc}", "exp": now + 12 * 60 * 60, "sub": subject()},
                       key, algorithm="ES256")
    return {"Authorization": f"vapid t={token}, k={b64url_encode(_public_bytes(key.public_key()))}"}


# ---------------------------------------------------------------- subscriptions

def valid_endpoint(endpoint: str) -> bool:
    if not isinstance(endpoint, str) or not 20 <= len(endpoint) <= 1024:
        return False
    try:
        parts = urlsplit(endpoint)
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443):
        return False
    return any(host == allowed or host.endswith("." + allowed) for allowed in PUSH_SERVICE_HOSTS)


def valid_keys(p256dh: str, auth: str) -> bool:
    if not (isinstance(p256dh, str) and isinstance(auth, str)):
        return False
    if not (B64URL.match(p256dh) and B64URL.match(auth)) or len(p256dh) > 128 or len(auth) > 64:
        return False
    try:
        point, secret = b64url_decode(p256dh), b64url_decode(auth)
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
    except (ValueError, TypeError):
        return False
    return len(point) == 65 and len(secret) == 16


def save_subscription(db: Session, user_id: int, endpoint: str, p256dh: str, auth: str, _retry: bool = True) -> bool:
    """Store (or move to this member) one device's subscription; keeps the newest ten per member.

    Returns True when the device is newly turned on for this member.
    """
    try:
        return _save_subscription(db, user_id, endpoint, p256dh, auth)
    except IntegrityError:
        # The page-load sync and the "Turn on" click raced to insert the same endpoint.
        db.rollback()
        if not _retry:
            raise
        return save_subscription(db, user_id, endpoint, p256dh, auth, _retry=False)


def _save_subscription(db: Session, user_id: int, endpoint: str, p256dh: str, auth: str) -> bool:
    row = db.query(models.PushSubscription).filter(models.PushSubscription.endpoint == endpoint).first()
    fresh = row is None or row.user_id != user_id
    if row is None:
        row = models.PushSubscription(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        db.add(row)
    else:
        # The same browser signed in as someone else, or refreshed its keys.
        if fresh:
            row.created_at = datetime.utcnow()
        row.user_id, row.p256dh, row.auth, row.failure_count = user_id, p256dh, auth, 0
    db.flush()
    extra = (db.query(models.PushSubscription).filter(models.PushSubscription.user_id == user_id)
             .order_by(models.PushSubscription.created_at.desc(), models.PushSubscription.id.desc())
             .offset(MAX_DEVICES_PER_MEMBER).all())
    for old in extra:
        db.delete(old)
    db.commit()
    return fresh


def remove_subscription(db: Session, user_id: int, endpoint: str) -> bool:
    count = (db.query(models.PushSubscription)
             .filter(models.PushSubscription.user_id == user_id, models.PushSubscription.endpoint == endpoint)
             .delete(synchronize_session=False))
    db.commit()
    return bool(count)


# ---------------------------------------------------------------- sending

def safe_link(link: Optional[str]) -> str:
    """Only same-site paths open from a notification."""
    if isinstance(link, str) and link.startswith("/") and not link.startswith("//") and "\\" not in link \
            and len(link) <= 300:
        return link
    return "/"


def payload_for(kind: str, message: str, link: Optional[str]) -> bytes:
    body = (message or "").strip()
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS - 1].rstrip() + "…"
    data = {"title": TITLES.get(kind, "OmniTrackr"), "body": body, "url": safe_link(link), "tag": kind or "omnitrackr"}
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def send_one(http: httpx.Client, key: ec.EllipticCurvePrivateKey, row: models.PushSubscription, payload: bytes) -> int:
    """POST one encrypted message; returns the push service's status code (0 when unreachable)."""
    if not valid_endpoint(row.endpoint):
        return 410
    body = encrypt(payload, b64url_decode(row.p256dh), b64url_decode(row.auth))
    headers = {
        **vapid_headers(row.endpoint, key),
        "TTL": str(TTL_SECONDS),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "Urgency": "normal",
    }
    try:
        return http.post(row.endpoint, content=body, headers=headers).status_code
    except httpx.HTTPError:
        return 0


def deliver(db: Session, messages: list[tuple[int, str, str, Optional[str]]],
            http: Optional[httpx.Client] = None) -> dict:
    """Push each (user_id, type, message, link) to that member's devices.

    Gone subscriptions (404/410) are removed; one that keeps failing is dropped
    after a few tries. Returns counts for logging and tests.
    """
    stats = {"sent": 0, "removed": 0, "failed": 0}
    user_ids = {user_id for user_id, *_ in messages}
    if not user_ids:
        return stats
    rows = (db.query(models.PushSubscription)
            .join(models.User, models.User.id == models.PushSubscription.user_id)
            .filter(models.PushSubscription.user_id.in_(user_ids), models.User.is_active == True)
            .all())
    if not rows:
        return stats
    devices: dict[int, list[models.PushSubscription]] = {}
    for row in rows:
        devices.setdefault(row.user_id, []).append(row)
    key = signing_key(db)
    owns_client = http is None
    http = http or httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=False)
    try:
        for user_id, kind, message, link in messages:
            payload = payload_for(kind, message, link)
            for row in devices.get(user_id, []):
                if row in db.deleted:
                    continue
                status = send_one(http, key, row, payload)
                if 200 <= status < 300:
                    row.last_success_at, row.failure_count = datetime.utcnow(), 0
                    stats["sent"] += 1
                elif status in (404, 410) or row.failure_count + 1 >= MAX_FAILURES:
                    db.delete(row)
                    stats["removed"] += 1
                else:
                    row.failure_count += 1
                    stats["failed"] += 1
        db.commit()
    finally:
        if owns_client:
            http.close()
    return stats


# ---------------------------------------------------------------- dispatch hook

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="web-push")
PENDING_KEY = "web_push_pending"


def dispatch_enabled() -> bool:
    if os.getenv("WEB_PUSH", "").lower() in {"0", "false", "off"}:
        return False
    return os.getenv("TESTING", "").lower() != "true"


def _run(bind, messages) -> None:
    db = Session(bind=bind)
    try:
        stats = deliver(db, messages)
        if stats["sent"] or stats["removed"]:
            logger.info("Web push: %s", stats)
    except Exception:
        logger.exception("Web push delivery failed")
        db.rollback()
    finally:
        db.close()


def submit(bind, messages) -> None:
    """Hand a committed batch to the background sender (tests replace this)."""
    _EXECUTOR.submit(_run, bind, messages)


@event.listens_for(Session, "after_flush")
def _collect(session: Session, flush_context) -> None:
    fresh = [(obj.user_id, obj.type or "", obj.message or "", obj.link)
             for obj in session.new if isinstance(obj, models.Notification) and obj.user_id is not None]
    if fresh:
        session.info.setdefault(PENDING_KEY, []).extend(fresh)


@event.listens_for(Session, "after_commit")
def _send_committed(session: Session) -> None:
    messages = session.info.pop(PENDING_KEY, None)
    if not messages or not dispatch_enabled():
        return
    try:
        submit(session.get_bind(), messages)
    except Exception:
        logger.exception("Could not queue web push")


@event.listens_for(Session, "after_rollback")
def _forget(session: Session) -> None:
    session.info.pop(PENDING_KEY, None)
