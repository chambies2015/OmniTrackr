"""Nov 26 2026 sweep of #342 (finishing Google sign-up outside app browsers) and #343 (Fill in your year)."""
import re
from datetime import datetime
from pathlib import Path

from app import continue_page, models, tier_list, year_fill
from tests.test_app_browser_signup_nov26 import SAFARI
from tests.test_year_fill import NOW, frozen, member, save  # noqa: F401  (frozen is an autouse fixture)

ROOT = Path(__file__).resolve().parents[1]


def befriend(db, one, two):
    low, high = sorted((one.id, two.id))
    db.add(models.Friendship(user1_id=low, user2_id=high))
    db.commit()


def feed_events(db, user):
    return db.query(models.FriendFeedEvent).filter_by(user_id=user.id, kind="finished").all()


# ---------------------------------------------------------------- #343 Fill in your year

def test_dating_a_list_title_to_an_earlier_month_or_before_the_year_is_not_news_for_friends(db_session):
    user = member(db_session)
    friend = member(db_session, "friend")
    befriend(db_session, user, friend)
    march = save(db_session, user, model=models.Book, title="Piranesi", added=datetime(2026, 2, 1))
    long_ago = save(db_session, user, model=models.Book, title="Dune", added=datetime(2026, 2, 1))
    today = save(db_session, user, model=models.Book, title="Circe", added=datetime(2026, 2, 1))
    db_session.commit()

    year_fill.answer(db_session, user, 2026, "books", march.id, "month", 3, now=NOW)
    year_fill.answer(db_session, user, 2026, "books", long_ago.id, "before", now=NOW)
    for row in (march, long_ago):
        db_session.refresh(row)
        assert row.read is True
    # A March finish and one from before 2026 are ticked off without a "finished" card today.
    assert feed_events(db_session, user) == []
    assert year_fill.friend_feed.QUIET_KEY not in db_session.info

    # "This month" is a normal tick, so friends see it like any other.
    year_fill.answer(db_session, user, 2026, "books", today.id, "month", 12, now=NOW)
    assert [event.item_id for event in feed_events(db_session, user)] == [today.id]

    # The quiet switch is only for that one save: a later tick elsewhere is news again.
    other = save(db_session, user, model=models.Book, title="Kindred")
    db_session.commit()
    other.read = True
    db_session.commit()
    assert sorted(event.item_id for event in feed_events(db_session, user)) == sorted([today.id, other.id])


def test_the_member_page_carries_every_total_for_its_script(client, db_session):
    user = member(db_session)
    for index in range(year_fill.DECK_LIMIT + 5):
        save(db_session, user, title=f"Old film {index}", watched=True)
    for index in range(year_fill.OPEN_LIMIT + 3):
        save(db_session, user, model=models.Book, title=f"Book {index}", added=datetime(2026, 2, 1))
    db_session.commit()
    from app import auth
    page = client.get("/year-in-review/2026/fill",
                      headers={"Authorization": f"Bearer {auth.create_user_access_token(user)}"}).text
    root = re.search(r'<section class="yf"[^>]*>', page).group(0)
    # The page shows 40 and 12 cards, but "the rest" answers all of them, so the script needs the full counts.
    assert f'data-undated-total="{year_fill.DECK_LIMIT + 5}"' in root
    assert f'data-open-total="{year_fill.OPEN_LIMIT + 3}"' in root
    assert 'data-finished-total="0"' in root and 'data-filled="0"' in root
    assert page.count('class="yf-card"') == year_fill.DECK_LIMIT + year_fill.OPEN_LIMIT
    assert "year-fill.js?v=20261126-fill-2" in page


# ---------------------------------------------------------------- #342 /continue

def test_signed_in_continue_page_waits_for_add_before_taking_carried_titles(client):
    client.cookies.set("omnitrackr_session", "anything")
    page = client.get("/continue", headers={"user-agent": SAFARI}).text
    assert 'data-continue="member"' in page
    # The list and the Add button are there for continue.js to fill, hidden until a link carries titles.
    assert re.search(r'<button type="button" class="[^"]*continue-add" data-continue-add hidden>', page)
    assert '<div class="continue-list" data-continue-list hidden>' in page
    assert 'href="/" data-continue-open>Open your library</a>' in page
    assert f"/static/continue.js?v={continue_page.JS_VERSION}" in page and continue_page.JS_VERSION != "20261126-continue-1"


def test_carried_covers_come_only_from_the_image_proxy_hosts():
    script = (ROOT / "app" / "static" / "continue.js").read_text()

    def listed(name):
        block = re.search(rf"const {name} = \[(.*?)\];", script, re.S).group(1)
        return tuple(re.findall(r"'([^']+)'", block))

    assert listed("COVER_HOSTS") == tier_list.IMAGE_HOSTS
    assert listed("HTTPS_COVER_HOSTS") == tier_list.HTTPS_IMAGE_HOSTS
