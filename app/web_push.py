"""Phone and desktop notifications (Web Push) for the bell's notifications.

Members opt in per device from the notification bell. Notifications the app
already creates (release days, club picks, friend recommendations and so on)
are then also pushed to that member's devices, so they reach them with the site
closed. Members choose which kinds are pushed and can set quiet hours; the
defaults push only the few that are worth a buzz. Nothing here changes how the
bell works.

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
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
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
    "episode_today": "New episode out",
    "away_nudge": "Still on your list",
    "review_helpful": "Your review helped someone",
    "shared_list_added": "You're on a shared list",
    "shared_list_joined": "Someone joined your shared list",
    "shared_list_item": "New on a shared list",
    "friend_invite_accepted": "A friend joined",
    "friend_recommendation": "A friend thinks you'd love this",
    "friend_recommendation_added": "Your recommendation landed",
    "club_pick": "New club pick",
    "club_post": "New in your watch club",
    "club_due_soon": "Club pick due soon",
    "discussion_reply": "New reply in a discussion",
    "discussion_report": "A discussion post was reported",
    "friend_feed_cheer": "A friend cheered you on",
    "push_enabled": "Notifications are on",
    "held": "While you were away",
    "memory": "On this day",
    "new_follower": "New follower",
}

# What members can switch on or off for their devices: (key, label, hint, on by default, types).
# The defaults stay quiet: things you'd want to hear about now are on; chatter and
# things you'll see next time you open OmniTrackr anyway are off.
TOPICS = (
    ("releases", "Out today", "Release days for titles, new seasons and sequels you track.", True,
     ("release_day",)),
    ("episodes", "New episodes", "The moment a new episode of a show or anime you're watching is out.", True,
     ("episode_today",)),
    ("clubs", "Watch club picks", "A new pick on your shared lists, and a nudge two days before it's due.", True,
     ("club_pick", "club_due_soon", "shared_list_added")),
    ("recommendations", "Friend recommendations", "When a friend sends you something, or answers when you ask.", True,
     ("friend_recommendation", "friend_recommendation_added", "recommendation_received",
      "recommendation_invitation", "take_received")),
    ("friends", "Friend requests", "New requests, and friends who accept or join from your invite.", True,
     ("friend_request_received", "friend_request_accepted", "friend_invite_accepted")),
    ("discussions", "Discussion replies", "Replies in title discussions you started or joined.", True,
     ("discussion_reply", "discussion_report")),
    ("club_talk", "Club talk and list updates", "New posts about a club pick, people joining and titles added.", False,
     ("club_post", "shared_list_joined", "shared_list_item")),
    ("milestones", "Cheers, badges and goals", "Cheers, helpful votes, badges, goals and challenges.", False,
     ("friend_feed_cheer", "review_helpful", "goal_reached", "badge_earned", "challenge_complete")),
    ("memories", "On this day", "Once a day, something you finished or started on this date in an earlier year.", False,
     ("memory",)),
    ("followers", "New followers", "When someone starts following your public profile.", False,
     ("new_follower",)),
    ("reminders", "When you've been away", "After a week without a visit, one reminder of what's waiting for you. "
     "Never more than one every two weeks, and it stops if you don't come back.", True,
     ("away_nudge",)),
)
TOPIC_KEYS = tuple(topic[0] for topic in TOPICS)
TOPIC_FOR_TYPE = {kind: topic[0] for topic in TOPICS for kind in topic[4]}
# Pushed whatever the switches say: the confirmation that push works, and notices about the member's own content.
ALWAYS_PUSHED = {"push_enabled", "review_unlisted", "collection_unlisted"}
# Anything new that isn't listed above follows the quietest switch until it's given a home.
FALLBACK_TOPIC = "milestones"
TIME_ZONE = re.compile(r"^[A-Za-z][A-Za-z0-9_+\-]*(/[A-Za-z0-9_+\-]+){0,2}$")


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


# ---------------------------------------------------------------- preferences

def topic_of(kind: str) -> Optional[str]:
    """The switch that decides whether this notification type is pushed (None: always pushed)."""
    if kind in ALWAYS_PUSHED:
        return None
    return TOPIC_FOR_TYPE.get(kind, FALLBACK_TOPIC)


def chosen_topics(pref: Optional[models.PushPreference]) -> dict[str, bool]:
    chosen = {key: default for key, _, _, default, _ in TOPICS}
    if pref is not None and pref.topics:
        try:
            saved = json.loads(pref.topics)
        except (TypeError, ValueError):
            saved = {}
        if isinstance(saved, dict):
            chosen.update({key: value for key, value in saved.items() if key in chosen and isinstance(value, bool)})
    return chosen


def wants(pref: Optional[models.PushPreference], kind: str) -> bool:
    topic = topic_of(kind)
    return topic is None or chosen_topics(pref)[topic]


def zone(name: Optional[str]) -> Optional[ZoneInfo]:
    if not isinstance(name, str) or not name or len(name) > 64 or not TIME_ZONE.match(name):
        return None
    try:
        return ZoneInfo(name)
    except Exception:
        return None


def in_quiet_hours(pref: Optional[models.PushPreference], now: Optional[datetime] = None) -> bool:
    """Whether it's within the member's quiet hours where they are. Unknown time zone: never quiet."""
    if pref is None or not pref.quiet_hours or pref.quiet_start == pref.quiet_end:
        return False
    tz = zone(pref.time_zone)
    if tz is None:
        return False
    now = now or datetime.utcnow()
    hour = now.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).hour
    start, end = pref.quiet_start, pref.quiet_end
    return start <= hour < end if start < end else hour >= start or hour < end


def quiet_started_at(pref: models.PushPreference, now: datetime) -> datetime:
    """When (UTC) the quiet hours the member is in right now began; everything since was held back."""
    tz = zone(pref.time_zone) or ZoneInfo("UTC")
    local = now.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    start = local.replace(hour=pref.quiet_start, minute=0, second=0, microsecond=0)
    if start > local:
        start -= timedelta(days=1)
    return start.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def get_preference(db: Session, user_id: int) -> models.PushPreference:
    """The member's row, made with the defaults when they have none yet (not committed)."""
    pref = db.get(models.PushPreference, user_id)
    if pref is None:
        pref = models.PushPreference(user_id=user_id, quiet_hours=True, quiet_start=22, quiet_end=8)
        db.add(pref)
    return pref


