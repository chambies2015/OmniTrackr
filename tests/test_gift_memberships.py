"""Gift supporter memberships (Nov 23 2026): OT-GIFT Ko-fi payments, gift codes, opening a gift, the giver's card
page, "Lost the email?" and the owner's gift tools."""
import json
from datetime import datetime, timedelta

import pytest

from app import auth, gift_memberships as gifts, models, site_traffic, supporters
from app.site_traffic import RECORDER
from tests.test_founding_supporters import CHROME, TOKEN, headers, member, pay, setup  # noqa: F401  (autouse Ko-fi token)


@pytest.fixture(autouse=True)
def mail(monkeypatch):
    sent = []

    async def fake_send(email, items, resend=False):
        sent.append({"email": email, "items": items, "resend": resend})
        return True

    from app import email as email_utils
    monkeypatch.setattr(email_utils, "send_gift_email", fake_send)
    return sent


def gift_pay(client, message_id, email, message="OT-GIFT", amount="9.00", **fields):
    return pay(client, message_id, email, message=message, amount=amount, **fields)


def only_gift(db):
    rows = db.query(models.GiftMembership).all()
    assert len(rows) == 1
    return rows[0]


def owner(db, monkeypatch, name="boss"):
    monkeypatch.setenv("ADMIN_USERNAMES", name)
    return member(db, name)


def cookie_client(client, user):
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(user))
    return client


# ---------------------------------------------------------------- buying one

def test_ot_gift_payment_makes_a_gift_instead_of_perks_for_the_payer(client, db_session, mail):
    ana = member(db_session, "ana")
    response = gift_pay(client, "g-1", "ana@example.com")
    assert response.json() == {"status": "recorded", "linked": False, "gift": True}
    gift = only_gift(db_session)
    assert gift.months == 3 and gift.giver_id == ana.id and gift.source == "kofi"
    assert supporters.get_supporter(db_session, ana.id) is None
    payment = db_session.query(models.KofiPayment).one()
    assert payment.gift is True and payment.user_id is None
    # Never on the owner's "to link" list, and a later email check doesn't link it either.
    assert supporters.waiting_count(db_session) == 0
    assert supporters.link_pending_by_email(db_session, ana) == 0
    assert mail == [{"email": "ana@example.com", "items": [gifts.email_item(gift)], "resend": False}]
    assert mail[0]["items"][0]["url"].endswith(gifts.path_of(gift))
    note = db_session.query(models.Notification).filter(models.Notification.user_id == ana.id).one()
    assert note.type == "gift_ready" and note.link == "/supporters/gift#your-gifts"


def test_the_member_code_ties_the_gift_to_them_whatever_email_paid(client, db_session):
    ben = member(db_session, "ben")
    gift_pay(client, "g-2", "someone-else@example.org", message=f"Merry Christmas {gifts.marker_for(ben.id)}!")
    assert only_gift(db_session).giver_id == ben.id


def test_a_wrong_check_still_makes_a_gift_but_ties_it_to_nobody(client, db_session):
    member(db_session, "cal")
    gift_pay(client, "g-3", "stranger@example.org", message="OT-GIFT-1-000000")
    gift = only_gift(db_session)
    assert gift.giver_id is None


@pytest.mark.parametrize("message", ["ot gift", "OT-GIFT", "please make this an ot_gift for my sister", "OTGIFT"])
def test_marker_spellings(message):
    assert gifts.find_marker({"message": message}) == {"giver_id": None}


@pytest.mark.parametrize("message", ["a gift for you", "OT-GIFTS", "NOT-GIFT", "", None])
def test_not_a_marker(message):
    assert gifts.find_marker({"message": message}) is None


@pytest.mark.parametrize("amount, months", [("3.00", 1), ("5.00", 1), ("6", 2), ("9.00", 3), ("18.00", 6),
                                            ("36.00", 12), ("100", 12), ("1.00", 1), ("junk", 1)])
def test_months_from_the_amount(amount, months):
    assert gifts.months_for(amount) == months


def test_days_per_length():
    assert [gifts.days_for(m) for m in (1, 3, 6, 12)] == [30, 91, 183, 365]


