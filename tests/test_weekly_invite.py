"""Weekly email invites (Oct 7): one-click opt-in link in emails, button in "What's new"."""
import asyncio
from datetime import datetime

from itsdangerous import URLSafeTimedSerializer

from app import announcements, digest, models
from tests.test_retention_oct import member, run_send


def subscribed(db, user):
    return digest.subscription_for(db, user.id) is not None


# ---------------------------------------------------------------- tokens

def test_tokens_round_trip_and_reject_tampering():
    token = digest.subscribe_link_token(42)
    assert digest.user_id_from_subscribe_token(token) == 42
    for bad in ("", None, "x" * 400, token[:-3] + "abc", announcements.unsubscribe_token(42)):
        assert digest.user_id_from_subscribe_token(bad) is None


def test_tokens_expire(monkeypatch):
    token = digest.subscribe_link_token(7)
    monkeypatch.setattr(digest, "SUBSCRIBE_LINK_MAX_AGE", -1)
    assert digest.user_id_from_subscribe_token(token) is None


def test_other_signed_values_are_not_accepted():
    from app.email import SECRET_KEY
    wrong_salt = URLSafeTimedSerializer(SECRET_KEY, salt="something-else").dumps({"u": 3})
    assert digest.user_id_from_subscribe_token(wrong_salt) is None


# ---------------------------------------------------------------- the link

def test_opening_the_link_only_asks_it_never_subscribes(client, db_session):
    user = member(db_session, "reader")
    db_session.commit()
    page = client.get(f"/email/weekly/subscribe?token={digest.subscribe_link_token(user.id)}")
    assert page.status_code == 200
    assert "Yes, email me weekly" in page.text and 'method="post"' in page.text
    assert page.headers["x-robots-tag"] == "noindex, nofollow"
    assert page.headers["cache-control"] == "no-store"
    assert not subscribed(db_session, user)  # mail-app link scanners prefetch GETs


def test_pressing_the_button_subscribes_once(client, db_session):
    user = member(db_session, "reader")
    db_session.commit()
    url = f"/email/weekly/subscribe?token={digest.subscribe_link_token(user.id)}"
    assert "Your first weekly email arrives" in client.post(url).text
    assert "Your first weekly email arrives" in client.post(url).text
    assert db_session.query(models.EmailDigestSubscription).filter_by(user_id=user.id).count() == 1
    assert "already subscribed" in client.get(url).text.replace("&#x27;", "'")


def test_unverified_inactive_and_bad_links_do_nothing(client, db_session):
    unverified = member(db_session, "newbie", verified=False)
    gone = member(db_session, "gone", active=False)
    db_session.commit()
    for token in (digest.subscribe_link_token(unverified.id), digest.subscribe_link_token(gone.id),
                  digest.subscribe_link_token(99999), "forged"):
        assert "expired" in client.post(f"/email/weekly/subscribe?token={token}").text
    assert db_session.query(models.EmailDigestSubscription).count() == 0


def test_unsubscribe_still_works_after_subscribing_by_link(client, db_session):
    user = member(db_session, "reader")
    db_session.commit()
    client.post(f"/email/weekly/subscribe?token={digest.subscribe_link_token(user.id)}")
    token = digest.subscription_for(db_session, user.id).token
    client.post(f"/email/unsubscribe?token={token}")
    db_session.expire_all()
    assert not subscribed(db_session, user)


# ---------------------------------------------------------------- "What's new" email

def test_whats_new_has_a_weekly_button_for_non_subscribers(db_session):
    user = member(db_session, "reader")
    db_session.commit()
    subject, html, text, _unsub = announcements.email_for(db_session, user)
    assert "Email me weekly" in html and "/email/weekly/subscribe?token=" in html
    assert "/email/weekly/subscribe?token=" in text
    token = html.split("/email/weekly/subscribe?token=")[1].split('"')[0]
    assert digest.user_id_from_subscribe_token(token) == user.id  # the link is for this member only
    assert announcements.WEEKLY_FEATURE not in html  # replaced by the button, not repeated


def test_subscribers_get_no_button(db_session):
    user = member(db_session, "reader")
    db_session.commit()
    digest.subscribe(db_session, user.id)
    _subject, html, text, _unsub = announcements.email_for(db_session, user)
    assert "/email/weekly/subscribe" not in html and "/email/weekly/subscribe" not in text
    assert announcements.WEEKLY_FEATURE in html


def test_campaign_sends_carry_each_members_own_link(db_session):
    a, b = member(db_session, "ann"), member(db_session, "ben")
    db_session.commit()
    announcements.set_status(db_session, "sending")
    sent = []
    run_send(db_session, sent, now=datetime.utcnow())
    links = {to: html.split("/email/weekly/subscribe?token=")[1].split('"')[0] for to, _s, html, _u in sent}
    assert digest.user_id_from_subscribe_token(links["ann@example.com"]) == a.id
    assert digest.user_id_from_subscribe_token(links["ben@example.com"]) == b.id
    assert not subscribed(db_session, a) and not subscribed(db_session, b)  # sending never subscribes anyone
