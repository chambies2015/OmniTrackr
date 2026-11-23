"""Nov 23 2026 sweep of gift supporter perks (PR #330) and the home start-up requests (PR #329)."""
from datetime import datetime

from app import gift_memberships as gifts, models, supporters
from tests.test_founding_supporters import CHROME, headers, member, pay, setup  # noqa: F401  (autouse Ko-fi token)
from tests.test_gift_memberships import cookie_client, gift_pay, mail, only_gift, owner  # noqa: F401  (autouse mail)


def test_a_plain_supporter_code_next_to_ot_gift_does_not_make_that_member_the_giver(client, db_session):
    # The payer put the code of the friend the gift is for. That friend must still be able to open it.
    friend = member(db_session, "friend")
    gift_pay(client, "sw-1", "payer@example.org", message=f"OT-GIFT for {supporters.supporter_code(friend.id)}")
    gift = only_gift(db_session)
    assert gift.giver_id is None
    gifts.redeem(db_session, friend, gifts.code_of(gift))
    assert supporters.is_active(supporters.get_supporter(db_session, friend.id))


def test_the_gift_code_or_the_payers_email_still_ties_a_gift_to_the_giver(client, db_session):
    ana, ben = member(db_session, "ana"), member(db_session, "ben")
    gift_pay(client, "sw-2", "ana@example.com", message=f"OT-GIFT {supporters.supporter_code(ben.id)}")
    gift_pay(client, "sw-3", "other@example.org", message=gifts.marker_for(ben.id))
    by_payment = {row.payment_id: row.giver_id for row in db_session.query(models.GiftMembership).all()}
    payments = {row.message_id: row.id for row in db_session.query(models.KofiPayment).all()}
    assert by_payment[payments["sw-2"]] == ana.id
    assert by_payment[payments["sw-3"]] == ben.id


def test_the_owner_cannot_link_a_gift_payment_to_a_member(client, db_session, monkeypatch):
    boss = owner(db_session, monkeypatch)
    cat = member(db_session, "cat")
    gift_pay(client, "sw-4", "stranger@example.org")
    response = client.post("/api/supporters/link", json={"message_id": "sw-4", "username": "cat"}, headers=headers(boss))
    assert response.status_code == 409
    assert supporters.get_supporter(db_session, cat.id) is None
    assert db_session.query(models.KofiPayment).one().user_id is None


def test_a_members_gift_page_is_not_kept_on_the_device(client, db_session):
    guest = client.get("/supporters/gift", headers=CHROME)
    assert guest.headers["Cache-Control"] == "private, no-cache"
    dee = member(db_session, "dee")
    signed_in = client.get("/supporters/gift", headers=headers(dee))
    assert signed_in.headers["Cache-Control"] == "private, no-store"


def test_the_sample_badge_on_a_december_gift_stays_gold_in_the_new_year(client, db_session, monkeypatch):
    monkeypatch.setattr(supporters, "_now", lambda: datetime(2026, 12, 28, 12))
    gift_pay(client, "sw-5", "eve@example.com")
    december = only_gift(db_session)
    monkeypatch.setattr(supporters, "_now", lambda: datetime(2027, 2, 3, 12))
    monkeypatch.setattr(gifts, "_now", lambda: datetime(2027, 2, 3, 12))
    page = client.get(gifts.path_of(december), headers=CHROME).text
    assert "becomes a founding supporter" in page or "makes you a founding supporter" in page
    assert "gm-sample gm-sample--gold" in page and "★ Founding supporter" in page
    gift_pay(client, "sw-6", "eve@example.com")
    february = db_session.query(models.GiftMembership).order_by(models.GiftMembership.id.desc()).first()
    later = client.get(gifts.path_of(february), headers=CHROME).text
    assert "gm-sample--gold" not in later and "♥ Supporter" in later