def test_a_membership_payment_with_ot_gift_stays_a_membership(client, db_session):
    dee = member(db_session, "dee")
    gift_pay(client, "sub-1", "dee@example.com", type="Subscription", is_subscription_payment=True, tier_name="Popcorn")
    assert db_session.query(models.GiftMembership).count() == 0
    assert supporters.is_member(supporters.get_supporter(db_session, dee.id))


def test_a_retried_delivery_makes_one_gift(client, db_session, mail):
    gift_pay(client, "g-dup", "eve@example.com")
    assert gift_pay(client, "g-dup", "eve@example.com").json()["status"] == "duplicate"
    only_gift(db_session)
    assert len(mail) == 1


def test_ko_fi_test_pings_never_make_gifts(client, db_session):
    gift_pay(client, "g-test", "jo.example@example.com", from_name="Ko-fi Team",
             kofi_transaction_id=supporters.TEST_TRANSACTION_ID)
    assert db_session.query(models.GiftMembership).count() == 0


def test_codes_are_not_stored_and_read_back_the_same(client, db_session):
    gift_pay(client, "g-code", "fay@example.com")
    gift = only_gift(db_session)
    code = gifts.code_of(gift)
    assert len(code) == 14 and code.count("-") == 2
    assert all(ch in gifts.ALPHABET for ch in code.replace("-", ""))
    assert code.replace("-", "") not in json.dumps({c.name: str(getattr(gift, c.name)) for c in gift.__table__.columns})
    assert gifts.by_code(db_session, code.lower().replace("-", " ")).id == gift.id
    assert gifts.by_code(db_session, "ABCD-EFGH-JKMN") is None
    assert gifts.normalize("ABCD-EFGH-JKM0") is None  # 0 is never in a code


# ---------------------------------------------------------------- opening one

def test_guest_sees_the_card_and_sign_up_links_that_come_back(client, db_session):
    gift_pay(client, "g-guest", "gil@example.com")
    gift = only_gift(db_session)
    gift.to_name, gift.from_name, gift.note = "Sam", "Alex <b>", "Line one\nLine two"
    db_session.commit()
    path = gifts.path_of(gift)
    response = client.get(path, headers=CHROME)
    assert response.status_code == 200
    html = response.text
    assert "For Sam" in html and "From Alex &lt;b&gt;" in html and "<p>Line one</p><p>Line two</p>" in html
    assert f'/?next={path.replace("/", "%2F")}#signup' in html
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert "no-store" in response.headers["Cache-Control"]
    db_session.refresh(gift)
    assert gift.opened == 1


def test_member_opens_a_gift_and_gets_numbered_perks(client, db_session, monkeypatch):
    paid = datetime(2026, 12, 20, 12)
    monkeypatch.setattr(supporters, "_now", lambda: paid)
    gift_pay(client, "g-open", "hal@example.com")
    gift = only_gift(db_session)
    opened_at = datetime(2027, 1, 6, 9)
    monkeypatch.setattr(gifts, "_now", lambda: opened_at)
    monkeypatch.setattr(supporters, "_now", lambda: opened_at)
    ivy = member(db_session, "ivy")
    cookie_client(client, ivy)
    page = client.get(gifts.path_of(gift), headers=CHROME)
    assert "Open my gift" in page.text and "@ivy" in page.text
    response = client.post(gifts.path_of(gift) + "/open", headers=CHROME, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].endswith("?opened=1")
    supporter = supporters.get_supporter(db_session, ivy.id)
    assert supporter.number == 1 and supporter.active_until == opened_at + timedelta(days=91)
    # Bought in December, opened in January: still a founding supporter, as the pages promise.
    assert supporter.since == paid and supporters.is_founding(supporter)
    done = client.get(response.headers["location"], headers=CHROME)
    assert "Your supporter perks are on" in done.text and "Pick your theme" in done.text
    status = supporters.status_payload(db_session, ivy)
    assert status["active"] and status["gift"]["count"] == 1 and status["months"] == 0


