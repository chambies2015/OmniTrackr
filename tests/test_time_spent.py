"""Time spent estimates, the public profile hours tile and the binge calculator."""
import json
from datetime import date, datetime

from app import auth, binge_calculator, episodes, models, time_spent, title_metadata, title_pages


def _member(db, name="timer", **extra):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, created_at=datetime(2025, 3, 4), **extra)
    db.add(user)
    db.commit()
    return user


def _cache(db, kind, title, year, facts):
    key = title_metadata.cache_key(kind, title_pages.normalize(title), year)
    db.add(models.TitleMetadata(key=key, status="ok", data=json.dumps({"facts": facts}), fetched_at=datetime.utcnow()))
    db.commit()


def _row(result, category):
    return next(row for row in result["categories"] if row["category"] == category)


# ---------------------------------------------------------------- parsing

def test_minutes_parse_the_formats_the_cache_stores():
    assert time_spent.parse_minutes("142 min") == 142
    assert time_spent.parse_minutes("142 min, 150 min") == 142
    assert time_spent.parse_minutes("24 min per ep") == 24
    assert time_spent.parse_minutes("1 hr 30 min") == 90
    assert time_spent.parse_minutes("12 hours") == 720
    assert time_spent.parse_minutes("unknown") is None
    assert time_spent.parse_minutes(None) is None
    assert time_spent.parse_count("352") == 352
    assert time_spent.parse_count("0") is None


# ---------------------------------------------------------------- estimates

def test_finished_titles_use_cached_lengths_and_typical_ones_otherwise(db_session):
    user = _member(db_session)
    db_session.add_all([
        models.Movie(title="Arrival", year=2016, watched=True, user_id=user.id),
        models.Movie(title="Unknown Film", year=2001, watched=True, user_id=user.id),
        models.Movie(title="Not Yet", year=2020, watched=False, user_id=user.id),
        models.VideoGame(title="Hades", played=True, user_id=user.id),
        models.Book(title="Dune", year=1965, read=True, user_id=user.id),
    ])
    db_session.commit()
    _cache(db_session, "movie", "Arrival", 2016, [{"label": "Running time", "value": "116 min"}])
    _cache(db_session, "book", "Dune", 1965, [{"label": "Pages", "value": "400"}])

    result = time_spent.estimate(db_session, user, today=date(2026, 10, 29))
    movies = _row(result, "movies")
    assert movies["minutes"] == 116 + time_spent.MOVIE_MINUTES
    assert movies["titles"] == 2 and movies["typical"] == 1
    assert _row(result, "video-games")["minutes"] == time_spent.GAME_HOURS * 60
    assert _row(result, "books")["minutes"] == round(400 * time_spent.MINUTES_PER_PAGE)
    assert result["titles"] == 4
    assert result["minutes"] == sum(row["minutes"] for row in result["categories"])
    assert result["hours"] == round(result["minutes"] / 60)


def test_unfinished_shows_and_books_count_up_to_the_checkpoint(db_session):
    user = _member(db_session)
    show = models.TVShow(title="Severance", year=2022, seasons=1, episodes=9, watched=False, user_id=user.id)
    book = models.Book(title="Middlemarch", year=1871, read=False, user_id=user.id)
    db_session.add_all([show, book])
    db_session.commit()
    _cache(db_session, "tv", "Severance", 2022, [{"label": "Episode length", "value": "50 min"}])
    db_session.add_all([
        models.ProgressCheckpoint(user_id=user.id, category="tv-shows", item_id=show.id, unit="episode", season=1, position=4),
        models.ProgressCheckpoint(user_id=user.id, category="books", item_id=book.id, unit="page", position=120),
    ])
    db_session.commit()

    result = time_spent.estimate(db_session, user, today=date(2026, 10, 29))
    assert _row(result, "tv-shows")["minutes"] == 4 * 50
    assert _row(result, "books")["minutes"] == round(120 * time_spent.MINUTES_PER_PAGE)
    # Nothing was finished, so nothing counts toward this year.
    assert result["year_minutes"] == 0


