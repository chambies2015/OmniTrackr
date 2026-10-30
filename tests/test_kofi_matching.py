"""Ko-fi payments that don't match a member on arrival: looser matching, test pings, the owner's
one-click linking, and the member's "I donated but don't see my badge" claim."""
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text

from app import auth, migrations, models, supporters
from app import email as email_utils

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
    monkeypatch.setenv("ADMIN_USERNAMES", "boss")


@pytest.fixture
def sent(monkeypatch):
    outbox = []

    async def fake_send(email, username, url):
        outbox.append({"email": email, "username": username, "url": url})

    monkeypatch.setattr(email_utils, "send_kofi_claim_email", fake_send)
    return outbox


def payment(message_id="msg-1", **fields):
    data = {
        "verification_token": TOKEN, "message_id": message_id, "timestamp": "2026-10-08T12:00:00Z",
        "type": "Donation", "is_public": True, "from_name": "Sam", "message": "Love the app",
        "amount": "5.00", "url": "https://ko-fi.com/Home/CoffeeShop?txid=x", "email": "nobody@elsewhere.com",
        "currency": "USD", "is_subscription_payment": False, "is_first_subscription_payment": False,
        "kofi_transaction_id": f"tx-{message_id}", "tier_name": None,
    }
    data.update(fields)
    return data


def post(client, data):
    return client.post("/api/kofi/webhook", data={"data": json.dumps(data)})


def kofi_test_ping(message_id="test-1"):
    return payment(message_id, from_name="Ko-fi Team", message="Good luck with the integration!", amount="3.00",
                   email="someone@example.com", kofi_transaction_id=supporters.TEST_TRANSACTION_ID)


def stored(db, message_id="msg-1"):
    db.expire_all()
    return db.query(models.KofiPayment).filter(models.KofiPayment.message_id == message_id).one()


# ---------------------------------------------------------------- matching on arrival

def test_gmail_dots_plus_tags_and_case_still_match(client, db_session):
    user = member(db_session, "jdoe", email="jdoe@gmail.com")
    db_session.commit()
    assert post(client, payment(email="J.Doe+kofi@GoogleMail.com")).json()["linked"] is True
    assert stored(db_session).user_id == user.id


def test_same_inbox_match_must_be_unique_and_verified(client, db_session):
    member(db_session, "one", email="sam.lee@gmail.com")
    member(db_session, "two", email="samlee@gmail.com")
    member(db_session, "three", verified=False, email="pat@fastmail.com")
    db_session.commit()
    assert post(client, payment("a", email="s.amlee@gmail.com")).json()["linked"] is False
    assert post(client, payment("b", email="pat+x@fastmail.com")).json()["linked"] is False


def test_retyped_code_and_code_in_the_name_field_link(client, db_session):
    user = member(db_session, "coder", email="coder@example.com")
    db_session.commit()
    code = supporters.supporter_code(user.id)
    _, user_id, check = code.split("-")
    assert post(client, payment("a", message=f"for ot {user_id} – {check.upper()} thanks")).json()["linked"] is True
    assert post(client, payment("b", message=None, from_name=code)).json()["linked"] is True


def test_kofi_test_pings_are_recorded_but_never_linked_or_counted(client, db_session, monkeypatch):
    monkeypatch.setenv("KOFI_MONTHLY_GOAL", "100")
    member(db_session, "someone", email="someone@example.com")
    db_session.commit()
    assert post(client, kofi_test_ping()).json() == {"status": "recorded", "linked": False}
    row = stored(db_session, "test-1")
    assert row.test is True and row.user_id is None
    assert supporters.waiting_count(db_session) == 0
    assert supporters.unmatched_payments(db_session) == []
    assert supporters.goal_progress(db_session)["raised"] == 0


def test_waiting_payment_links_when_the_member_verifies_their_email(client, db_session):
    post(client, payment(email="late@example.com"))
    user = member(db_session, "late", verified=False, email="late@example.com")
    token = email_utils.generate_verification_token(user.email)
    user.verification_token = token
    db_session.commit()
    assert client.get(f"/auth/verify-email?token={token}").status_code == 200
    assert stored(db_session).user_id == user.id
    assert supporters.is_active(supporters.get_supporter(db_session, user.id))
    note = db_session.query(models.Notification).filter(models.Notification.user_id == user.id).one()
    assert note.type == "supporter_linked" and note.link == "/#supporter"


# ---------------------------------------------------------------- perks for a late link

def test_late_link_gets_full_days_from_now_and_keeps_the_payment_date(client, db_session):
    user = member(db_session, "patient")
    db_session.commit()
    post(client, payment())
    paid = datetime.utcnow() - timedelta(days=25)
    db_session.query(models.KofiPayment).update({"received_at": paid})
    db_session.commit()
    supporters.link_payment(db_session, "msg-1", user)
    supporter = supporters.get_supporter(db_session, user.id)
    assert supporter.since == paid
    assert supporter.active_until > datetime.utcnow() + timedelta(days=supporters.DONATION_DAYS - 1)