def settings_for(pref: Optional[models.PushPreference]) -> dict:
    chosen = chosen_topics(pref)
    return {
        "topics": [{"key": key, "label": label, "hint": hint, "on": chosen[key]}
                   for key, label, hint, _, _ in TOPICS],
        "quiet_hours": {"on": True if pref is None else bool(pref.quiet_hours),
                        "start": 22 if pref is None else pref.quiet_start,
                        "end": 8 if pref is None else pref.quiet_end},
        "time_zone": None if pref is None else pref.time_zone,
    }


def save_settings(db: Session, user_id: int, topics: Optional[dict] = None, quiet_hours: Optional[bool] = None,
                  quiet_start: Optional[int] = None, quiet_end: Optional[int] = None,
                  time_zone: Optional[str] = None, _retry: bool = True) -> models.PushPreference:
    pref = get_preference(db, user_id)
    if topics:
        chosen = chosen_topics(pref)
        chosen.update({key: bool(value) for key, value in topics.items() if key in chosen})
        changed = {key: value for key, value in chosen.items()
                   if value != next(topic[3] for topic in TOPICS if topic[0] == key)}
        pref.topics = json.dumps(changed, separators=(",", ":")) if changed else None
    if quiet_hours is not None:
        pref.quiet_hours = bool(quiet_hours)
    if quiet_start is not None:
        pref.quiet_start = quiet_start
    if quiet_end is not None:
        pref.quiet_end = quiet_end
    if time_zone is not None and zone(time_zone) is not None:
        pref.time_zone = time_zone
    pref.updated_at = datetime.utcnow()
    try:
        db.commit()
    except IntegrityError:
        # The page-load sync made the row at the same moment; apply the change to that one.
        db.rollback()
        if not _retry:
            raise
        return save_settings(db, user_id, topics, quiet_hours, quiet_start, quiet_end, time_zone, _retry=False)
    return pref


def members_wanting(db: Session, kind: str) -> list[int]:
    """Active members with at least one device that gets this kind of notification pushed."""
    rows = (db.query(models.PushSubscription.user_id, models.PushPreference)
            .join(models.User, models.User.id == models.PushSubscription.user_id)
            .outerjoin(models.PushPreference, models.PushPreference.user_id == models.PushSubscription.user_id)
            .filter(models.User.is_active == True)  # noqa: E712
            .distinct().all())
    return sorted({user_id for user_id, pref in rows if wants(pref, kind)})


# ---------------------------------------------------------------- sending

def record_sent(kind: str, count: int) -> bool:
    """Count pushes that reached a push service in the daily traffic counters (kind "push"). Never raises.

    Anonymous totals per notification type, so Site stats can show whether these
    go out at all and which kinds members get.
    """
    if count <= 0:
        return False
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled:
            return False
        day = datetime.utcnow().date()
        key = f"sent_{kind}" if kind and re.match(r"^[a-z_]{1,40}$", kind) else "sent_other"
        with RECORDER._lock:
            RECORDER._pending[(day, "push", key)] += count
            RECORDER._events += count
        return True
    except Exception:
        return False


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


def _send_to(db: Session, http: httpx.Client, key, rows: list[models.PushSubscription], payload: bytes,
             stats: dict) -> None:
    for row in rows:
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


def _devices(db: Session, user_ids) -> dict[int, list[models.PushSubscription]]:
    rows = (db.query(models.PushSubscription)
            .join(models.User, models.User.id == models.PushSubscription.user_id)
            .filter(models.PushSubscription.user_id.in_(user_ids), models.User.is_active == True)
            .all())
    devices: dict[int, list[models.PushSubscription]] = {}
    for row in rows:
        devices.setdefault(row.user_id, []).append(row)
    return devices


