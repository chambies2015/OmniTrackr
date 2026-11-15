"""Site-wide speed pass (Nov 15 2026): one stylesheet for the dashboard, fewer queries for the
sitemap, people directory, Year in Review and stats cards, and an index for "added this week" reads."""
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import event, inspect as sa_inspect

from app import dashboard_assets, models, people_pages, title_pages, user_columns, year_in_review
from app.auth import AUTH_COOKIE_NAME
from tests.conftest import engine
from tests.test_people_pages import REVIEW, member, movie


@contextmanager
def counting():
    seen = []

    def count(*_args, **_kwargs):
        seen.append(1)

    event.listen(engine, "before_cursor_execute", count)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", count)


# ---------------------------------------------------------------- one dashboard stylesheet

def test_signed_in_dashboard_links_one_bundled_stylesheet(client):
    client.cookies.set(AUTH_COOKIE_NAME, "x")
    page = client.get("/").text
    css, version, hrefs = dashboard_assets.stylesheet_bundle()
    links = [line for line in page.splitlines() if 'rel="stylesheet"' in line]
    assert links == [f'  <link rel="stylesheet" href="/dashboard.css?v={version}">']
    assert len(hrefs) >= 30
    assert dashboard_assets.page_stylesheets(page) == list(hrefs)
    # The preload for styles.css would fetch a file the page no longer uses.
    assert 'rel="preload" href="./styles.css' not in page