def test_late_membership_payments_stack_from_now(client, db_session):
    user = member(db_session, "member")
    db_session.commit()
    post(client, payment("m1", type="Subscription", is_subscription_payment=True, tier_name="Season Pass"))
    post(client, payment("m2", type="Subscription", is_subscription_payment=True, tier_name="Season Pass"))
    db_session.query(models.KofiPayment).update({"received_at": datetime.utcnow() - timedelta(days=40)})
    db_session.commit()
    supporters.link_payment(db_session, "m1", user)
    supporters.link_payment(db_session, "m2", user)
    supporter = supporters.get_supporter(db_session, user.id)
    assert supporter.member_until > datetime.utcnow() + timedelta(days=2 * supporters.MONTHLY_DAYS - 1)
    assert supporters.member_tier(supporter)["slug"] == "season_pass"


# ---------------------------------------------------------------- the owner's list

def test_owner_list_suggests_members_and_links_in_one_click(client, db_session):
    boss = member(db_session, "boss")
    member(db_session, "sam", verified=False, email="nobody@elsewhere.com")
    db_session.commit()
    post(client, payment())

    listed = client.get("/api/supporters/unmatched", headers=headers_for(boss)).json()
    assert listed["waiting"] == 1
    [row] = listed["payments"]
    assert row["looks_like_test"] is False
    assert row["suggestions"] == [{"username": "sam", "verified": False, "reason": "same email, not verified"}]

    linked = client.post("/api/supporters/link", headers=headers_for(boss), json={"message_id": "msg-1", "username": "@sam"})
    assert linked.status_code == 200
    assert client.get("/api/supporters/unmatched", headers=headers_for(boss)).json()["waiting"] == 0


def test_owner_can_search_by_email_and_link_by_email(client, db_session):
    boss = member(db_session, "boss")
    fan = member(db_session, "fan", email="fan.mail@gmail.com")
    db_session.commit()
    post(client, payment("a", email="other@elsewhere.com"))
    post(client, payment("b", email="fan.person@outlook.com"))

    found = client.get("/api/supporters/unmatched", params={"email": "FAN.person@outlook.com"}, headers=headers_for(boss)).json()
    assert [p["message_id"] for p in found["payments"]] == ["b"]
    assert found["members"] == []
    found = client.get("/api/supporters/unmatched", params={"email": "fanmail@gmail.com"}, headers=headers_for(boss)).json()
    assert found["members"] == [{"username": "fan", "verified": True}]
    bad = client.get("/api/supporters/unmatched", params={"email": "fan"}, headers=headers_for(boss))
    assert bad.status_code == 422

    linked = client.post("/api/supporters/link", headers=headers_for(boss), json={"message_id": "b", "username": "fanmail@gmail.com"})
    assert linked.json()["username"] == "fan"
    assert stored(db_session, "b").user_id == fan.id


def test_owner_can_set_aside_and_restore_a_payment(client, db_session):
    boss = member(db_session, "boss")
    fan = member(db_session, "fan")
    db_session.commit()
    post(client, payment())
    assert client.post("/api/supporters/set-aside", headers=headers_for(fan), json={"message_id": "msg-1"}).status_code == 403
    assert client.post("/api/supporters/set-aside", headers=headers_for(boss), json={"message_id": "msg-1"}).status_code == 200
    assert client.get("/api/supporters/unmatched", headers=headers_for(boss)).json() == {"payments": [], "waiting": 0}
    client.post("/api/supporters/set-aside", headers=headers_for(boss), json={"message_id": "msg-1", "set_aside": False})
    assert client.get("/api/supporters/unmatched", headers=headers_for(boss)).json()["waiting"] == 1


def test_older_payment_from_the_kofi_sample_sender_is_flagged(client, db_session):
    boss = member(db_session, "boss")
    db_session.commit()
    post(client, payment(from_name="Ko-fi Team"))
    [row] = client.get("/api/supporters/unmatched", headers=headers_for(boss)).json()["payments"]
    assert row["looks_like_test"] is True


def test_site_stats_counts_only_payments_that_need_linking(client, db_session):
    boss = member(db_session, "boss")
    db_session.commit()
    post(client, payment())
    post(client, kofi_test_ping())
    growth = client.get("/api/site-stats/overview", headers=headers_for(boss)).json()["growth"]["supporters"]
    assert growth["unlinked_payments"] == 1
    assert growth["payments"] == 1


# ---------------------------------------------------------------- "I donated but don't see my badge"

