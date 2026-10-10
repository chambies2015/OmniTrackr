"""Phone and desktop notifications (Web Push)."""
import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app import models, web_push
from app.web_push import b64url_decode, b64url_encode
from app import auth as app_auth


FCM = "https://fcm.googleapis.com/fcm/send/abc123:APA91bExampleEndpointToken"


def create_user_and_login(client, username, email):
    db = client.app_state_db
    db.add(models.User(username=username, email=email, is_verified=True,
                       hashed_password=app_auth.get_password_hash("password123")))
    db.commit()
    response = client.post("/auth/login", data={"username": username, "password": "password123"})
    assert response.status_code == 200
    client.cookies.clear()  # Each test call names its member through the bearer token.
    return response.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(client, db_session):
    client.app_state_db = db_session
    return client


def browser_keys():
    """A fake browser subscription: its private key (to decrypt) and the keys it would send."""
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(serialization.Encoding.X962,
                                               serialization.PublicFormat.UncompressedPoint)
    auth = b"0123456789abcdef"
    return private, b64url_encode(public), b64url_encode(auth)


def decrypt(body: bytes, ua_private, auth: bytes) -> bytes:
    """What a browser does with a push message (RFC 8291 receiver side)."""
    salt, rs, idlen = body[:16], int.from_bytes(body[16:20], "big"), body[20]
    as_public = body[21:21 + idlen]
    ciphertext = body[21 + idlen:]
    assert rs == 4096
    ua_public = ua_private.public_key().public_bytes(serialization.Encoding.X962,
                                                     serialization.PublicFormat.UncompressedPoint)
    sender = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public)
    shared = ua_private.exchange(ec.ECDH(), sender)

    def hkdf(salt_, ikm, info, length):
        return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt_, info=info).derive(ikm)

    ikm = hkdf(auth, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    plain = AESGCM(cek).decrypt(nonce, ciphertext, None)
    assert plain.endswith(b"\x02")
    return plain[:-1]


@pytest.fixture(autouse=True)
def fresh_key(monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    web_push._reset_key_cache()
    yield
    web_push._reset_key_cache()


@pytest.fixture
def pushed(monkeypatch):
    """Capture committed batches instead of sending them from a background thread."""
    batches = []
    monkeypatch.setattr(web_push, "dispatch_enabled", lambda: True)
    monkeypatch.setattr(web_push, "submit", lambda bind, messages: batches.append(list(messages)))
    return batches


def test_encryption_matches_rfc_8291_example():
    # RFC 8291, Appendix A.
    ua_public = b64url_decode("BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4")
    as_private = ec.derive_private_key(
        int.from_bytes(b64url_decode("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"), ec.SECP256R1())
    body = web_push.encrypt(
        b"When I grow up, I want to be a watermelon", ua_public, b64url_decode("BTBZMqHH6r4Tts7J_aSIgg"),
        sender_key=as_private, salt=b64url_decode("DGv6ra1nlYgDCS1FRnbzlw"))
    assert b64url_encode(body) == (
        "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8w"
        "EqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN")


def test_encrypted_payload_round_trips():
    private, p256dh, auth = browser_keys()
    body = web_push.encrypt(b'{"title":"Out today"}', b64url_decode(p256dh), b64url_decode(auth))
    assert decrypt(body, private, b64url_decode(auth)) == b'{"title":"Out today"}'


@pytest.mark.parametrize("endpoint,ok", [
    (FCM, True),
    ("https://updates.push.services.mozilla.com/wpush/v2/gAAAAABexample", True),
    ("https://web.push.apple.com/QGuQyavXutnMH9zYVMPCvH6nXrNfx2Hz", True),
    ("https://wns2-by3p.notify.windows.com/w/?token=BQYAAAexample", True),
    ("http://fcm.googleapis.com/fcm/send/abc123", False),
    ("https://fcm.googleapis.com.evil.example/fcm/send/abc", False),
    ("https://evilfcm.googleapis.com.example/x/abc123456", False),
    ("https://user:pw@fcm.googleapis.com/fcm/send/abc123", False),
    ("https://fcm.googleapis.com:8443/fcm/send/abc123", False),
    ("https://169.254.169.254/latest/meta-data/iam", False),
    ("https://localhost/fcm/send/abc12345678", False),
])
def test_only_browser_push_services_are_accepted(endpoint, ok):
    assert web_push.valid_endpoint(endpoint) is ok


def test_key_is_created_once_and_reused(db_session):
    first = web_push.public_key(db_session)
    web_push._reset_key_cache()
    assert web_push.public_key(db_session) == first
    assert db_session.query(models.WebPushKey).count() == 1
    assert len(b64url_decode(first)) == 65


def test_environment_key_wins(db_session, monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    raw = key.private_numbers().private_value.to_bytes(32, "big")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", b64url_encode(raw))
    expected = key.public_key().public_bytes(serialization.Encoding.X962,
                                             serialization.PublicFormat.UncompressedPoint)
    assert web_push.public_key(db_session) == b64url_encode(expected)
    assert db_session.query(models.WebPushKey).count() == 0


def test_vapid_header_is_a_valid_es256_token(db_session):
    key = web_push.signing_key(db_session)
    header = web_push.vapid_headers(FCM, key, now=1_800_000_000)["Authorization"]
    token = header.split("t=")[1].split(",")[0]
    claims = jwt.decode(token, key.public_key(), algorithms=["ES256"], audience="https://fcm.googleapis.com",
                        options={"verify_exp": False})
    assert claims["exp"] == 1_800_000_000 + 12 * 3600
    assert claims["sub"].startswith("mailto:")
    assert header.endswith("k=" + web_push.public_key(db_session))


def test_subscribe_and_unsubscribe(client, db_session, pushed):
    token = create_user_and_login(client, "pushfan", "pushfan@example.com")
    _, p256dh, auth = browser_keys()
    key = client.get("/notifications/push/key", headers=auth_headers(token)).json()
    assert key["devices"] == 0 and len(b64url_decode(key["public_key"])) == 65

    response = client.post("/notifications/push/subscription", headers=auth_headers(token),
                           json={"endpoint": FCM, "keys": {"p256dh": p256dh, "auth": auth}})
    assert response.status_code == 200
    assert client.get("/notifications/push/key", headers=auth_headers(token)).json()["devices"] == 1
    # The confirmation goes to the bell and is pushed.
    assert pushed and pushed[-1][0][1] == "push_enabled"
    # The page re-sends the subscription on later visits; that adds nothing new.
    again = client.post("/notifications/push/subscription", headers=auth_headers(token),
                        json={"endpoint": FCM, "keys": {"p256dh": p256dh, "auth": auth}})
    assert again.json() == {"enabled": True, "new": False}
    assert db_session.query(models.Notification).filter_by(type="push_enabled").count() == 1

    response = client.post("/notifications/push/subscription/remove", headers=auth_headers(token),
                           json={"endpoint": FCM})
    assert response.json() == {"enabled": False, "removed": True}
    assert db_session.query(models.PushSubscription).count() == 0


def test_subscribe_rejects_other_hosts_and_bad_keys(client, pushed):
    token = create_user_and_login(client, "pushfan2", "pushfan2@example.com")
    _, p256dh, auth = browser_keys()
    bad_host = client.post("/notifications/push/subscription", headers=auth_headers(token),
                           json={"endpoint": "https://internal.example/hook/abcdef", "keys": {"p256dh": p256dh, "auth": auth}})
    assert bad_host.status_code == 422
    bad_key = client.post("/notifications/push/subscription", headers=auth_headers(token),
                          json={"endpoint": FCM, "keys": {"p256dh": "AAAA", "auth": auth}})
    assert bad_key.status_code == 422
    assert client.get("/notifications/push/key").status_code == 401


def test_same_device_moves_to_whoever_signs_in(client, db_session, pushed):
    _, p256dh, auth = browser_keys()
    first = create_user_and_login(client, "firstuser", "first@example.com")
    client.post("/notifications/push/subscription", headers=auth_headers(first),
                json={"endpoint": FCM, "keys": {"p256dh": p256dh, "auth": auth}})
    second = create_user_and_login(client, "seconduser", "second@example.com")
    client.post("/notifications/push/subscription", headers=auth_headers(second),
                json={"endpoint": FCM, "keys": {"p256dh": p256dh, "auth": auth}})
    rows = db_session.query(models.PushSubscription).all()
    assert len(rows) == 1
    assert rows[0].user_id == db_session.query(models.User).filter_by(username="seconduser").one().id
    # The first member can't remove a device that is no longer theirs.
    removed = client.post("/notifications/push/subscription/remove", headers=auth_headers(first), json={"endpoint": FCM})
    assert removed.json()["removed"] is False


def test_any_new_notification_is_queued_after_commit(db_session, pushed):
    user = models.User(username="bell", email="bell@example.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    pushed.clear()
    db_session.add(models.Notification(user_id=user.id, type="release_day", message="Out today: Dune", link="/release-radar"))
    db_session.flush()
    assert pushed == []  # Nothing goes out before the commit.
    db_session.commit()
    assert pushed == [[(user.id, "release_day", "Out today: Dune", "/release-radar")]]

    db_session.add(models.Notification(user_id=user.id, type="goal_reached", message="rolled back"))
    db_session.flush()
    db_session.rollback()
    db_session.commit()
    assert len(pushed) == 1


def test_nothing_is_queued_when_disabled(db_session, monkeypatch):
    batches = []
    monkeypatch.setattr(web_push, "submit", lambda bind, messages: batches.append(messages))
    user = models.User(username="quiet", email="quiet@example.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    db_session.add(models.Notification(user_id=user.id, type="release_day", message="Out today"))
    db_session.commit()
    assert batches == []  # TESTING disables background sending.


def _subscribe(db_session, user, endpoint=FCM):
    private, p256dh, auth = browser_keys()
    web_push.save_subscription(db_session, user.id, endpoint, p256dh, auth)
    return private, b64url_decode(auth)


def test_deliver_encrypts_for_each_device_and_prunes_gone_ones(db_session):
    user = models.User(username="phones", email="phones@example.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    private, auth = _subscribe(db_session, user)
    _subscribe(db_session, user, "https://updates.push.services.mozilla.com/wpush/v2/gone-device-token")
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        if "mozilla" in request.url.host:
            return httpx.Response(410)
        return httpx.Response(201)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        stats = web_push.deliver(db_session, [(user.id, "release_day", "Out today: Dune (Movie), from your library.",
                                               "/release-radar/movies#item-dune")], http=http)
    assert stats == {"sent": 1, "removed": 1, "failed": 0}
    fcm = next(request for request in seen if "fcm" in request.url.host)
    assert fcm.headers["Content-Encoding"] == "aes128gcm"
    assert fcm.headers["TTL"] == str(web_push.TTL_SECONDS)
    assert fcm.headers["Authorization"].startswith("vapid t=")
    message = json.loads(decrypt(fcm.content, private, auth))
    assert message == {"title": "Out today", "body": "Out today: Dune (Movie), from your library.",
                       "url": "/release-radar/movies#item-dune", "tag": "release_day"}
    remaining = db_session.query(models.PushSubscription).all()
    assert len(remaining) == 1 and remaining[0].last_success_at is not None


def test_deliver_skips_deactivated_members_and_repeated_failures(db_session):
    active = models.User(username="active", email="active@example.com", hashed_password="x")
    gone = models.User(username="gone", email="gone@example.com", hashed_password="x", is_active=False)
    db_session.add_all([active, gone])
    db_session.commit()
    _subscribe(db_session, active)
    _subscribe(db_session, gone, FCM + "-other")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        for _ in range(web_push.MAX_FAILURES):
            web_push.deliver(db_session, [(active.id, "x", "hi", None), (gone.id, "x", "hi", None)], http=http)
    assert len(calls) == web_push.MAX_FAILURES  # Only the active member's device was tried.
    assert db_session.query(models.PushSubscription).filter_by(user_id=active.id).count() == 0


def test_links_stay_on_site_and_bodies_are_short():
    data = json.loads(web_push.payload_for("take_received", "x" * 500, "https://evil.example/"))
    assert data["url"] == "/" and len(data["body"]) == web_push.MAX_BODY_CHARS
    assert json.loads(web_push.payload_for("unknown", "hi", "//evil.example"))["url"] == "/"
    assert json.loads(web_push.payload_for("unknown", "hi", "/titles/movie/dune"))["title"] == "OmniTrackr"


def test_each_member_keeps_at_most_ten_devices(db_session):
    user = models.User(username="many", email="many@example.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    for index in range(12):
        _subscribe(db_session, user, f"{FCM}-{index}")
    assert db_session.query(models.PushSubscription).filter_by(user_id=user.id).count() == web_push.MAX_DEVICES_PER_MEMBER
