"""Title page refresh: member verdict, at-a-glance sidebar, on-this-page tabs and "More from"."""
from datetime import datetime, timedelta

from app import title_pages
from tests.test_title_pages import ESSAY, add_movie, member, seed_metadata


def seed_interstellar(db, count=6, recent=0):
    users = []
    for index in range(count):
        user = member(db, f"fan{index}")
        added = datetime.utcnow() - timedelta(days=5 if index < recent else 200)
        add_movie(db, user, rating=9.0 if index % 2 else 8.0, watched=index < count - 1, added_at=added,
                  review=ESSAY if index == 0 else None, review_public=index == 0)
        users.append(user)
    db.commit()
    return users


def test_verdict_and_glance_summarize_member_data(client, db_session):
    seed_interstellar(db_session, count=6, recent=3)
    seed_metadata(db_session)
    html = client.get("/titles/movie/interstellar-2014").text
    assert "The member verdict" in html
    assert "Members rate Interstellar 8.5/10 on average across 6 ratings, and 100% of them gave it 8 or more." in html
    assert "5 of the 6 members tracking it have watched it (83%); the other 1 has it on their list." in html
    assert "3 members added it to their library in the last 30 days." in html
    assert 'aria-labelledby="glance-title"' in html and "Member score" in html and "169 min" in html
    assert "Start your free library" in html
    assert 'class="title-tabs"' in html and 'href="#community-title"' in html and 'href="#about-title"' in html


def test_recent_adds_need_two_members(db_session):
    seed_interstellar(db_session, count=4, recent=1)
    summary = title_pages.summarize(db_session, title_pages.find(db_session, "movie", "interstellar-2014"))
    assert summary["recent_members"] == 0


def test_small_pages_skip_the_verdict(client, db_session):
    user = member(db_session, "solo")
    add_movie(db_session, user, review=ESSAY, review_public=True, rating=9, watched=True)
    db_session.commit()
    html = client.get("/titles/movie/interstellar-2014").text
    assert "The member verdict" not in html
    assert "have watched it (" not in html


def test_more_from_creator_lists_other_titles_but_not_private_ones(client, db_session):
    users = seed_interstellar(db_session, count=3)
    add_movie(db_session, users[0], title="Inception", year=2010)
    add_movie(db_session, users[1], title="Tenet", year=2020, director=" christopher nolan ")
    hidden = member(db_session, "private_fan")
    hidden.movies_private = True
    add_movie(db_session, hidden, title="Memento", year=2000)
    add_movie(db_session, users[2], title="Arrival", year=2016, director="Denis Villeneuve")
    db_session.commit()
    html = client.get("/titles/movie/interstellar-2014").text
    assert "More from Christopher Nolan" in html
    section = html.split('id="creator-title"', 1)[1].split("</section>", 1)[0]
    assert "/titles/movie/inception-2010" in section and "/titles/movie/tenet-2020" in section
    assert "Memento" not in section and "Arrival" not in section and "interstellar-2014" not in section


def test_signed_in_members_get_a_review_link_instead_of_signup(authenticated_client, db_session):
    seed_interstellar(db_session, count=3)
    html = authenticated_client.get("/titles/movie/interstellar-2014").text
    assert "Rate and review it" in html
    assert "Start your free library" not in html