def test_bundle_keeps_every_stylesheet_in_template_order(client):
    css, version, hrefs = dashboard_assets.stylesheet_bundle()
    template = dashboard_assets.TEMPLATE.read_text(encoding="utf-8")
    assert list(hrefs) == [m.group(1) for m in dashboard_assets.stylesheet_links(template)]
    positions = [css.index(f"/* {dashboard_assets._served_path(href)} */\n") for href in hrefs]
    assert positions == sorted(positions)
    for href in hrefs:
        source = dashboard_assets._stylesheet_file(href).read_text(encoding="utf-8")
        assert dashboard_assets._absolute_urls(source, dashboard_assets._served_path(href)) in css
    response = client.get(f"/dashboard.css?v={version}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.text == css
    assert client.get("/dashboard.css?v=old").headers["cache-control"] == "public, max-age=86400"


def test_no_stylesheet_can_swallow_the_next_one_in_the_bundle():
    """Joined files share one parser: an open comment, string or block would run into the next file."""
    import re
    for href in dashboard_assets.stylesheet_bundle()[2]:
        text = dashboard_assets._stylesheet_file(href).read_text(encoding="utf-8")
        stripped = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        assert "/*" not in stripped, href
        stripped = re.sub(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', "", stripped)
        assert stripped.count("{") == stripped.count("}"), href
        assert "@import" not in stripped and "@charset" not in stripped, href


def test_relative_urls_still_point_at_the_same_file():
    css = "a{background:url('./omnitrackr_vortex.png')} b{background:url(img/x.png)} c{background:url(data:image/png;base64,AA)}"
    assert dashboard_assets._absolute_urls(css, "/styles.css") == (
        "a{background:url('/omnitrackr_vortex.png')} b{background:url(/img/x.png)} c{background:url(data:image/png;base64,AA)}")
    assert "url(/static/img/x.png)" in dashboard_assets._absolute_urls("b{background:url(img/x.png)}", "/static/x.css")


def test_a_template_that_no_longer_matches_is_left_alone():
    html = '<head>\n  <link rel="stylesheet" href="/static/only.css?v=1">\n</head>'
    assert dashboard_assets.bundle_stylesheets(html) == html


def test_guests_still_get_their_own_stylesheets(client):
    page = client.get("/").text
    assert "/dashboard.css" not in page
    assert '<link rel="stylesheet"' in page


def test_service_worker_keeps_the_bundle_offline():
    sw = (dashboard_assets.STATIC_DIR / "sw.js").read_text(encoding="utf-8")
    assert "'/dashboard.css'" in sw


# ---------------------------------------------------------------- people pages and sitemap

def _director_films(db, users, numbers):
    for number in numbers:
        for index, user in enumerate(users):
            movie(db, user, f"Film {number}", 1990 + number, director="Ava Example", rating=8.0,
                  review=REVIEW if index == 0 else None, review_public=index == 0)
    db.commit()


def _director_library(db, titles):
    users = [member(db, f"fan{i}") for i in range(3)]
    _director_films(db, users, range(titles))
    return users


def test_a_person_page_reads_reviews_in_a_fixed_number_of_queries(db_session):
    """It used to ask for each title's review states and reviewers separately (two queries a title)."""
    users = _director_library(db_session, 4)
    with counting() as few:
        assert people_pages.build(db_session, people_pages.PERSON, "ava-example") is not None
    _director_films(db_session, users, range(4, 16))
    with counting() as many:
        page = people_pages.build(db_session, people_pages.PERSON, "ava-example")
    assert page is not None and len(page.works) == 16
    assert len(many) <= len(few) + 2


def test_review_context_gives_the_same_summary(db_session):
    _director_library(db_session, 3)
    groups = list(title_pages.find_many(db_session, "movie", ["film-0-1990", "film-1-1991", "film-2-1992"]).values())
    context = title_pages.review_context(db_session, groups)
    editors = title_pages.editor_id_set(db_session)
    for group in groups:
        plain = title_pages.summarize(db_session, group, page_sections=False)
        shared = title_pages.summarize(db_session, group, page_sections=False, editors=editors, review_context=context)
        assert plain == shared
        assert [review["username"] for review in shared["reviews"]] == ["fan0"]


def test_review_context_respects_suspended_reviews(db_session):
    from app.routers.reviews import _review_content_hash
    _director_library(db_session, 1)
    row = db_session.query(models.Movie).filter(models.Movie.review_public == True).first()  # noqa: E712
    db_session.add(models.PublicReviewState(user_id=row.user_id, category="movie", item_id=row.id,
                                            suspended_at=datetime.utcnow(),
                                            content_hash=_review_content_hash("movie", row.id, row.review)))
    db_session.commit()
    group = title_pages.find(db_session, "movie", "film-0-1990")
    context = title_pages.review_context(db_session, [group])
    assert title_pages.summarize(db_session, group, page_sections=False, review_context=context)["reviews"] == []


# ---------------------------------------------------------------- Year in Review friends

def test_year_in_review_friends_section_does_not_query_per_friend(db_session):
    from app.crud import friends as friend_crud
    me = member(db_session, "me")
    db_session.commit()
    now = datetime(2026, 6, 1)

    def befriend(count):
        for index in range(count):
            friend = member(db_session, f"pal{db_session.query(models.User).count()}")
            low, high = sorted([me.id, friend.id])
            db_session.add(models.Friendship(user1_id=low, user2_id=high))
            db_session.add(models.ActivityEntry(user_id=friend.id, category="movies", action="completed",
                                                title="Arrival", occurred_at=now))
        db_session.commit()

    db_session.add(models.ActivityEntry(user_id=me.id, category="movies", action="completed", title="Arrival",
                                        occurred_at=now))
    befriend(2)
    _, finished = year_in_review._finishes(db_session, me.id, 2026, list(year_in_review.CATEGORIES))
    with counting() as two:
        result = year_in_review._friends(db_session, me, 2026, finished, list(year_in_review.CATEGORIES))
    assert result["checked"] == 2 and len(result["matches"]) == 2
    befriend(6)
    with counting() as eight:
        result = year_in_review._friends(db_session, me, 2026, finished, list(year_in_review.CATEGORIES))
    assert result["checked"] == 8 and len(result["matches"]) == min(8, year_in_review.FRIENDS_LIMIT)
    assert len(eight) <= len(two) + 1
    assert len(friend_crud.get_friends(db_session, me.id)) == 8


def test_a_friends_private_shelf_still_stays_out(db_session):
    me, pal = member(db_session, "me"), member(db_session, "pal", movies_private=True)
    low, high = sorted([me.id, pal.id])
    db_session.add(models.Friendship(user1_id=low, user2_id=high))
    for user in (me, pal):
        db_session.add(models.ActivityEntry(user_id=user.id, category="movies", action="completed",
                                            title="Arrival", occurred_at=datetime(2026, 3, 1)))
    db_session.commit()
    _, finished = year_in_review._finishes(db_session, me.id, 2026, list(year_in_review.CATEGORIES))
    result = year_in_review._friends(db_session, me, 2026, finished, list(year_in_review.CATEGORIES))
    assert result["matches"] == []


# ---------------------------------------------------------------- member flags in one query

def test_library_flags_load_together(db_session):
    from app import crud
    user_id = member(db_session, "flags", books_visible=False, anime_private=True).id
    db_session.commit()
    db_session.expunge_all()
    signed_in = crud.get_user_by_id_auth(db_session, user_id)
    with counting() as reads:
        user_columns.ensure_loaded(signed_in, user_columns.VISIBLE + user_columns.PRIVATE)
        flags = [getattr(signed_in, name) for name in user_columns.VISIBLE + user_columns.PRIVATE]
    assert len(reads) == 1
    assert flags.count(False) == 9 and signed_in.books_visible is False and signed_in.anime_private is True
    with counting() as again:
        user_columns.ensure_loaded(signed_in, user_columns.VISIBLE)
    assert again == []


def test_flags_helper_ignores_rows_without_a_session():
    user_columns.ensure_loaded(models.User(username="loose"), user_columns.VISIBLE)
    user_columns.ensure_loaded(None, user_columns.VISIBLE)


def test_stats_home_card_reads_the_visible_flags_once(authenticated_client):
    with counting() as reads:
        assert authenticated_client.get("/statistics/home/").status_code == 200
    assert len(reads) <= 22


# ---------------------------------------------------------------- added_at index

def test_every_library_gets_an_added_at_index(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from app import database, migrations
    test_engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    database.Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr(migrations, "engine", test_engine)
    migrations.run_migrations()
    migrations.run_migrations()  # safe to run again on the next start
    inspector = sa_inspect(test_engine)
    for table in ("movies", "tv_shows", "anime", "video_games", "music", "books", "manga", "podcasts", "audiobooks"):
        indexes = {index["name"]: index["column_names"] for index in inspector.get_indexes(table)}
        assert indexes.get(f"ix_{table}_added_at") == ["added_at"], table