def test_finished_shows_use_the_cached_episode_layout(db_session):
    user = _member(db_session)
    db_session.add(models.Anime(title="Frieren", year=2023, watched=True, user_id=user.id))
    db_session.commit()
    key = episodes.layout_key("anime", "Frieren", 2023)
    db_session.add(models.TitleMetadata(key=key, status="ok", data=json.dumps({"seasons": [{"number": 1, "episodes": 28}]}),
                                        fetched_at=datetime.utcnow()))
    db_session.commit()
    _cache(db_session, "anime", "Frieren", 2023, [{"label": "Episode length", "value": "24 min per ep"}])

    row = _row(time_spent.estimate(db_session, user), "anime")
    assert row["minutes"] == 28 * 24 and row["typical"] == 0


def test_this_year_counts_titles_finished_this_year(db_session):
    user = _member(db_session)
    recent = models.Movie(title="Arrival", year=2016, watched=True, user_id=user.id)
    older = models.Movie(title="Heat", year=1995, watched=True, user_id=user.id)
    db_session.add_all([recent, older])
    db_session.commit()
    db_session.add_all([
        models.ActivityEntry(user_id=user.id, category="movies", item_id=recent.id, title="Arrival", action="completed",
                             occurred_at=datetime(2026, 3, 1)),
        models.ActivityEntry(user_id=user.id, category="movies", item_id=older.id, title="Heat", action="completed",
                             occurred_at=datetime(2025, 3, 1)),
    ])
    db_session.commit()

    result = time_spent.estimate(db_session, user, today=date(2026, 10, 29))
    assert result["year_minutes"] == time_spent.MOVIE_MINUTES
    assert result["minutes"] == 2 * time_spent.MOVIE_MINUTES


def test_one_absurd_episode_count_is_capped(db_session):
    user = _member(db_session)
    db_session.add(models.TVShow(title="Typo", year=2020, episodes=4000, watched=True, user_id=user.id))
    db_session.commit()
    assert _row(time_spent.estimate(db_session, user), "tv-shows")["minutes"] <= time_spent.MAX_ITEM_MINUTES


def test_comparison_reads_plainly():
    assert time_spent.comparison(30) == ""
    assert "hours" in time_spent.comparison(5 * 60)
    assert "days without stopping" in time_spent.comparison(100 * 60)
    assert "years" in time_spent.comparison(24 * 60 * 400)


# ---------------------------------------------------------------- API and public profile

def test_time_spent_endpoint_needs_sign_in(client):
    assert client.get("/statistics/time-spent/").status_code == 401


def test_time_spent_endpoint_returns_the_estimate(authenticated_client, db_session):
    user = db_session.query(models.User).filter_by(username="testuser").one()
    db_session.add(models.Movie(title="Arrival", year=2016, watched=True, user_id=user.id))
    db_session.commit()
    response = authenticated_client.get("/statistics/time-spent/")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.json()["minutes"] == time_spent.MOVIE_MINUTES


def _hours_tile(html):
    return "est. hours" in html or "est. hour<" in html


def test_profile_shows_hours_only_from_public_shelves(client, db_session):
    user = _member(db_session, name="hourly", movies_private=True)
    db_session.add_all([
        models.Movie(title="Secret Film", year=2016, watched=True, user_id=user.id),
        models.VideoGame(title="Hades", played=True, user_id=user.id),
        models.PublicProfile(user_id=user.id, enabled=True),
    ])
    db_session.commit()
    assert time_spent.public_hours(db_session, user) == time_spent.GAME_HOURS
    html = client.get("/u/hourly").text
    assert _hours_tile(html)
    assert f"<strong>{time_spent.GAME_HOURS}</strong><span>est. hours" in html


def test_profile_hides_hours_when_statistics_are_private(client, db_session):
    user = _member(db_session, name="quiet", statistics_private=True)
    db_session.add_all([
        models.VideoGame(title="Hades", played=True, user_id=user.id),
        models.PublicProfile(user_id=user.id, enabled=True),
    ])
    db_session.commit()
    assert not _hours_tile(client.get("/u/quiet").text)


def test_profile_hides_hours_when_stats_are_switched_off(client, db_session):
    user = _member(db_session, name="nostats")
    db_session.add_all([
        models.VideoGame(title="Hades", played=True, user_id=user.id),
        models.PublicProfile(user_id=user.id, enabled=True, show_stats=False),
    ])
    db_session.commit()
    assert not _hours_tile(client.get("/u/nostats").text)


# ---------------------------------------------------------------- binge calculator

