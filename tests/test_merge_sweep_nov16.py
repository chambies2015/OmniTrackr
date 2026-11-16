"""Sweep of the Nov 15 2026 merges (#219 What's new card, #220 title page chapters, #221 fixes)."""
from datetime import datetime, timedelta

from app import episode_calendar, friend_feed, home_today, models, title_metadata
from app.routers import titles
from tests.test_title_pages import SAMPLE, add_movie, member, seed_metadata

NOW = datetime(2026, 11, 15, 18, 0)


def _friends(db, a, b):
    low, high = sorted([a.id, b.id])
    db.add(models.Friendship(user1_id=low, user2_id=high))
    db.flush()


def test_home_card_reads_the_members_shows_once(db_session, monkeypatch):
    me = member(db_session, "maya")
    db_session.add(models.TVShow(user_id=me.id, title="Severance", year=2022, watched=False))
    db_session.commit()
    calls = []
    real = episode_calendar.member_shows
    monkeypatch.setattr(episode_calendar, "member_shows", lambda db, user_id: calls.append(user_id) or real(db, user_id))

    data = home_today.build(db_session, me, now=NOW)
    assert calls == [me.id]
    # The schedule was never fetched, so the stale check still asks for it.
    assert data["stale_shows"] == 1


def test_stale_check_without_a_known_list_still_reads_it(db_session):
    me = member(db_session, "maya")
    db_session.add(models.Anime(user_id=me.id, title="Frieren", year=2023, watched=False))
    db_session.commit()
    assert episode_calendar._stale_shows(db_session, [me.id]) == [("anime", "Frieren", 2023)]
    assert episode_calendar._stale_shows(db_session, [me.id], {me.id: []}) == []


def test_friend_count_covers_the_whole_feed_and_only_four_cards_are_built(db_session):
    me = member(db_session, "maya")
    for index in range(6):
        friend = member(db_session, f"friend{index}")
        _friends(db_session, me, friend)
        for number in range(5):
            add_movie(db_session, friend, title=f"Film {index}-{number}", year=2020, watched=True, rating=8,
                      added_at=NOW - timedelta(hours=index * 5 + number + 1))
    db_session.commit()

    part = home_today.build(db_session, me, since=NOW - timedelta(days=2), now=NOW)["friends"]
    assert len(part["items"]) == home_today.FRIEND_LIMIT
    assert part["new"] == 30  # was capped at 20 when only the first page was counted
    assert part["friends"] == 6


def test_friends_feed_page_shape_is_unchanged_without_a_count(db_session):
    me = member(db_session, "maya")
    friend = member(db_session, "jordan")
    _friends(db_session, me, friend)
    add_movie(db_session, friend, title="Heat", year=1995, watched=True, rating=9, added_at=NOW - timedelta(hours=2))
    db_session.commit()
    data = friend_feed.page(db_session, me.id, now=NOW)
    assert "since_count" not in data and len(data["items"]) == 1
    assert friend_feed.page(db_session, me.id, now=NOW, count_since=NOW - timedelta(hours=1))["since_count"] == 0


class _Group:
    def __init__(self, kind):
        self.kind, self.title, self.year, self.path = kind, "Test", 2014, f"/titles/{kind}/test-2014"


def test_a_pair_of_directors_gets_two_cards_not_three():
    metadata = {"facts": [{"label": "Director", "value": "Phil Lord, Christopher Miller"},
                          {"label": "Starring", "value": "Chris Pratt, Will Arnett, Elizabeth Banks"}]}
    crew = titles._crew(_Group("movie"), {"creator": "Phil Lord, Christopher Miller"}, metadata)
    names = [name for name, _ in crew]
    assert names == ["Phil Lord", "Christopher Miller", "Chris Pratt", "Will Arnett", "Elizabeth Banks"]
    # Without a Director fact the member-typed pair is still split.
    crew = titles._crew(_Group("movie"), {"creator": "Phil Lord, Christopher Miller"}, {"facts": metadata["facts"][1:]})
    assert [name for name, _ in crew][:2] == ["Phil Lord", "Christopher Miller"]


def test_band_names_keep_their_commas_and_placeholders_get_no_card():
    assert titles._crew(_Group("album"), {"creator": "Earth, Wind & Fire"}, {}) == [("Earth, Wind & Fire", ["Artist"])]
    assert titles._crew(_Group("movie"), {"creator": "Unknown"}, {}) == []


def test_title_page_links_each_director_card(client, db_session):
    data = {**SAMPLE, "facts": [{"label": "Starring", "value": "Matthew McConaughey, Anne Hathaway, Jessica Chastain"}]}
    for index in range(2):
        add_movie(db_session, member(db_session, f"fan{index}"), director="Jonathan Nolan, Christopher Nolan",
                  rating=9, watched=True)
    db_session.commit()
    seed_metadata(db_session, data)
    html = client.get("/titles/movie/interstellar-2014").text
    cast = html.split('class="title-cast', 1)[1].split("</ul>", 1)[0]
    assert "<strong>Jonathan Nolan</strong>" in cast and "<strong>Christopher Nolan</strong>" in cast
    assert "Jonathan Nolan, Christopher Nolan</strong>" not in cast
