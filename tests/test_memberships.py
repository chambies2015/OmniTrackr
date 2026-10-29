"""Monthly Ko-fi memberships (Oct 28): tiers, member banners, moving banners and the Director's Cut credits."""
from datetime import datetime, timedelta

from app import models, supporters
from tests.test_supporters import headers_for, kofi_token, member, payment, post  # noqa: F401 (kofi_token is autouse)


def _monthly(message_id, **fields):
    return payment(message_id, type="Subscription", is_subscription_payment=True, **fields)


def _profile(db, user):
    db.add(models.PublicProfile(user_id=user.id, enabled=True))


def test_tier_comes_from_the_ko_fi_name_then_the_amount():
    assert supporters.resolve_tier("Season Pass", "3.00") == "season_pass"
    assert supporters.resolve_tier("director's cut", None) == "directors_cut"
    assert supporters.resolve_tier("Supporter", "10.00") == "directors_cut"
    assert supporters.resolve_tier(None, "5") == "season_pass"
    assert supporters.resolve_tier(None, "1.50") == "popcorn"


def test_membership_payment_records_the_tier(client, db_session):
    user = member(db_session, "jo")
    db_session.commit()
    post(client, _monthly("s1", tier_name="Season Pass", amount="5.00"))
    supporter = supporters.get_supporter(db_session, user.id)
    assert supporter.tier == "season_pass" and supporters.is_member(supporter)
    assert db_session.query(models.KofiPayment).one().tier_name == "Season Pass"
    data = client.get("/api/supporter", headers=headers_for(user)).json()
    assert data["member"] is True and data["tier_name"] == "Season Pass" and data["can_animate"] is True
    assert set(supporters.MEMBER_BANNERS) <= set(data["unlocked_banners"])
    assert data["tiers_url"] == "https://ko-fi.com/omnitrackr/tiers"


def test_one_time_supporters_keep_every_banner_they_had_but_not_member_ones(client, db_session):
    user = member(db_session, "tip", email="jo@example.com")
    db_session.commit()
    post(client, payment("t1"))
    data = client.get("/api/supporter", headers=headers_for(user)).json()
    assert data["member"] is False and data["unlocked_banners"] == list(supporters.BANNERS)
    assert client.put("/api/supporter", headers=headers_for(user), json={"banner": "vinyl"}).status_code == 200
    assert client.put("/api/supporter", headers=headers_for(user), json={"banner": "neon"}).status_code == 403
    assert client.put("/api/supporter", headers=headers_for(user), json={"banner_motion": True}).status_code == 403


def test_a_tip_from_a_member_leaves_the_membership_alone(client, db_session):
    user = member(db_session, "both", email="jo@example.com")
    db_session.commit()
    post(client, _monthly("s1", tier_name="Popcorn", amount="3.00"))
    post(client, payment("t1"))
    supporter = supporters.get_supporter(db_session, user.id)
    assert supporter.monthly is True and supporter.tier == "popcorn" and supporters.is_member(supporter)


def test_popcorn_members_get_member_banners_but_not_motion(client, db_session):
    user = member(db_session, "pop", email="jo@example.com")
    db_session.commit()
    post(client, _monthly("s1", tier_name="Popcorn", amount="3.00"))
    assert client.put("/api/supporter", headers=headers_for(user), json={"banner": "marquee"}).status_code == 200
    assert client.put("/api/supporter", headers=headers_for(user), json={"banner_motion": True}).status_code == 403


def test_profile_shows_the_tier_and_a_moving_banner(client, db_session):
    user = member(db_session, "jo")
    _profile(db_session, user)
    db_session.commit()
    post(client, _monthly("s1", tier_name="Season Pass", amount="5.00"))
    assert client.put("/api/supporter", headers=headers_for(user),
                      json={"banner": "neon", "banner_motion": True}).status_code == 200
    page = client.get("/u/jo").text
    assert "Season Pass member</a>" in page
    assert 'class="profile-banner profile-banner--neon profile-banner--motion"' in page


def test_a_lapsed_membership_hides_member_extras_but_keeps_the_choice(client, db_session):
    user = member(db_session, "gone", email="jo@example.com")
    _profile(db_session, user)
    db_session.commit()
    post(client, _monthly("s1", tier_name="Season Pass", amount="5.00"))
    client.put("/api/supporter", headers=headers_for(user), json={"banner": "comic", "banner_motion": True})
    supporter = supporters.get_supporter(db_session, user.id)
    supporter.member_until = datetime.utcnow() - timedelta(days=1)  # still a supporter from a later tip
    supporter.active_until = datetime.utcnow() + timedelta(days=10)
    db_session.commit()
    page = client.get("/u/gone").text
    assert "profile-banner--comic" not in page and "member</a>" not in page
    assert supporters.get_supporter(db_session, user.id).banner == "comic"


def test_directors_cut_unlocks_gold_and_the_credits(client, db_session):
    user = member(db_session, "auteur", email="jo@example.com")
    db_session.commit()
    post(client, _monthly("s1", tier_name="Director's Cut", amount="10.00"))
    supporter = supporters.get_supporter(db_session, user.id)
    supporter.since = datetime(2027, 3, 1)  # not founding, so gold comes from the tier
    db_session.commit()
    assert client.put("/api/supporter", headers=headers_for(user), json={"accent": "gold", "on_wall": True}).status_code == 200
    page = client.get("/supporters").text
    assert "support-credits" in page and ">auteur</span>" in page


def test_supporters_page_lists_the_tiers(client):
    page = client.get("/supporters").text
    assert 'id="tiers-heading"' in page and "<!--SUPPORTERS_TIERS-->" not in page
    for tier in supporters.TIERS:
        assert f"Join {tier['name']}".replace("'", "&#x27;") in page
    assert "support-credits" not in page


def test_existing_monthly_supporters_become_members_once(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text

    from app import migrations

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE supporters (id INTEGER PRIMARY KEY, user_id INTEGER, since TIMESTAMP, "
                          "active_until TIMESTAMP, monthly BOOLEAN NOT NULL DEFAULT FALSE)"))
        conn.execute(text("CREATE TABLE kofi_payments (id INTEGER PRIMARY KEY, message_id VARCHAR(80))"))
        conn.execute(text("INSERT INTO supporters VALUES (1, 1, '2026-10-01', '2026-11-20', TRUE), "
                          "(2, 2, '2026-10-01', '2026-11-05', FALSE)"))
    monkeypatch.setattr(migrations, "engine", engine)
    migrations.add_membership_columns()
    migrations.add_membership_columns()  # a second run changes nothing

    assert "tier_name" in {col["name"] for col in inspect(engine).get_columns("kofi_payments")}
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, tier, member_until, banner_motion FROM supporters ORDER BY id")).all()
    assert rows[0][1] is None and str(rows[0][2]).startswith("2026-11-20") and not rows[0][3]
    assert rows[1][2] is None and not rows[1][3]