def test_claim_by_another_email_sends_a_confirmation_that_links(client, db_session, sent):
    fan = member(db_session, "fan")
    db_session.commit()
    post(client, payment(email="Fan.Old@Gmail.com"))

    reply = client.post("/api/supporter/claim", headers=headers_for(fan), json={"value": "fanold@gmail.com"})
    assert reply.json()["status"] == "email_sent"
    [mail] = sent
    assert mail["email"] == "fanold@gmail.com" and mail["username"] == "fan"
    assert stored(db_session).user_id is None  # nothing until the inbox owner confirms

    token = mail["url"].split("token=", 1)[1]
    page = client.get(f"/supporter/claim?token={token}")
    assert page.status_code == 200 and "@fan" in page.text and 'method="post"' in page.text
    assert stored(db_session).user_id is None  # a mail app opening the link changes nothing
    done = client.post(f"/supporter/claim?token={token}")
    assert "Thank you" in done.text
    assert stored(db_session).user_id == fan.id
    assert supporters.is_active(supporters.get_supporter(db_session, fan.id))
    assert "Already linked" in client.post(f"/supporter/claim?token={token}").text


def test_claim_reply_is_the_same_when_nothing_is_waiting(client, db_session, sent):
    fan = member(db_session, "fan")
    db_session.commit()
    post(client, payment(email="real@elsewhere.com"))
    found = client.post("/api/supporter/claim", headers=headers_for(fan), json={"value": "real@elsewhere.com"}).json()
    missing = client.post("/api/supporter/claim", headers=headers_for(fan), json={"value": "nope@elsewhere.com"}).json()
    assert found == missing
    assert [mail["email"] for mail in sent] == ["real@elsewhere.com"]


def test_claim_with_own_verified_email_links_at_once(client, db_session, sent):
    fan = member(db_session, "fan", email="fan@example.com")
    post(client, payment(email="other@elsewhere.com"))
    db_session.query(models.KofiPayment).update({"email_hash": supporters.email_hash("fan@example.com"),
                                                 "email_key": supporters.email_key("fan@example.com")})
    db_session.commit()
    reply = client.post("/api/supporter/claim", headers=headers_for(fan), json={"value": "FAN@example.com"}).json()
    assert reply["status"] == "linked" and reply["supporter"]["active"] is True
    assert sent == []


def test_bad_or_expired_claim_links_nothing(client, db_session):
    assert "expired" in client.get("/supporter/claim?token=nonsense").text
    assert "expired" in client.post("/supporter/claim?token=nonsense").text


def test_claim_by_transaction_id_waits_for_the_owner(client, db_session):
    boss = member(db_session, "boss")
    fan = member(db_session, "fan")
    db_session.commit()
    post(client, payment(kofi_transaction_id="ABCD-1234-efgh"))
    missing = client.post("/api/supporter/claim", headers=headers_for(fan), json={"value": "not-a-real-id"})
    assert missing.status_code == 404
    reply = client.post("/api/supporter/claim", headers=headers_for(fan), json={"value": " abcd-1234-EFGH "})
    assert reply.json()["status"] == "claimed"
    assert stored(db_session).user_id is None
    [row] = client.get("/api/supporters/unmatched", headers=headers_for(boss)).json()["payments"]
    assert row["claimed"] is True
    assert row["suggestions"][0] == {"username": "fan", "verified": True, "reason": "claimed it with the transaction id"}


def test_test_pings_cannot_be_claimed(client, db_session, sent):
    fan = member(db_session, "fan")
    db_session.commit()
    post(client, kofi_test_ping())
    client.post("/api/supporter/claim", headers=headers_for(fan), json={"value": "someone@example.com"})
    assert sent == []
    assert client.post("/api/supporter/claim", headers=headers_for(fan),
                       json={"value": supporters.TEST_TRANSACTION_ID}).status_code == 404


# ---------------------------------------------------------------- migration

def test_migration_adds_columns_and_keeps_existing_payments(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE kofi_payments (id INTEGER PRIMARY KEY, message_id VARCHAR(80) NOT NULL UNIQUE, "
                          "kind VARCHAR(24) NOT NULL, amount VARCHAR(16), currency VARCHAR(8), monthly BOOLEAN NOT NULL, "
                          "tier_name VARCHAR(40), email_hash VARCHAR(64), from_name VARCHAR(80), user_id INTEGER, "
                          "received_at TIMESTAMP NOT NULL, linked_at TIMESTAMP)"))
        conn.execute(text("INSERT INTO kofi_payments (message_id, kind, monthly, email_hash, received_at) "
                          "VALUES ('old', 'donation', 0, 'abc', '2026-10-10 10:00:00')"))
    monkeypatch.setattr(migrations, "engine", engine)
    migrations.add_kofi_matching_columns()
    migrations.add_kofi_matching_columns()
    columns = {col["name"] for col in inspect(engine).get_columns("kofi_payments")}
    assert {"email_key", "transaction_hash", "test", "dismissed_at", "claimed_by", "claimed_at"} <= columns
    with engine.connect() as conn:
        row = conn.execute(text("SELECT message_id, email_hash, test, dismissed_at, user_id FROM kofi_payments")).one()
    assert tuple(row) == ("old", "abc", 0, None, None)


def test_email_check_is_plain_string_work():
    assert supporters.looks_like_email("fan@example.com")
    assert not supporters.looks_like_email("fan")
    assert not supporters.looks_like_email("a@b@c.com")
    assert not supporters.looks_like_email("a@" + "!" * 5000)
