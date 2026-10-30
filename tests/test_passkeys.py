"""Passkeys: adding one in Settings, logging in with it, and the WebAuthn checks behind both."""
import hashlib
import json
import secrets
import struct
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa

from app import auth, models, passkeys

from .test_two_factor import _code, _turn_on

RP = "testserver"
ORIGIN = "http://testserver"
PASSWORD = "testpassword123"


# ---------------------------------------------------------------- a software authenticator

def cbor(value) -> bytes:
    """Just enough CBOR to build what a real authenticator sends."""
    def head(major, argument):
        if argument < 24:
            return bytes([(major << 5) | argument])
        for info, fmt in ((24, ">B"), (25, ">H"), (26, ">I"), (27, ">Q")):
            if argument < (1 << (8 * struct.calcsize(fmt))):
                return bytes([(major << 5) | info]) + struct.pack(fmt, argument)
        raise ValueError(argument)

    if value is None:
        return b"\xf6"
    if isinstance(value, bool):
        return bytes([0xF5 if value else 0xF4])
    if isinstance(value, int):
        return head(0, value) if value >= 0 else head(1, -1 - value)
    if isinstance(value, bytes):
        return head(2, len(value)) + value
    if isinstance(value, str):
        data = value.encode("utf-8")
        return head(3, len(data)) + data
    if isinstance(value, list):
        return head(4, len(value)) + b"".join(cbor(item) for item in value)
    if isinstance(value, dict):
        return head(5, len(value)) + b"".join(cbor(k) + cbor(v) for k, v in value.items())
    raise TypeError(type(value))


