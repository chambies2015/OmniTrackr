"""Issued-token binding and privileged-name reservation regressions."""
import bcrypt
import pytest
from app import auth, email as email_utils, models


def member(db, username="account_a", email="old@example.com", verified=False):
    token = email_utils.generate_verification_token(email)
    user = models.User(username=username, email=email, hashed_password=auth.get_password_hash("tea on the porch"),
                       is_active=True, is_verified=verified, verification_token=token)
    db.add(user)
    db.commit()
    return user, token


def test_nonce_makes_same_second_reset_and_verification_links_distinct():
    for generate, verify in ((email_utils.generate_reset_token, email_utils.verify_reset_token),
                             (email_utils.generate_verification_token, email_utils.verify_token)):
        first, second = generate("a@example.com"), generate("a@example.com")
        assert first != second
        assert verify(first) == verify(second) == "a@example.com"


def test_full_reset_verifier_distinguishes_a_changed_suffix_after_byte_72():
    first = "a" * 90 + "first"
    second = "a" * 90 + "second"
    assert auth.verify_token_hash(second, auth.hash_token(second))
    assert not auth.verify_token_hash(first, auth.hash_token(second))
    short = "legacy-short-token"
    legacy = bcrypt.hashpw(short.encode(), bcrypt.gensalt()).decode()
    assert auth.verify_token_hash(short, legacy)
    long = bcrypt.hashpw(first.encode()[:72], bcrypt.gensalt()).decode()
    assert not auth.verify_token_hash(first, long)
    assert not auth.verify_token_hash(second, long)


def test_reset_request_replaces_old_signed_long_email_token(client, db_session):
    address = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@example.com"
    user, _ = member(db_session, email=address, verified=True)
    first = email_utils.generate_reset_token(address)
    user.reset_token = auth.hash_token(first)
    from datetime import datetime, timedelta
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db_session.commit()
    assert client.post("/auth/request-password-reset", params={"email": address}).status_code == 200
    response = client.post("/auth/reset-password", json={"token": first, "new_password": "a new secure phrase"})
    assert response.status_code == 400


def test_replaced_verification_link_cannot_verify_account(client, db_session):
    user, first = member(db_session)
    user.verification_token = email_utils.generate_verification_token(user.email)
    db_session.commit()
    assert client.get("/auth/verify-email", params={"token": first}).status_code == 400
    db_session.refresh(user)
    assert not user.is_verified
    assert client.get("/auth/verify-email", params={"token": user.verification_token}).status_code == 200


def test_old_link_cannot_verify_later_account_using_freed_email(client, db_session):
    first_user, old_link = member(db_session)
    assert client.get("/auth/verify-email", params={"token": old_link}).status_code == 200
    first_user.email = "changed@example.com"
    db_session.commit()
    later, current = member(db_session, username="later_account")
    assert client.get("/auth/verify-email", params={"token": old_link}).status_code == 400
    db_session.refresh(later)
    assert not later.is_verified
    assert client.get("/auth/verify-email", params={"token": current}).status_code == 200


def test_legacy_issued_string_verification_link_still_works(client, db_session):
    user, _ = member(db_session)
    legacy = email_utils.serializer.dumps(user.email, salt="email-verification")
    user.verification_token = legacy
    db_session.commit()
    assert client.get("/auth/verify-email", params={"token": legacy}).status_code == 200


@pytest.mark.parametrize("setting", ["ADMIN_USERNAMES", "COLLECTION_MODERATOR_USERNAMES", "admin_usernames"])
def test_configured_privileged_names_cannot_be_registered(client, monkeypatch, setting):
    monkeypatch.setenv(setting, "ReservedBoss")
    for name in ("ReservedBoss", "reservedboss", "RESERVEDBOSS"):
        result = client.post("/auth/register", json={"username": name, "email": "claim@example.com", "password": "tea on the porch"})
        assert result.status_code == 400
        assert "reserved" in result.json()["detail"].lower()


def test_historical_case_collision_cannot_claim_configured_admin_name(client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "ReservedBoss")
    user, _ = member(db_session, username="RESERVEDBOSS", verified=True)
    headers = {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}
    result = client.put("/account/username", json={"new_username": "ReservedBoss", "password": "tea on the porch"}, headers=headers)
    assert result.status_code == 400
    assert client.get("/api/site-stats/access", headers=headers).json() == {"admin": False}


def test_existing_admin_retains_access_and_may_rename_away(client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "ReservedBoss")
    user, _ = member(db_session, username="ReservedBoss", verified=True)
    headers = {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}
    assert client.get("/api/site-stats/access", headers=headers).json() == {"admin": True}
    assert client.put("/account/username", json={"new_username": "ReservedBoss", "password": "tea on the porch"}, headers=headers).status_code == 200
    assert client.put("/account/username", json={"new_username": "FormerOwner", "password": "tea on the porch"}, headers=headers).status_code == 200
    assert client.get("/api/site-stats/access", headers=headers).json() == {"admin": False}