def test_a_gift_adds_after_the_perks_someone_already_has(client, db_session):
    jo = member(db_session, "jo")
    pay(client, "own-1", "jo@example.com")
    before = supporters.get_supporter(db_session, jo.id).active_until
    gift_pay(client, "g-stack", "kim@example.com", amount="3.00")
    gifts.redeem(db_session, jo, gifts.code_of(only_gift(db_session)))
    db_session.expire_all()
    assert supporters.get_supporter(db_session, jo.id).active_until == before + timedelta(days=30)


def test_a_gift_opens_once(client, db_session):
    gift_pay(client, "g-once", "lee@example.com")
    gift = only_gift(db_session)
    code = gifts.code_of(gift)
    mo, ned = member(db_session, "mo"), member(db_session, "ned")
    gifts.redeem(db_session, mo, code)
    with pytest.raises(gifts.GiftError) as error:
        gifts.redeem(db_session, ned, code)
    assert error.value.status == 409
    assert supporters.get_supporter(db_session, ned.id) is None
    assert gifts.redeem(db_session, mo, code).id == gift.id  # pressing again on your own is harmless
    cookie_client(client, ned)
    assert "has been opened" in client.get(gifts.path_of(gift), headers=CHROME).text


def test_two_people_pressing_at_once_only_one_wins(client, db_session, monkeypatch):
    gift_pay(client, "g-race", "ora@example.com")
    gift = only_gift(db_session)
    code = gifts.code_of(gift)
    pat, quin = member(db_session, "pat"), member(db_session, "quin")
    stale = gifts.by_code(db_session, code)
    gifts.redeem(db_session, pat, code)
    # The second press read the gift before the first one saved.
    stale.redeemed_at = None
    monkeypatch.setattr(gifts, "by_code", lambda db, raw: stale)
    with pytest.raises(gifts.GiftError):
        gifts.redeem(db_session, quin, code)
    db_session.expire_all()
    assert supporters.get_supporter(db_session, quin.id) is None


def test_an_account_removed_after_opening_does_not_reopen_the_gift(client, db_session):
    gift_pay(client, "g-gone", "rae@example.com")
    gift = only_gift(db_session)
    sid, tom = member(db_session, "sid"), member(db_session, "tom")
    gifts.redeem(db_session, sid, gifts.code_of(gift))
    gift.redeemed_by = None  # ON DELETE SET NULL
    db_session.commit()
    with pytest.raises(gifts.GiftError):
        gifts.redeem(db_session, tom, gifts.code_of(gift))


def test_the_giver_cannot_open_their_own_gift(client, db_session):
    uma = member(db_session, "uma")
    gift_pay(client, "g-self", "uma@example.com")
    gift = only_gift(db_session)
    with pytest.raises(gifts.GiftError) as error:
        gifts.redeem(db_session, uma, gifts.code_of(gift))
    assert error.value.status == 403
    cookie_client(client, uma)
    page = client.get(gifts.path_of(gift), headers=CHROME).text
    assert "This is your gift" in page and gifts.manage_path(gift) in page
    db_session.refresh(gift)
    assert gift.opened == 0  # the giver checking their own link isn't counted


def test_unknown_and_turned_off_codes_are_404(client, db_session):
    assert client.get("/gift/ABCD-EFGH-JKMN").status_code == 404
    assert client.get("/gift/not-a-code").status_code == 404
    gift_pay(client, "g-off", "val@example.com")
    gift = only_gift(db_session)
    gift.cancelled_at = datetime.utcnow()
    db_session.commit()
    assert client.get(gifts.path_of(gift)).status_code == 404