def test_binge_plan_counts_the_start_day():
    plan = time_spent.binge_plan(2914, 120, date(2026, 11, 1))
    assert plan == {"days": 25, "finish": "2026-11-25", "hours": 48.6}


def test_binge_examples_add_up():
    breaking_bad = binge_calculator.EXAMPLES["breaking-bad"]
    assert binge_calculator.example_minutes(breaking_bad) == 62 * 47
    assert binge_calculator.days_at(62 * 47, 2) == 25
    potter = binge_calculator.EXAMPLES["harry-potter"]
    assert binge_calculator.example_pages(potter) == round(1084000 / binge_calculator.WORDS_PER_PAGE)


def test_binge_calculator_page_is_public_and_indexable(client):
    response = client.get("/binge-calculator")
    assert response.status_code == 200
    html = response.text
    assert '<link rel="canonical" href="https://omnitrackr.xyz/binge-calculator">' in html
    assert 'content="index, follow' in html
    assert "Breaking Bad" in html and "Harry Potter" in html
    assert '"@type": "FAQPage"' in html
    assert "/static/binge-calculator.js" in html and "/static/ad-loader.js" in html
    assert " style=" not in html.split("<main", 1)[1]
    # Worked examples read without scripts.
    assert '<li class="bc-item" id="breaking-bad">' in html and "<dd>25 days</dd>" in html


def test_binge_calculator_skips_ads_for_members(client):
    from app.auth import AUTH_COOKIE_NAME
    client.cookies.set(AUTH_COOKIE_NAME, "signed-in")
    assert "/static/ad-loader.js" not in client.get("/binge-calculator").text


def test_binge_calculator_is_in_the_sitemap_and_ad_paths(client):
    assert "https://omnitrackr.xyz/binge-calculator" in client.get("/sitemap.xml").text
    from pathlib import Path
    loader = (Path(__file__).parents[1] / "app" / "static" / "ad-loader.js").read_text(encoding="utf-8")
    assert r"/^\/binge-calculator$/" in loader


def test_binge_length_reads_the_cache_only(client, db_session):
    _cache(db_session, "tv", "Severance", 2022, [{"label": "Episode length", "value": "50 min"}])
    key = episodes.layout_key("tv-shows", "Severance", 2022)
    db_session.add(models.TitleMetadata(key=key, status="ok", fetched_at=datetime.utcnow(),
                                        data=json.dumps({"seasons": [{"number": 1, "episodes": 9}, {"number": 2, "episodes": 10}]})))
    db_session.commit()
    data = client.get("/api/binge-calculator/length", params={"kind": "tv", "title": "Severance", "year": 2022}).json()
    assert data["episodes"] == 19 and data["minutes"] == 50

    missing = client.get("/api/binge-calculator/length", params={"kind": "book", "title": "Nothing Cached"}).json()
    assert missing["pages"] is None
    assert client.get("/api/binge-calculator/length", params={"kind": "movie", "title": "Arrival"}).status_code == 400


def test_public_hours_are_reused_for_a_few_minutes_but_follow_privacy(db_session, monkeypatch):
    monkeypatch.setenv("TESTING", "false")
    time_spent.clear_public_hours_cache()
    user = _member(db_session, name="cached")
    db_session.add(models.VideoGame(title="Hades", played=True, user_id=user.id))
    db_session.commit()
    calls = []
    real = time_spent.estimate
    monkeypatch.setattr(time_spent, "estimate", lambda *args, **kwargs: calls.append(1) or real(*args, **kwargs))
    try:
        assert time_spent.public_hours(db_session, user) == time_spent.GAME_HOURS
        db_session.add(models.VideoGame(title="Celeste", played=True, user_id=user.id))
        db_session.commit()
        assert time_spent.public_hours(db_session, user) == time_spent.GAME_HOURS  # cached
        assert len(calls) == 1
        user.video_games_private = True
        db_session.commit()
        assert time_spent.public_hours(db_session, user) == 0  # a privacy change is a new key
        clock = time_spent.time.monotonic() + time_spent.PUBLIC_HOURS_SECONDS + 1
        monkeypatch.setattr(time_spent.time, "monotonic", lambda: clock)
        user.video_games_private = False
        db_session.commit()
        assert time_spent.public_hours(db_session, user) == 2 * time_spent.GAME_HOURS  # expired
    finally:
        time_spent.clear_public_hours_cache()