class SoftAuthenticator:
    """Signs like a phone or security key would, with knobs for every check we make."""

    def __init__(self, algorithm="es256", rp=RP, origin=ORIGIN, counter=0, transports=("internal", "hybrid")):
        self.algorithm = algorithm
        self.rp, self.origin, self.counter, self.transports = rp, origin, counter, list(transports)
        self.credential_id = secrets.token_bytes(32)
        if algorithm == "es256":
            self.key = ec.generate_private_key(ec.SECP256R1())
        elif algorithm == "rs256":
            self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        else:
            self.key = ed25519.Ed25519PrivateKey.generate()

    def cose_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers() if self.algorithm != "eddsa" else None
        if self.algorithm == "es256":
            return cbor({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")})
        if self.algorithm == "rs256":
            return cbor({1: 3, 3: -257, -1: numbers.n.to_bytes(256, "big"), -2: numbers.e.to_bytes(3, "big")})
        from cryptography.hazmat.primitives import serialization
        raw = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return cbor({1: 1, 3: -8, -1: 6, -2: raw})

    def sign(self, data: bytes) -> bytes:
        if self.algorithm == "es256":
            return self.key.sign(data, ec.ECDSA(hashes.SHA256()))
        if self.algorithm == "rs256":
            return self.key.sign(data, padding.PKCS1v15(), hashes.SHA256())
        return self.key.sign(data)

    def client_data(self, kind, challenge_b64, origin=None, **extra) -> bytes:
        data = {"type": kind, "challenge": challenge_b64, "origin": origin or self.origin, "crossOrigin": False, **extra}
        return json.dumps(data).encode("utf-8")

    def authenticator_data(self, *, credential: bool, uv=True, up=True, backed_up=True, rp=None, counter=None) -> bytes:
        flags = (0x01 if up else 0) | (0x04 if uv else 0) | (0x08 | 0x10 if backed_up else 0)
        if credential:
            flags |= 0x40
        out = hashlib.sha256((rp or self.rp).encode()).digest() + bytes([flags])
        out += struct.pack(">I", self.counter if counter is None else counter)
        if credential:
            out += bytes(16) + struct.pack(">H", len(self.credential_id)) + self.credential_id + self.cose_key()
        return out

    def register(self, options, *, client_type="webauthn.create", challenge=None, origin=None, **auth_kwargs) -> dict:
        client = self.client_data(client_type, challenge or options["challenge"], origin)
        attestation = cbor({"fmt": "none", "attStmt": {}, "authData": self.authenticator_data(credential=True, **auth_kwargs)})
        return {
            "id": passkeys.b64url(self.credential_id), "rawId": passkeys.b64url(self.credential_id), "type": "public-key",
            "response": {"clientDataJSON": passkeys.b64url(client), "attestationObject": passkeys.b64url(attestation),
                         "transports": self.transports},
        }

    def assertion(self, options, *, challenge=None, origin=None, counter=None, signature=None, **auth_kwargs) -> dict:
        if counter is not None:
            self.counter = counter
        client = self.client_data("webauthn.get", challenge or options["challenge"], origin)
        auth_data = self.authenticator_data(credential=False, **auth_kwargs)
        signed = signature if signature is not None else self.sign(auth_data + hashlib.sha256(client).digest())
        return {
            "id": passkeys.b64url(self.credential_id), "rawId": passkeys.b64url(self.credential_id), "type": "public-key",
            "response": {"clientDataJSON": passkeys.b64url(client), "authenticatorData": passkeys.b64url(auth_data),
                         "signature": passkeys.b64url(signed), "userHandle": None},
        }


def _add(client, authenticator=None, name="", password=PASSWORD, **register_kwargs):
    authenticator = authenticator or SoftAuthenticator()
    options = client.post("/account/passkeys/options", json={"password": password})
    assert options.status_code == 200, options.text
    response = client.post("/account/passkeys/register",
                           json={"name": name, "credential": authenticator.register(options.json(), **register_kwargs)})
    return authenticator, response


def _sign_out(client):
    client.headers = {}
    client.cookies.clear()


def _passkey_login(client, authenticator, **assertion_kwargs):
    options = client.post("/auth/passkey/options")
    assert options.status_code == 200, options.text
    return client.post("/auth/passkey/login", json=authenticator.assertion(options.json(), **assertion_kwargs))


# ---------------------------------------------------------------- the pieces

def test_cbor_reader_handles_what_authenticators_send():
    value = {"fmt": "none", "attStmt": {}, "authData": b"\x01\x02", 1: -7, -2: [True, False, None, 300, 70000]}
    decoded, consumed = passkeys.cbor_decode(cbor(value) + b"trailing")
    assert decoded == value
    assert consumed == len(cbor(value))


@pytest.mark.parametrize("broken", [b"", b"\x5f\xff", b"\x82\x01", b"\x62\xff\xfe", b"\x18"])
def test_cbor_reader_refuses_truncated_or_indefinite_input(broken):
    with pytest.raises(passkeys.PasskeyError):
        passkeys.cbor_decode(broken)


def test_relying_party_id_is_the_bare_domain(monkeypatch):
    monkeypatch.delenv("PASSKEY_RP_ID", raising=False)
    monkeypatch.setattr(passkeys.auth, "ENVIRONMENT", "production")
    import app.email
    monkeypatch.setattr(app.email, "APP_URL", "https://www.omnitrackr.xyz")
    www = SimpleNamespace(headers={"host": "www.omnitrackr.xyz"}, url=SimpleNamespace(scheme="http"))
    bare = SimpleNamespace(headers={"host": "omnitrackr.xyz"}, url=SimpleNamespace(scheme="http"))
    assert passkeys.rp_id(www) == "omnitrackr.xyz"
    assert passkeys.rp_id(bare) == "omnitrackr.xyz"
    # An unknown host (a preview URL, say) falls back to the site's own domain rather than trusting the header.
    other = SimpleNamespace(headers={"host": "evil.example"}, url=SimpleNamespace(scheme="https"))
    assert passkeys.rp_id(other) == "omnitrackr.xyz"
    origins = passkeys.expected_origins(www)
    assert {"https://omnitrackr.xyz", "https://www.omnitrackr.xyz"} <= origins
    assert "https://evil.example" not in passkeys.expected_origins(other)
    monkeypatch.setenv("PASSKEY_RP_ID", "example.org")
    monkeypatch.setenv("PASSKEY_ORIGINS", "https://staging.example.org/")
    assert passkeys.rp_id(www) == "example.org"
    assert "https://staging.example.org" in passkeys.expected_origins(None)


def test_challenge_cookie_is_bound_to_its_purpose_and_member():
    challenge = passkeys.new_challenge()
    value = passkeys.challenge_cookie_value("create", challenge, 7)
    assert passkeys.read_challenge(value, "create", 7) == challenge
    assert passkeys.read_challenge(value, "get") is None
    assert passkeys.read_challenge(value, "create", 8) is None
    assert passkeys.read_challenge(value + "x", "create", 7) is None


# ---------------------------------------------------------------- settings

def test_members_start_with_no_passkeys(authenticated_client):
    assert authenticated_client.get("/account/passkeys").json() == {"passkeys": [], "has_password": True, "limit": 10}


def test_options_need_the_password(authenticated_client):
    response = authenticated_client.post("/account/passkeys/options", json={"password": "wrong"})
    assert response.status_code == 400
    assert passkeys.CHALLENGE_COOKIE not in response.cookies


def test_options_describe_this_site_and_ask_for_a_synced_verified_key(authenticated_client):
    response = authenticated_client.post("/account/passkeys/options", json={"password": PASSWORD})
    options = response.json()
    assert options["rp"] == {"id": RP, "name": "OmniTrackr"}
    assert options["user"]["name"] == "testuser" and "test@example.com" not in json.dumps(options["user"])
    assert [p["alg"] for p in options["pubKeyCredParams"]] == [-7, -8, -257]
    assert options["authenticatorSelection"] == {"residentKey": "required", "requireResidentKey": True, "userVerification": "required"}
    assert options["attestation"] == "none"
    assert passkeys.CHALLENGE_COOKIE in response.cookies


@pytest.mark.parametrize("algorithm", ["es256", "eddsa", "rs256"])
def test_adding_a_passkey_keeps_the_public_half(authenticated_client, db_session, algorithm):
    authenticator, response = _add(authenticated_client, SoftAuthenticator(algorithm))
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["passkeys"]) == 1 and body["added"]["name"] == "Synced passkey"
    row = db_session.query(models.UserPasskey).one()
    assert row.credential_id == passkeys.b64url(authenticator.credential_id)
    assert passkeys.unb64url(row.public_key) == authenticator.cose_key()
    assert row.backed_up is True and json.loads(row.transports) == ["internal", "hybrid"]
    # The one-time challenge is gone once it is used.
    again = authenticated_client.post("/account/passkeys/register",
                                      json={"credential": authenticator.register({"challenge": passkeys.b64url(b"x" * 32)})})
    assert again.status_code == 400 and "expired" in again.json()["detail"]


def test_names_are_cleaned_or_suggested(authenticated_client):
    _, response = _add(authenticated_client, name="  Work   laptop ")
    assert response.json()["added"]["name"] == "Work laptop"
    _, response = _add(authenticated_client, SoftAuthenticator(transports=("usb", "nfc")))
    assert response.json()["added"]["name"] == "Security key"
    _, response = _add(authenticated_client, SoftAuthenticator(transports=("usb",)))
    assert response.json()["added"]["name"] == "Security key 2"
    _, response = _add(authenticated_client, SoftAuthenticator(transports=("hybrid",)))
    assert response.json()["added"]["name"] == "Phone passkey"


@pytest.mark.parametrize("problem, kwargs", [
    ("different site", {"rp": "evil.example"}),
    ("own address", {"origin": "https://evil.example"}),
    ("fingerprint", {"uv": False}),
    ("expired", {"challenge": passkeys.b64url(b"z" * 32)}),
    ("malformed", {"client_type": "webauthn.get"}),
])
def test_registration_refuses_the_wrong_site_origin_verification_or_challenge(authenticated_client, db_session, problem, kwargs):
    _, response = _add(authenticated_client, **kwargs)
    assert response.status_code == 400, response.text
    assert problem in response.json()["detail"]
    assert db_session.query(models.UserPasskey).count() == 0


def test_the_same_credential_cannot_be_registered_twice(authenticated_client):
    authenticator, first = _add(authenticated_client)
    assert first.status_code == 200
    _, second = _add(authenticated_client, authenticator)
    assert second.status_code == 400 and "already registered" in second.json()["detail"]


def test_ten_passkeys_is_the_limit(authenticated_client):
    for _ in range(10):
        assert _add(authenticated_client)[1].status_code == 200
    response = authenticated_client.post("/account/passkeys/options", json={"password": PASSWORD})
    assert response.status_code == 400 and "up to 10" in response.json()["detail"]


def test_rename_and_remove(authenticated_client, db_session):
    _, response = _add(authenticated_client)
    passkey_id = response.json()["added"]["id"]
    renamed = authenticated_client.post(f"/account/passkeys/{passkey_id}/rename", json={"name": " Kitchen iPad "})
    assert renamed.status_code == 200 and renamed.json()["passkeys"][0]["name"] == "Kitchen iPad"
    assert authenticated_client.post(f"/account/passkeys/{passkey_id}/remove", json={"password": "nope"}).status_code == 400
    removed = authenticated_client.post(f"/account/passkeys/{passkey_id}/remove", json={"password": PASSWORD})
    assert removed.status_code == 200 and removed.json()["passkeys"] == []
    assert db_session.query(models.UserPasskey).count() == 0
    assert authenticated_client.post(f"/account/passkeys/{passkey_id}/rename", json={"name": "x"}).status_code == 404


def test_another_members_passkey_is_out_of_reach(authenticated_client, db_session):
    other = models.User(email="other@example.com", username="other", hashed_password=auth.get_password_hash("pw"), is_verified=True)
    db_session.add(other)
    db_session.commit()
    row = models.UserPasskey(user_id=other.id, credential_id="abc", public_key="def", name="Theirs")
    db_session.add(row)
    db_session.commit()
    assert authenticated_client.post(f"/account/passkeys/{row.id}/rename", json={"name": "Mine"}).status_code == 404
    assert authenticated_client.post(f"/account/passkeys/{row.id}/remove", json={"password": PASSWORD}).status_code == 404
    assert authenticated_client.get("/account/passkeys").json()["passkeys"] == []


# ---------------------------------------------------------------- logging in

@pytest.mark.parametrize("algorithm", ["es256", "eddsa", "rs256"])
def test_a_passkey_opens_the_session(authenticated_client, db_session, algorithm):
    authenticator, response = _add(authenticated_client, SoftAuthenticator(algorithm, counter=0))
    assert response.status_code == 200
    _sign_out(authenticated_client)
    assert authenticated_client.get("/account/me").status_code == 401
    response = _passkey_login(authenticated_client, authenticator)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"] and body["user"]["username"] == "testuser" and body["signed_in_with"] == "passkey"
    assert auth.AUTH_COOKIE_NAME in response.cookies
    assert authenticated_client.get("/account/me").status_code == 200
    row = db_session.query(models.UserPasskey).one()
    db_session.refresh(row)
    assert row.last_used_at is not None


def test_login_needs_a_fresh_challenge_each_time(authenticated_client):
    authenticator, _ = _add(authenticated_client)
    _sign_out(authenticated_client)
    options = authenticated_client.post("/auth/passkey/options").json()
    assertion = authenticator.assertion(options)
    assert authenticated_client.post("/auth/passkey/login", json=assertion).status_code == 200
    _sign_out(authenticated_client)
    # Same signed response again: the challenge cookie is gone, so it can't be replayed.
    assert authenticated_client.post("/auth/passkey/login", json=assertion).status_code == 401
    # And a challenge the server never issued doesn't count either.
    authenticated_client.cookies.set(passkeys.CHALLENGE_COOKIE, "forged", path=passkeys.LOGIN_COOKIE_PATH)
    assert authenticated_client.post("/auth/passkey/login", json=assertion).status_code == 401


@pytest.mark.parametrize("kwargs", [
    {"signature": b"\x30\x06\x02\x01\x01\x02\x01\x01"},
    {"origin": "https://evil.example"},
    {"rp": "evil.example"},
    {"uv": False},
    {"up": False},
    {"challenge": passkeys.b64url(b"q" * 32)},
])
def test_login_refuses_a_bad_assertion(authenticated_client, kwargs):
    authenticator, _ = _add(authenticated_client)
    _sign_out(authenticated_client)
    response = _passkey_login(authenticated_client, authenticator, **kwargs)
    assert response.status_code == 401, response.text
    assert auth.AUTH_COOKIE_NAME not in response.cookies
    assert authenticated_client.get("/account/me").status_code == 401


def test_login_refuses_an_unknown_or_removed_passkey(authenticated_client):
    authenticator, response = _add(authenticated_client)
    passkey_id = response.json()["added"]["id"]
    authenticated_client.post(f"/account/passkeys/{passkey_id}/remove", json={"password": PASSWORD})
    _sign_out(authenticated_client)
    response = _passkey_login(authenticated_client, authenticator)
    assert response.status_code == 401 and "don't know that passkey" in response.json()["detail"]
    stranger = SoftAuthenticator()
    assert _passkey_login(authenticated_client, stranger).status_code == 401


def test_a_counter_that_goes_backwards_is_refused(authenticated_client, db_session):
    authenticator, _ = _add(authenticated_client, SoftAuthenticator(counter=1, transports=("usb",)))
    _sign_out(authenticated_client)
    assert _passkey_login(authenticated_client, authenticator, counter=5).status_code == 200
    _sign_out(authenticated_client)
    refused = _passkey_login(authenticated_client, authenticator, counter=3)
    assert refused.status_code == 401 and "copied" in refused.json()["detail"]
    assert _passkey_login(authenticated_client, authenticator, counter=6).status_code == 200
    row = db_session.query(models.UserPasskey).one()
    db_session.refresh(row)
    assert row.sign_count == 6


def test_a_passkey_skips_the_two_factor_code(authenticated_client):
    secret, _ = _turn_on(authenticated_client)
    authenticator, response = _add(authenticated_client)
    assert response.status_code == 200
    _sign_out(authenticated_client)
    # The password alone still stops at the code step...
    password_step = authenticated_client.post("/auth/login", data={"username": "testuser", "password": PASSWORD})
    assert password_step.json() == {"two_factor_required": True}
    _sign_out(authenticated_client)
    # ...while a passkey, which already checked a fingerprint or PIN, goes straight in.
    response = _passkey_login(authenticated_client, authenticator)
    assert response.status_code == 200 and response.json()["access_token"]
    assert authenticated_client.get("/account/me").status_code == 200
    assert _code(secret)  # the authenticator setup is untouched


def test_unverified_locked_or_deactivated_accounts_still_cannot_get_in(authenticated_client, db_session):
    authenticator, _ = _add(authenticated_client)
    user = db_session.query(models.User).filter(models.User.username == "testuser").one()
    _sign_out(authenticated_client)

    user.is_verified = False
    db_session.commit()
    assert _passkey_login(authenticated_client, authenticator).status_code == 403
    user.is_verified = True

    from datetime import datetime, timedelta
    user.locked_until = datetime.utcnow() + timedelta(minutes=10)
    db_session.commit()
    assert _passkey_login(authenticated_client, authenticator).status_code == 423
    user.locked_until = None

    user.is_active = False
    db_session.commit()
    assert _passkey_login(authenticated_client, authenticator).status_code == 403
    user.is_active = True
    db_session.commit()
    assert _passkey_login(authenticated_client, authenticator).status_code == 200


def test_google_only_accounts_add_passkeys_without_a_password(authenticated_client, db_session):
    user = db_session.query(models.User).filter(models.User.username == "testuser").one()
    user.password_set = False
    db_session.commit()
    assert authenticated_client.get("/account/passkeys").json()["has_password"] is False
    _, response = _add(authenticated_client, password="")
    assert response.status_code == 200, response.text


def test_the_dashboard_and_homepage_load_the_passkey_script(client):
    home = client.get("/").text
    assert 'id="passkeyLoginButton"' in home and "/static/passkeys.js" in home
    assert 'autocomplete="username webauthn"' in home
    assert client.get("/static/passkeys.js").status_code == 200
