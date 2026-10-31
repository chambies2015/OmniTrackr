"""Member charts (/titles/<kind>) and the chart signals on title pages."""
from app import models, title_charts, title_pages
from app.editorial_collections import EDITOR_EMAIL, EDITOR_USERNAME
from tests.test_title_pages import LONG_REVIEW, add_movie, member


def _rate(db, title, year, ratings, prefix):
    users = []
    for index, rating in enumerate(ratings):
        user = member(db, f"{prefix}{index}")
        add_movie(db, user, title=title, year=year, rating=rating, watched=True)
        users.append(user)
    return users


def test_weighted_ranking_needs_enough_ratings(db_session):
    _rate(db_session, "Few Perfect", 2001, [10, 10, 10], "f")
    _rate(db_session, "Many Great", 2002, [9.5] * 30, "m")
    _rate(db_session, "Only Two", 2003, [10, 10], "t")
    _rate(db_session, "Weak", 2004, [4] * 10, "w")
    db_session.commit()
    data = title_charts.build(db_session, "movie")
    titles = [entry["title"] for entry in data["ranked"]]
    assert titles == ["Many Great", "Few Perfect", "Weak"]  # Two ratings don't chart; thirty 9.5s beat three 10s.
    top = data["ranked"][0]
    assert (top["rank"], top["rated"], top["members"], top["finished"], top["average"]) == (1, 30, 30, 30, 9.5)
    assert top["url"] == "/titles/movie/many-great-2002"
    assert not data["indexable"]
    assert "_ids" not in top and "_sum" not in top


def test_one_rating_per_member_and_privacy(db_session):
    users = _rate(db_session, "Arrival", 2016, [8, 8, 8], "a")
    add_movie(db_session, users[0], title="Arrival", year=2016, rating=2)  # A second entry: latest counts.
    private = member(db_session, "private")
    private.movies_private = True
    add_movie(db_session, private, title="Arrival", year=2016, rating=1)
    gone = member(db_session, "gone", active=False)
    add_movie(db_session, gone, title="Arrival", year=2016, rating=1)
    editor = models.User(username=EDITOR_USERNAME, email=EDITOR_EMAIL, hashed_password="x", is_verified=True, is_active=True)
    db_session.add(editor)
    db_session.flush()
    add_movie(db_session, editor, title="Arrival", year=2016, rating=1)
    db_session.commit()
    entry = title_charts.build(db_session, "movie")["ranked"][0]
    assert (entry["rated"], entry["members"], entry["average"]) == (3, 3, 6.0)


def test_chart_page_lists_ranks_quotes_and_stays_out_of_search_while_thin(client, db_session):
    users = _rate(db_session, "Interstellar", 2014, [9, 9, 8], "i")
    users[0].movies_private = False
    db_session.query(models.Movie).filter_by(user_id=users[0].id).update({"review": LONG_REVIEW, "review_public": True})
    db_session.commit()
    response = client.get("/titles/movie")
    assert response.status_code == 200
    html = response.text
    assert "The highest-rated movies on OmniTrackr" in html
    assert 'id="rank-1"' in html and 'href="/titles/movie/interstellar-2014"' in html
    assert "8.7" in html and "3 member ratings" in html
    assert "Interstellar works because the science" in html  # Quote from the public review.
    assert "How this chart works" in html and "Create a free account" in html
    assert response.headers["X-Robots-Tag"] == "noindex, follow"
    assert '"@type": "ItemList"' in html or '"@type":"ItemList"' in html
    assert client.get("/titles/comic").status_code == 404


def test_chart_page_is_indexed_and_in_sitemap_with_enough_titles(client, db_session):
    for number in range(title_charts.CHART_INDEX_MIN):
        _rate(db_session, f"Film {number}", 2000 + number, [7, 8, 9], f"u{number}-")
    db_session.commit()
    response = client.get("/titles/movie")
    assert "X-Robots-Tag" not in response.headers
    assert '<meta name="robots" content="index, follow">' in response.text
    assert "/titles/movie</loc>" in client.get("/sitemap.xml").text
    assert "/titles/book</loc>" not in client.get("/sitemap.xml").text


def test_empty_chart_explains_how_titles_join(client, db_session):
    response = client.get("/titles/book")
    assert response.status_code == 200
    assert "Not enough ratings to chart yet" in response.text
    assert response.headers["X-Robots-Tag"] == "noindex, follow"


def test_title_page_shows_rank_and_rating_spread(client, db_session):
    _rate(db_session, "Interstellar", 2014, [9.5, 9, 8.2, 6, 3], "s")
    db_session.commit()
    html = client.get("/titles/movie/interstellar-2014").text
    assert 'href="/titles/movie#rank-1"' in html and "highest-rated movie on OmniTrackr" in html
    assert "How members rate Interstellar" in html
    assert "From 5 member ratings out of 10" in html
    assert 'href="/titles/movie">Movies</a>' in html  # Breadcrumb points at the chart.


def test_spread_waits_for_five_ratings(client, db_session):
    _rate(db_session, "Interstellar", 2014, [9, 8, 7, 6], "s")
    db_session.commit()
    assert "How members rate" not in client.get("/titles/movie/interstellar-2014").text
    spread = title_pages.rating_spread([9.5, 9, 8.2, 6, 3])
    assert [band["count"] for band in spread] == [2, 1, 0, 1, 1]
    assert sum(band["percent"] for band in spread) == 100


def test_titles_directory_links_each_chart(client, db_session):
    add_movie(db_session, member(db_session, "a"))
    add_movie(db_session, member(db_session, "b"))
    db_session.commit()
    assert 'href="/titles/movie">Highest-rated movies' in client.get("/titles").text
