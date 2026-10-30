"""Trending pages (/trending) and the trending badge on title pages."""
from datetime import datetime, timedelta

from app import models, trending
from app.editorial_collections import EDITOR_EMAIL, EDITOR_USERNAME

NOW = datetime(2026, 10, 30, 12, 0)


def person(db, name, **extra):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True,
                       is_active=extra.pop("active", True), **extra)
    db.add(user)
    db.flush()
    return user


def add(db, user, title, year=2024, days_ago=1, model=models.Movie, **extra):
    if model is not models.VideoGame:
        extra["year"] = year
    item = model(user_id=user.id, title=title, added_at=NOW - timedelta(days=days_ago), **extra)
    db.add(item)
    db.flush()
    return item


def journal(db, user, item, action, days_ago=1, rating=None, category="movies", source="manual"):
    db.add(models.ActivityEntry(user_id=user.id, category=category, item_id=item.id if item else None,
                                title=item.title if item else "Loose Entry", action=action, rating=rating,
                                source=source, occurred_at=NOW - timedelta(days=days_ago)))
    db.flush()


def crowd(db, prefix, count):
    return [person(db, f"{prefix}{index}") for index in range(count)]


def test_points_rank_titles_and_one_member_is_never_named(db_session):
    for user in crowd(db_session, "a", 3):
        item = add(db_session, user, "Busy Film")
        journal(db_session, user, item, "completed", rating=8)
    for user in crowd(db_session, "b", 4):
        add(db_session, user, "Added Only")
    loner = person(db_session, "solo")
    add(db_session, loner, "Solo Pick")
    db_session.commit()
    week = trending.build(db_session, NOW)["week"]
    chart = week["kinds"]["movie"]["chart"]
    assert [e["title"] for e in chart] == ["Busy Film", "Added Only"]  # 3 x (1 + 2) beats 4 x 1.
    top = chart[0]
    assert (top["members"], top["added"], top["finished"], top["rated"], top["average"]) == (3, 3, 3, 3, 8.0)
    assert top["url"] == "/titles/movie/busy-film-2024" and top["movement"] == "new"
    assert week["kinds"]["movie"]["finished"][0]["title"] == "Busy Film"
    assert week["rated"][0]["title"] == "Busy Film"
    assert "Solo Pick" not in str(week)


def test_private_inactive_editor_and_imported_activity_never_count(db_session):
    users = crowd(db_session, "p", 2)
    for user in users:
        add(db_session, user, "Shared Film")
    hidden = person(db_session, "hidden", movies_private=True)
    gone = person(db_session, "gone", active=False)
    editor = models.User(username=EDITOR_USERNAME, email=EDITOR_EMAIL, hashed_password="x", is_verified=True, is_active=True)
    db_session.add(editor)
    db_session.flush()
    for user in (hidden, gone, editor):
        add(db_session, user, "Shared Film")
    # Two members whose only activity on this title came from an import.
    for user in crowd(db_session, "i", 2):
        journal(db_session, user, add(db_session, user, "Imported Film", days_ago=200), "completed", source="import")
    db_session.commit()
    chart = trending.build(db_session, NOW)["week"]["kinds"]["movie"]["chart"]
    assert [(e["title"], e["members"]) for e in chart] == [("Shared Film", 2)]


def test_bulk_adds_are_scaled_down(db_session):
    importer, other = person(db_session, "bulk"), person(db_session, "other")
    for number in range(60):
        add(db_session, importer, f"Batch {number}")
    add(db_session, other, "Batch 0")
    fans = crowd(db_session, "f", 2)
    for user in fans:
        add(db_session, user, "Real Favorite")
    db_session.commit()
    chart = trending.build(db_session, NOW)["week"]["kinds"]["movie"]["chart"]
    assert chart[0]["title"] == "Real Favorite"
    batch = next(e for e in chart if e["title"] == "Batch 0")
    assert batch["score"] < chart[0]["score"]


def test_windows_and_movement_against_the_period_before(db_session):
    early = crowd(db_session, "e", 5)
    for user in early:
        add(db_session, user, "Old News", days_ago=10)  # Last week, not this one.
    for user in early[:2]:
        add(db_session, user, "Old News", year=2024, days_ago=2)
    for user in crowd(db_session, "n", 3):
        add(db_session, user, "Fresh Hit", days_ago=2)
    for user in crowd(db_session, "c", 2):
        add(db_session, user, "Climber", days_ago=12)
    for user in crowd(db_session, "d", 4):
        add(db_session, user, "Climber", days_ago=3)
    db_session.commit()
    built = trending.build(db_session, NOW)
    week = {e["title"]: e for e in built["week"]["kinds"]["movie"]["chart"]}
    assert week["Climber"]["rank"] == 1 and week["Climber"]["movement"] == "up" and week["Climber"]["change"] == 1
    assert week["Fresh Hit"]["movement"] == "new"
    assert week["Old News"]["movement"] == "down"
    month = {e["title"]: e for e in built["month"]["kinds"]["movie"]["chart"]}
    assert month["Climber"]["members"] == 6 and month["Old News"]["members"] == 5