def deliver(db: Session, messages: list[tuple[int, str, str, Optional[str]]],
            http: Optional[httpx.Client] = None, now: Optional[datetime] = None) -> dict:
    """Push each (user_id, type, message, link) to that member's devices.

    Types the member switched off are skipped, and during their quiet hours the
    message is held for the catch-up (see send_held). Gone subscriptions
    (404/410) are removed; one that keeps failing is dropped after a few tries.
    Returns counts for logging and tests.
    """
    stats = {"sent": 0, "removed": 0, "failed": 0, "muted": 0, "held": 0}
    user_ids = {user_id for user_id, *_ in messages}
    if not user_ids:
        return stats
    devices = _devices(db, user_ids)
    if not devices:
        return stats
    prefs = {pref.user_id: pref for pref in
             db.query(models.PushPreference).filter(models.PushPreference.user_id.in_(devices)).all()}
    now = now or datetime.utcnow()
    key = signing_key(db)
    owns_client = http is None
    http = http or httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=False)
    try:
        for user_id, kind, message, link in messages:
            if user_id not in devices:
                continue
            pref = prefs.get(user_id)
            if not wants(pref, kind):
                stats["muted"] += 1
                continue
            if kind != "push_enabled" and in_quiet_hours(pref, now):
                if pref.held_since is None:
                    pref.held_since = quiet_started_at(pref, now)
                stats["held"] += 1
                continue
            sent_before = stats["sent"]
            _send_to(db, http, key, devices[user_id], payload_for(kind, message, link), stats)
            record_sent(kind, stats["sent"] - sent_before)
        db.commit()
    finally:
        if owns_client:
            http.close()
    return stats


HELD_SHOWN = 2


def held_payload(notifications: list[models.Notification]) -> bytes:
    """One catch-up message for what came in during quiet hours."""
    if len(notifications) == 1:
        only = notifications[0]
        return payload_for(only.type or "", only.message or "", only.link)
    lines = [(item.message or "").strip() for item in notifications[:HELD_SHOWN]]
    rest = len(notifications) - HELD_SHOWN
    body = " · ".join(line for line in lines if line)
    if rest > 0:
        body += f" (and {rest} more in the bell)"
    return payload_for("held", body, "/")


def send_held(db: Session, http: Optional[httpx.Client] = None, now: Optional[datetime] = None) -> dict:
    """Once a member's quiet hours end, send one catch-up for what was held (still unread, still wanted)."""
    stats = {"sent": 0, "removed": 0, "failed": 0, "members": 0}
    now = now or datetime.utcnow()
    waiting = [pref for pref in db.query(models.PushPreference).filter(models.PushPreference.held_since.isnot(None))
               if not in_quiet_hours(pref, now)]
    if not waiting:
        return stats
    devices = _devices(db, [pref.user_id for pref in waiting])
    key = signing_key(db) if devices else None
    owns_client = http is None
    http = http or httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=False)
    try:
        for pref in waiting:
            since = pref.held_since
            # Claim the catch-up so a second worker running this at the same moment skips it.
            claimed = (db.query(models.PushPreference)
                       .filter(models.PushPreference.user_id == pref.user_id,
                               models.PushPreference.held_since == since)
                       .update({"held_since": None}, synchronize_session=False))
            db.commit()
            if not claimed or pref.user_id not in devices:
                continue
            unread = (db.query(models.Notification)
                      .filter(models.Notification.user_id == pref.user_id, models.Notification.created_at >= since,
                              models.Notification.read_at.is_(None))
                      .order_by(models.Notification.created_at.desc(), models.Notification.id.desc())
                      .limit(50).all())
            unread = [item for item in unread if wants(pref, item.type or "") and item.type != "push_enabled"]
            if not unread:
                continue
            sent_before = stats["sent"]
            _send_to(db, http, key, devices[pref.user_id], held_payload(unread), stats)
            record_sent("held", stats["sent"] - sent_before)
            stats["members"] += 1
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


CHECK_EVERY_SECONDS = 15 * 60
FIRST_CHECK_DELAY_SECONDS = 240


def _hourly_jobs(session_factory) -> dict:
    """Catch-ups after quiet hours, club finish-by nudges, On this day (which reach the bell too) and away reminders."""
    from . import clubs, memories, push_nudges
    db = session_factory()
    try:
        nudged = clubs.send_due_reminders(db)
        held = send_held(db)
        try:
            remembered = memories.send_due_pushes(db)
        except Exception:
            db.rollback()
            logger.exception("On this day pushes failed")
            remembered = 0
        try:
            away = push_nudges.send_nudges(db)["sent"]
        except Exception:
            db.rollback()
            logger.exception("Away reminders failed")
            away = 0
        return {"club_reminders": nudged, "caught_up": held["members"], "memories": remembered, "away": away}
    finally:
        db.close()


async def push_loop(app) -> None:
    """Background task started with the app; never raises."""
    import asyncio
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            stats = await asyncio.to_thread(_hourly_jobs, SessionLocal)
            if any(stats.values()):
                logger.info("Push catch-up and club reminders: %s", stats)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Push catch-up check failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


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