def test_typed_codes_go_to_the_gift(client, db_session):
    gift_pay(client, "g-typed", "wes@example.com")
    gift = only_gift(db_session)
    raw = gifts.code_of(gift).replace("-", "").lower()
    response = client.post("/gift", data={"code": raw}, follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == gifts.path_of(gift)
    assert client.get(f"/gift/{raw}", follow_redirects=False).headers["location"] == gifts.path_of(gift)
    assert client.post("/gift", data={"code": "nope"}).status_code == 422


def test_opening_needs_an_account(client, db_session):
    gift_pay(client, "g-anon", "xia@example.com")
    gift = only_gift(db_session)
    assert client.post(gifts.path_of(gift) + "/open").status_code == 401
    assert client.post("/api/gift/redeem", json={"code": gifts.code_of(gift)}).status_code == 401


def test_redeem_api(client, db_session):
    gift_pay(client, "g-api", "yan@example.com")
    zoe = member(db_session, "zoe")
    response = client.post("/api/gift/redeem", json={"code": gifts.code_of(only_gift(db_session))}, headers=headers(zoe))
    assert response.status_code == 200 and response.json()["supporter"]["active"]
    assert client.post("/api/gift/redeem", json={"code": "ABCD-EFGH-JKMN"}, headers=headers(zoe)).status_code == 404


# ---------------------------------------------------------------- the giver's card page

def test_card_page_needs_the_whole_token(client, db_session):
    gift_pay(client, "g-card", "abe@example.com")
    gift = only_gift(db_session)
    page = client.get(gifts.manage_path(gift))
    assert page.status_code == 200 and gifts.code_of(gift) in page.text and "data:image/svg+xml;base64," in page.text
    assert page.headers["X-Robots-Tag"] == "noindex, nofollow"
    token = gifts.manage_token(gift)
    wrong = token[:-1] + ("1" if token[-1] == "0" else "0")
    assert client.get(f"/supporters/gift/manage/{wrong}").status_code == 404
    assert client.get(f"/supporters/gift/manage/{gift.id}-{'0' * 32}").status_code == 404
    assert client.get("/supporters/gift/manage/99999-" + token.split("-", 1)[1]).status_code == 404


def test_writing_the_card(client, db_session):
    gift_pay(client, "g-write", "bea@example.com")
    gift = only_gift(db_session)
    path = gifts.manage_path(gift)
    response = client.post(path, data={"to_name": "  Sam‮  ", "from_name": "Alex", "note": "Hi\r\n\r\n\r\n\r\nthere​"},
                           follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(gift)
    assert (gift.to_name, gift.from_name, gift.note) == ("Sam", "Alex", "Hi\n\nthere")
    too_long = client.post(path, data={"to_name": "x" * 41, "from_name": "", "note": ""})
    assert too_long.status_code == 422 and "40 characters" in too_long.text
    db_session.refresh(gift)
    assert gift.to_name == "Sam"
    gifts.redeem(db_session, member(db_session, "cy"), gifts.code_of(gift))
    locked = client.post(path, data={"to_name": "New", "from_name": "", "note": ""})
    assert locked.status_code == 409


def test_member_sees_their_gifts_and_code(client, db_session):
    dot = member(db_session, "dot")
    cookie_client(client, dot)
    page = client.get("/supporters/gift", headers=CHROME).text
    assert gifts.marker_for(dot.id) in page and "Gifts you buy" in page
    gift_pay(client, "g-mine", "other@example.org", message=gifts.marker_for(dot.id))
    page = client.get("/supporters/gift", headers=CHROME).text
    gift = only_gift(db_session)
    assert gifts.manage_path(gift) in page and "Not opened yet" in page


def test_guest_giving_page(client, db_session):
    response = client.get("/supporters/gift", headers=CHROME)
    assert response.status_code == 200
    assert "OT-GIFT" in response.text and 'data-kofi-place="gift"' in response.text
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"


# ---------------------------------------------------------------- "Lost the email?"

def test_resend_reads_the_same_whether_or_not_a_gift_exists(client, db_session, mail):
    gift_pay(client, "g-lost", "Ed.Wards+kofi@gmail.com")
    mail.clear()
    found = client.post("/api/gift/resend", json={"email": "edwards@gmail.com"})
    missing = client.post("/api/gift/resend", json={"email": "nobody@example.com"})
    assert found.status_code == missing.status_code == 200 and found.json() == missing.json()
    assert [entry["email"] for entry in mail] == ["edwards@gmail.com"] and mail[0]["resend"] is True
    assert client.post("/api/gift/resend", json={"email": "not-an-email"}).status_code == 422


# ---------------------------------------------------------------- the owner

def test_owner_turns_a_waiting_payment_into_a_gift(client, db_session, monkeypatch):
    boss = owner(db_session, monkeypatch)
    pay(client, "forgot-1", "fern@example.org", amount="18.00")
    assert supporters.waiting_count(db_session) == 1
    response = client.post("/api/supporters/gifts/from-payment", json={"message_id": "forgot-1"}, headers=headers(boss))
    assert response.status_code == 200 and response.json()["months"] == 6
    assert supporters.waiting_count(db_session) == 0
    again = client.post("/api/supporters/gifts/from-payment", json={"message_id": "forgot-1"}, headers=headers(boss))
    assert again.status_code == 409


def test_owner_makes_and_turns_off_gifts(client, db_session, monkeypatch):
    boss = owner(db_session, monkeypatch)
    made = client.post("/api/supporters/gifts", json={"months": 12}, headers=headers(boss)).json()
    assert made["months_label"] == "a year" and made["url"].startswith("https://omnitrackr.xyz/gift/")
    listed = client.get("/api/supporters/gifts", headers=headers(boss)).json()["gifts"]
    assert listed[0]["code"] == made["code"] and listed[0]["source"] == "owner"
    assert client.post(f"/api/supporters/gifts/{made['id']}/cancel", headers=headers(boss)).json()["state"] == "cancelled"
    assert client.get(f"/gift/{made['code']}").status_code == 404


def test_only_the_owner_has_gift_tools(client, db_session, monkeypatch):
    owner(db_session, monkeypatch)
    gus = member(db_session, "gus")
    assert client.get("/api/supporters/gifts", headers=headers(gus)).status_code == 403
    assert client.post("/api/supporters/gifts", json={"months": 3}, headers=headers(gus)).status_code == 403
    assert client.post("/api/supporters/gifts/1/cancel", headers=headers(gus)).status_code == 403


# ---------------------------------------------------------------- around the site

def test_gift_links_are_counted_as_private_links():
    assert site_traffic.mask_private_link("/gift/ABCD-EFGH-JKMN") == "/gift/(private link)"
    assert site_traffic.mask_private_link("/supporters/gift/manage/1-abc") == "/supporters/gift/manage/(private link)"
    assert site_traffic.mask_private_link("/supporters/gift") == "/supporters/gift"


def test_supporters_page_and_gift_guide_mention_gifts(client, db_session):
    page = client.get("/supporters").text
    assert 'href="/supporters/gift"' in page and "OT-GIFT" in page and "<!--SUPPORTERS_GIFT_FOUNDING-->" not in page
    guide = client.get("/holidays/gifts").text
    assert 'id="give-omnitrackr"' in guide and 'href="/supporters/gift"' in guide


def test_site_stats_counts_gifts(client, db_session, monkeypatch):
    boss = owner(db_session, monkeypatch)
    gift_pay(client, "g-stats", "hil@example.com")
    gifts.redeem(db_session, member(db_session, "ida"), gifts.code_of(only_gift(db_session)))
    data = client.get("/api/site-stats/overview?days=30", headers=headers(boss)).json()
    counts = data["growth"]["supporters"]["gifts"]
    assert counts["bought"] == 1 and counts["opened"] == 1 and counts["waiting"] == 0


def test_migration_adds_the_gift_column_to_old_payment_tables(db_session, monkeypatch):
    from sqlalchemy import inspect, text
    from app import migrations
    engine = db_session.get_bind()
    monkeypatch.setattr(migrations, "engine", engine)
    db_session.close()
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS gift_memberships"))
        conn.execute(text("ALTER TABLE kofi_payments DROP COLUMN gift"))
        conn.execute(text("INSERT INTO kofi_payments (message_id, kind, monthly, test, received_at) "
                          "VALUES ('old-1', 'donation', 0, 0, CURRENT_TIMESTAMP)"))
        conn.commit()
    migrations.add_kofi_gift_column()
    migrations.add_kofi_gift_column()  # runs again on every start
    assert "gift" in {col["name"] for col in inspect(engine).get_columns("kofi_payments")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT gift FROM kofi_payments WHERE message_id = 'old-1'")).scalar() in (0, False)
    models.GiftMembership.__table__.create(bind=engine, checkfirst=True)