def test_hand_typed_journal_entries_join_their_title(db_session):
    users = crowd(db_session, "h", 3)
    item = add(db_session, users[0], "Typed Film", year=2020)
    journal(db_session, users[1], item, "started")  # users[0]'s row id, but users[1]'s journal.
    db_session.add(models.ActivityEntry(user_id=users[2].id, category="movies", item_id=None, title="Typed Film",
                                        action="completed", occurred_at=NOW - timedelta(days=1)))
    db_session.commit()
    entry = trending.build(db_session, NOW)["week"]["kinds"]["movie"]["chart"][0]
    assert (entry["title"], entry["year"], entry["members"], entry["active"], entry["finished"]) == ("Typed Film", 2020, 3, 1, 1)


def test_other_formats_and_overall_mix(db_session):
    for user in crowd(db_session, "g", 3):
        add(db_session, user, "Space Game", model=models.VideoGame, release_date=datetime(2025, 3, 1))
    for user in crowd(db_session, "m", 2):
        add(db_session, user, "Quiet Film")
    db_session.commit()
    week = trending.build(db_session, NOW)["week"]
    assert week["kinds"]["game"]["chart"][0]["url"] == "/titles/game/space-game-2025"
    assert [e["kind"] for e in week["overall"]] == ["game", "movie"]
    assert set(week["leaders"]) == {"game", "movie"}
    assert not week["indexable"]


def test_writeup_reads_from_the_numbers(db_session):
    for user in crowd(db_session, "w", 4):
        item = add(db_session, user, "Lead Film")
        journal(db_session, user, item, "completed", rating=9)
    for user in crowd(db_session, "x", 2):
        add(db_session, user, "Second Film")
    db_session.commit()
    week = trending.build(db_session, NOW)["week"]
    text = " ".join(trending.paragraphs(week, "movie"))
    assert "Lead Film tops the movie chart this week, with activity from 4 members: 4 added it and 4 watched it." in text
    assert "Second Film is close behind with 2 members." in text
    assert "rated it 9.0 out of 10 on average" in text
    assert "Across movies, 6 members added 6 movies and logged 4 finishes this week." in text
    assert trending.paragraphs(week, "book") == []


def test_trending_pages_render_and_stay_out_of_search_while_thin(client, db_session):
    for user in crowd(db_session, "r", 3):
        add(db_session, user, "Page Film", director="Some Director")
    db_session.commit()
    response = client.get("/trending")
    assert response.status_code == 200
    html = response.text
    assert "Trending on OmniTrackr this week" in html
    assert 'href="/titles/movie/page-film-2024"' in html and "3 members" in html
    assert "How trending works" in html and "Create a free account" in html
    assert 'href="/trending" aria-current="page"' in html  # The titles view switch.
    assert response.headers["X-Robots-Tag"] == "noindex, follow"
    assert '"@type": "ItemList"' in html or '"@type":"ItemList"' in html
    kind_page = client.get("/trending/movie")
    assert kind_page.status_code == 200 and "Trending movies this week" in kind_page.text
    month = client.get("/trending/movie/month")
    assert month.status_code == 200 and "Trending movies this month" in month.text
    assert client.get("/trending/month").status_code == 200
    assert client.get("/trending/comic").status_code == 404
    empty = client.get("/trending/book")
    assert "Nothing is trending this week yet" in empty.text and 'href="/trending/book/month"' in empty.text


def test_trending_pages_are_indexed_and_in_sitemap_with_enough_titles(client, db_session, monkeypatch):
    real_now = datetime.utcnow()
    for number in range(trending.INDEX_MIN_OVERALL):
        for user in crowd(db_session, f"s{number}-", 2):
            item = models.Movie(user_id=user.id, title=f"Film {number}", year=2000 + number,
                                added_at=real_now - timedelta(days=1))
            db_session.add(item)
            db_session.flush()
            db_session.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=item.id, title=item.title,
                                                action="completed", occurred_at=real_now - timedelta(hours=5)))
    db_session.commit()
    response = client.get("/trending")
    assert "X-Robots-Tag" not in response.headers
    assert '<meta name="robots" content="index, follow">' in response.text
    sitemap = client.get("/sitemap.xml").text
    assert "/trending</loc>" in sitemap and "/trending/movie</loc>" in sitemap
    assert "/trending/book</loc>" not in sitemap


def test_title_page_shows_its_trending_place(client, db_session):
    for user in crowd(db_session, "t", 3):
        db_session.add(models.Movie(user_id=user.id, title="Badge Film", year=2023, added_at=datetime.utcnow()))
    db_session.commit()
    html = client.get("/titles/movie/badge-film-2023").text
    assert 'href="/trending/movie#rank-1"' in html and "trending movie this week" in html


def test_site_map_and_footer_link_to_trending(client):
    assert 'href="/trending"' in client.get("/site-map").text
    footer = client.get("/about").text
    assert 'href="/trending">Trending this week</a>' in footer
