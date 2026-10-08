"""Ko-fi supporter tier: webhook, linking payments to members, settings, and the profile badge."""
import json
from datetime import datetime, timedelta

import pytest

from app import auth, models, supporters

TOKEN = "kofi-test-token"


def member(db, name, verified=True, email=None):
    user = models.User(username=name, email=email or f"{name}@example.com",
                       hashed_password=auth.get_password_hash("password123"),
                       is_verified=verified, is_active=True, created_at=datetime(2025, 3, 4))
    db.add(user)
    db.flush()
    return user


def headers_for(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}


@pytest.fixture(autouse=True)
def kofi_token(monkeypatch):
    monkeypatch.setenv("KOFI_VERIFICATION_TOKEN", TOKEN)


def payment(message_id="msg-1", **fields):
    data = {
        "verification_token": TOKEN, "message_id": message_id, "timestamp": "2026-10-08T12:00:00Z",
        "type": "Donation", "is_public": True, "from_name": "Jo Example", "message": "Love the app",
        "amount": "5.00", "url": "https://ko-fi.com/Home/CoffeeShop?txid=x", "email": "jo@example.com",
        "currency": "USD", "is_subscription_payment": False, "is_first_subscription_payment": False,
        "kofi_transaction_id": message_id, "tier_name": None,
    }
    data.update(fields)
    return data


def post(client, data):
    return client.post("/api/kofi/webhook", data={"data": json.dumps(data)})


# ---------------------------------------------------------------- webhook security

def test_webhook_rejects_a_wrong_token(client, db_session):
    response = post(client, payment(verification_token="nope"))
    assert response.status_code == 403
    assert db_session.query(models.KofiPayment).count() == 0


def test_webhook_is_off_until_a_token_is_configured(client, db_session, monkeypatch):
    monkeypatch.delenv("KOFI_VERIFICATION_TOKEN")
    assert post(client, payment()).status_code == 503
    assert db_session.query(models.KofiPayment).count() == 0


def test_webhook_rejects_garbage(client):
    assert client.post("/api/kofi/webhook", data={"data": "not json"}).status_code == 400
    assert client.post("/api/kofi/webhook", data={}).status_code == 400
    assert post(client, payment(message_id=None, kofi_transaction_id=None)).status_code == 400


# ---------------------------------------------------------------- linking

def test_matching_verified_email_grants_perks(client, db_session):
    user = member(db_session, "jo", email="Jo@Example.com")
    db_session.commit()
    response = post(client, payment())
    assert response.status_code == 200
    assert response.json() == {"status": "recorded", "linked": True}
    supporter = supporters.get_supporter(db_session, user.id)
    assert supporters.is_active(supporter)
    assert supporter.active_until - supporter.since == timedelta(days=supporters.DONATION_DAYS)
    assert supporters.is_ad_free(db_session, user)


def test_retried_delivery_counts_once(client, db_session):
    user = member(db_session, "jo")
    db_session.commit()
    post(client, payment())
    until = supporters.get_supporter(db_session, user.id).active_until
    again = post(client, payment())
    assert again.status_code == 200 and again.json()["status"] == "duplicate"
    db_session.expire_all()
    assert supporters.get_supporter(db_session, user.id).active_until == until
    assert db_session.query(models.KofiPayment).count() == 1


def test_unverified_email_does_not_match(client, db_session):
    user = member(db_session, "jo", verified=False)
    db_session.commit()
    assert post(client, payment()).json()["linked"] is False
    assert supporters.get_supporter(db_session, user.id) is None


def test_supporter_code_in_message_links_a_different_email(client, db_session):
    user = member(db_session, "reader", email="reader@example.com")
    db_session.commit()
    code = supporters.supporter_code(user.id)
    result = post(client, payment(email="other@elsewhere.com", message=f"Thanks! {code}")).json()
    assert result["linked"] is True
    assert supporters.is_active(supporters.get_supporter(db_session, user.id))


def test_forged_code_is_ignored():
    assert supporters.user_id_from_text("OT-5-000000") is None
    assert supporters.user_id_from_text(supporters.supporter_code(5).lower()) == 5
    assert supporters.user_id_from_text("no code here") is None


def test_unmatched_payment_links_when_member_opens_settings(client, db_session):
    post(client, payment(email="later@example.com"))
    user = member(db_session, "later")
    db_session.commit()
    data = client.get("/api/supporter", headers=headers_for(user)).json()
    assert data["active"] is True and data["ad_free"] is True
    assert db_session.query(models.KofiPayment).one().user_id == user.id


