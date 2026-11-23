"""Nov 23 2026 sweep of #318 (switching guides, awards nominees-out state), #319 (member phone CSS) and
#320 (supporter numbers, founding deadline, end-of-guide Ko-fi note).

Each test here failed before the fix it covers.
"""
import re
from datetime import datetime

from app import awards, awards_data, guide_layout, models, supporters
from tests.test_founding_supporters import member, pay, setup  # noqa: F401  (autouse Ko-fi token fixture)


# ---------------------------------------------------------------- supporter rows and numbers

def test_two_waiting_payments_for_one_member_link_into_one_numbered_row(client, db_session):
    # Two coffees bought before the account existed. Linking both in one go used to make two supporter
    # rows for the member (the session doesn't flush between them) and fail on the unique user_id,
    # so the payments never linked and email verification quietly rolled back every time.
    pay(client, "early-1", "cara@example.com")
    pay(client, "early-2", "cara@example.com")
    cara = member(db_session, "cara")
    assert supporters.link_pending_by_email(db_session, cara) == 2
    db_session.expire_all()
    rows = db_session.query(models.Supporter).filter(models.Supporter.user_id == cara.id).all()
    assert len(rows) == 1 and rows[0].number == 1
    assert supporters.months_supported(db_session, cara.id) == 2


def test_next_number_counts_rows_this_session_has_not_saved_yet(db_session):
    ana, ben = member(db_session, "ana"), member(db_session, "ben")
    db_session.add(models.Supporter(user_id=ana.id, since=datetime.utcnow(), active_until=datetime.utcnow(), number=1))
    assert supporters.next_number(db_session) == 2
    db_session.add(models.Supporter(user_id=ben.id, since=datetime.utcnow(), active_until=datetime.utcnow(),
                                    number=supporters.next_number(db_session)))
    db_session.commit()
    assert sorted(row.number for row in db_session.query(models.Supporter)) == [1, 2]


class _FakeBind:
    class dialect:
        name = "postgresql"


class _FakeSession:
    def __init__(self):
        self.sql = []

    def get_bind(self):
        return _FakeBind()

    def execute(self, statement, params=None):
        self.sql.append((str(statement), params))


def test_new_supporter_rows_take_one_lock_on_postgres():
    # Two payments landing together read the same top number (both members became #1) or both made a
    # row for the same member. On Postgres each grant now waits for the one before it to commit.
    fake = _FakeSession()
    supporters._lock_grants(fake)
    assert fake.sql == [("SELECT pg_advisory_xact_lock(:key)", {"key": supporters.GRANT_LOCK_KEY})]


def test_sqlite_grants_skip_the_lock(db_session):
    supporters._lock_grants(db_session)  # no pg_advisory_xact_lock on SQLite; must not raise


# ---------------------------------------------------------------- the founding deadline

def test_founding_lasts_until_december_31_is_over_everywhere():
    # The pages say founding supporter closes on December 31. At 7 p.m. in New York it's already
    # January 1 in UTC, so a coffee bought then used to miss out.
    evening_new_york = datetime(2027, 1, 1, 0, 30)
    assert supporters.founding_open(evening_new_york)
    assert supporters.is_founding(models.Supporter(since=evening_new_york))
    assert supporters.is_founding(models.Supporter(since=datetime(2027, 1, 1, 11, 59)))
    assert not supporters.is_founding(models.Supporter(since=datetime(2027, 1, 1, 12, 0)))
    assert not supporters.founding_open(datetime(2027, 1, 1, 12, 0))
    # The countdown itself still ends with December 31 in UTC; only the cutoff waits.
    assert supporters.founding_deadline(evening_new_york) is None


def test_last_day_line_does_not_say_today():
    # At 8 a.m. UTC on December 31 it's still December 30 on the US west coast.
    assert supporters.founding_deadline(datetime(2026, 12, 31, 8)) == (
        "December 31 is the last day to become a founding supporter.")


def test_late_december_31_payment_in_the_americas_gets_founding(client, db_session, monkeypatch):
    late = datetime(2027, 1, 1, 3, 0)  # 7 p.m. December 31 in Los Angeles
    monkeypatch.setattr(supporters, "_now", lambda: late)
    dee = member(db_session, "dee")
    pay(client, "nye-1", "dee@example.com")
    db_session.expire_all()
    assert supporters.is_founding(supporters.get_supporter(db_session, dee.id))


# ---------------------------------------------------------------- the end-of-guide note

def test_guide_note_matches_how_the_about_page_says_guides_are_made(client):
    note = guide_layout._support_note()
    # The About page says drafts are written with AI tools and the owner reviews every guide.
    assert "One person writes" not in note
    assert "run by one person, who checks every guide before it goes up" in note
    about = client.get("/about").text
    assert "Drafts are written with AI writing tools" in about
    assert "Every guide is reviewed by the site owner" in about


# ---------------------------------------------------------------- awards pages after nominees day

def test_game_awards_intro_and_description_stop_looking_ahead_once_nominees_are_out(client, monkeypatch):
    monkeypatch.setattr(awards, "_now", lambda: datetime(2026, 11, 23, 3))
    html = client.get("/awards/the-game-awards-2026").text
    assert "When they land, this page becomes a ballot" not in html
    assert "The nominees were revealed on Tuesday, November 17, and this page becomes a ballot" in html
    description = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
    assert "and the nominees are out" in description and "When the nominees are due" not in description
    assert "When the nominees are due" not in html  # JSON-LD Article description too


def test_awards_intro_is_unchanged_on_nominees_day_itself(client, monkeypatch):
    monkeypatch.setattr(awards, "_now", lambda: datetime(2026, 11, 17, 15))
    html = client.get("/awards/the-game-awards-2026").text
    assert "When they land, this page becomes a ballot" in html


def test_pending_words_keep_each_show_s_first_sentence():
    for slug, words in awards.PENDING_WORDS.items():
        show = awards_data.SHOWS[slug]
        assert words["lead"].split(". ")[0] == show["lead"].split(". ")[0], slug
        assert set(words) == {"lead", "description"}