def test_payments_store_no_plain_email(client, db_session):
    post(client, payment(email="secret@example.com"))
    row = db_session.query(models.KofiPayment).one()
    assert "secret" not in (row.email_hash or "")
    assert row.email_hash == supporters.email_hash("SECRET@example.com ")


def test_monthly_payments_stack_and_shop_orders_grant_nothing(client, db_session):
    user = member(db_session, "jo")
    db_session.commit()
    post(client, payment("s1", type="Subscription", is_subscription_payment=True, tier_name="Supporter"))
    post(client, payment("s2", type="Subscription", is_subscription_payment=True))
    supporter = supporters.get_supporter(db_session, user.id)
    assert supporter.monthly is True
    assert supporter.active_until - supporter.since == timedelta(days=2 * supporters.MONTHLY_DAYS)
    post(client, payment("shop", type="Shop Order"))
    db_session.expire_all()
    assert supporters.get_supporter(db_session, user.id).active_until == supporter.active_until


def test_lapsed_supporter_keeps_since_but_loses_perks(client, db_session):
    user = member(db_session, "jo")
    db_session.commit()
    post(client, payment())
    supporter = supporters.get_supporter(db_session, user.id)
    supporter.since = datetime(2026, 1, 1)
    supporter.active_until = datetime(2026, 2, 1)
    db_session.commit()
    assert not supporters.is_ad_free(db_session, user)
    post(client, payment("msg-2"))
    db_session.expire_all()
    supporter = supporters.get_supporter(db_session, user.id)
    assert supporter.since == datetime(2026, 1, 1)
    assert supporters.is_active(supporter)


# ---------------------------------------------------------------- settings

def test_status_for_a_non_supporter(client, db_session):
    user = member(db_session, "plain")
    db_session.commit()
    data = client.get("/api/supporter", headers=headers_for(user)).json()
    assert data["active"] is False and data["since"] is None
    assert data["code"] == supporters.supporter_code(user.id)
    assert client.put("/api/supporter", headers=headers_for(user), json={"accent": "teal"}).status_code == 403


def test_supporter_can_pick_accent_and_hide_badge(client, db_session):
    user = member(db_session, "jo")
    db_session.commit()
    post(client, payment())
    response = client.put("/api/supporter", headers=headers_for(user), json={"accent": "teal", "show_badge": False})
    assert response.status_code == 200
    assert response.json()["accent"] == "teal" and response.json()["show_badge"] is False
    assert client.put("/api/supporter", headers=headers_for(user), json={"accent": "neon"}).status_code == 422
    assert client.get("/api/supporter").status_code == 401


# ---------------------------------------------------------------- public profile

def test_profile_shows_badge_and_accent_only_while_active(client, db_session):
    user = member(db_session, "jo")
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    db_session.commit()
    assert "profile-supporter" not in client.get("/u/jo").text

    post(client, payment())
    client.put("/api/supporter", headers=headers_for(user), json={"accent": "rose"})
    page = client.get("/u/jo").text
    assert 'class="profile-supporter"' in page and "profile-hero--accent-rose" in page

    client.put("/api/supporter", headers=headers_for(user), json={"show_badge": False})
    assert "profile-supporter" not in client.get("/u/jo").text


# ---------------------------------------------------------------- site owner

def test_admin_can_list_and_link_unmatched_payments(client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "boss")
    boss = member(db_session, "boss")
    fan = member(db_session, "fan")
    db_session.commit()
    post(client, payment(email="nobody@elsewhere.com"))

    assert client.get("/api/supporters/unmatched", headers=headers_for(fan)).status_code == 403
    listed = client.get("/api/supporters/unmatched", headers=headers_for(boss)).json()["payments"]
    assert [p["message_id"] for p in listed] == ["msg-1"]

    linked = client.post("/api/supporters/link", headers=headers_for(boss), json={"message_id": "msg-1", "username": "fan"})
    assert linked.status_code == 200
    assert supporters.is_active(supporters.get_supporter(db_session, fan.id))
    again = client.post("/api/supporters/link", headers=headers_for(boss), json={"message_id": "msg-1", "username": "fan"})
    assert again.status_code == 409


def test_supporters_page_is_public_and_not_indexed(client):
    response = client.get("/supporters")
    assert response.status_code == 200
    assert "Support OmniTrackr" in response.text and "noindex" in response.text
