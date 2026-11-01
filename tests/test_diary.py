"""The diary: month calendar of finishes and revisits, the opt-in public diary, and Letterboxd diary dates."""
from datetime import datetime, timedelta

from app import auth, diary, models
from tests.test_import_formats import LB_DIARY, letterboxd_zip


def owner(db):
    return db.query(models.User).filter(models.User.username == "testuser").one()


def log(db, user, item, action, when, category="movies", note=None):
    entry = models.ActivityEntry(user_id=user.id, category=category, item_id=item.id if item else None,
                                 title=item.title if item else "Gone Film", action=action, note=note,
                                 rating=getattr(item, "rating", None), occurred_at=when)
    db.add(entry)
    db.commit()
    return entry


def movie(db, user, title="Arrival", year=2016, **extra):
    row = models.Movie(user_id=user.id, title=title, director="Someone", year=year, watched=True,
                       poster_url=f"https://img.example/{title.lower()}.jpg", **extra)
    db.add(row)
    db.commit()
    return row


def this_month(day=1, hour=12):
    now = datetime.utcnow()
    return datetime(now.year, now.month, day, hour)


# ---------------------------------------------------------------- the member's diary

def test_month_view_numbers_rewatches_and_leaves_other_moments_out(authenticated_client, db_session):
    user = owner(db_session)
    film = movie(db_session, user, rating=9.0)
    book = models.Book(user_id=user.id, title="Dune", author="Frank Herbert", year=1965, read=True)
    db_session.add(book)
    db_session.commit()
    log(db_session, user, film, "completed", this_month(1) - timedelta(days=5))
    log(db_session, user, film, "revisited", this_month(1), note="Better the second time.")
    log(db_session, user, film, "completed", this_month(1, 18))
    log(db_session, user, book, "completed", this_month(1, 20), category="books")
    log(db_session, user, film, "started", this_month(1, 21))  # Not a diary moment.
    stranger = models.User(username="other", email="o@example.com", hashed_password="x", is_verified=True)
    db_session.add(stranger)
    db_session.commit()
    log(db_session, stranger, movie(db_session, stranger, title="Heat"), "completed", this_month(1))

    response = authenticated_client.get("/activity/diary/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    data = response.json()
    first_day = this_month(1).date().isoformat()
    assert list(data["days"]) == [first_day]
    rows = data["days"][first_day]
    assert [(row["title"], row["visit"], row["visit_label"], row["repeat"]) for row in rows] == [
        ("Arrival", 2, "Rewatch", True), ("Arrival", 3, "3rd watch", True), ("Dune", 1, "Read", False)]
    assert rows[0]["note"] == "Better the second time."
    assert rows[0]["image"] == "https://img.example/arrival.jpg"
    assert rows[0]["item_id"] == film.id
    assert (data["entry_count"], data["finished_count"], data["repeat_count"], data["active_days"]) == (3, 1, 2, 1)
    assert data["previous_month"] is not None and data["next_month"] is None

    older = authenticated_client.get(f"/activity/diary/?month={data['previous_month']}").json()
    assert older["entry_count"] == 1 and older["next_month"] == data["month"]
    assert older["previous_month"] is None


def test_month_view_uses_the_members_local_day(authenticated_client, db_session):
    user = owner(db_session)
    film = movie(db_session, user)
    # Uses last month so the test doesn't depend on today's date: early on the 1st (UTC)
    # New York is still in the previous month, and the 2nd hasn't happened yet.
    last = this_month(1) - timedelta(days=1)
    month = last.strftime("%Y-%m")
    log(db_session, user, film, "completed", datetime(last.year, last.month, 2, 3))  # 03:00 UTC is still the 1st in New York.
    eastern = authenticated_client.get(f"/activity/diary/?month={month}&tz_offset_minutes=300").json()
    assert list(eastern["days"]) == [f"{month}-01"]
    utc = authenticated_client.get(f"/activity/diary/?month={month}").json()
    assert list(utc["days"]) == [f"{month}-02"]


def test_month_view_rejects_bad_months_and_caps_the_future(authenticated_client):
    assert authenticated_client.get("/activity/diary/?month=2026-13").status_code == 422
    assert authenticated_client.get("/activity/diary/?month=soon").status_code == 422
    future = authenticated_client.get("/activity/diary/?month=2999-01").json()
    assert future["month"] == datetime.utcnow().strftime("%Y-%m")
    empty = authenticated_client.get("/activity/diary/").json()
    assert empty["days"] == {} and empty["earliest_month"] is None and empty["previous_month"] is None


def test_diary_needs_an_account(client):
    assert client.get("/activity/diary/").status_code == 401


def test_dashboard_has_the_diary_calendar(authenticated_client):
    page = authenticated_client.get("/").text
    assert 'id="activityDiaryGrid"' in page
    assert 'data-action="activity-diary-older"' in page
    assert 'id="profileShowDiary"' in page


def test_visit_labels_fit_each_kind_of_title():
    entry = models.ActivityEntry(action="completed")
    assert diary.visit_label("books", entry, 1) == "Read"
    assert diary.visit_label("books", entry, 2) == "Reread"
    assert diary.visit_label("video-games", entry, 4) == "4th play"
    assert diary.visit_label("music", entry, 11) == "11th listen"
    assert diary.visit_label("movies", models.ActivityEntry(action="revisited"), 1) == "Rewatch"


# ---------------------------------------------------------------- public diary

def _public_member(db, name="diarist", **extra):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, created_at=datetime(2025, 3, 4), **extra)
    db.add(user)
    db.commit()
    return user


def test_public_diary_is_off_until_switched_on(client, db_session):
    user = _public_member(db_session)
    film = movie(db_session, user, rating=8.0)
    log(db_session, user, film, "completed", datetime(2026, 9, 3, 20), note="Private thought")
    profile = models.PublicProfile(user_id=user.id, enabled=True)
    db_session.add(profile)
    db_session.commit()
    assert "profile-diary" not in client.get("/u/diarist").text

    profile.show_diary = True
    db_session.commit()
    html = client.get("/u/diarist").text
    assert 'id="profile-diary"' in html
    assert "September 2026" in html and 'datetime="2026-09-03"' in html
    assert 'href="/titles/movie/arrival-2016"' in html
    assert "Private thought" not in html


def test_public_diary_marks_rewatches_and_skips_private_or_deleted_titles(client, db_session):
    user = _public_member(db_session, books_private=True)
    film = movie(db_session, user)
    gone = movie(db_session, user, title="Removed")
    book = models.Book(user_id=user.id, title="Hidden Book", author="A", year=2001, read=True)
    db_session.add(book)
    db_session.commit()
    log(db_session, user, film, "completed", datetime(2026, 8, 1, 12))
    log(db_session, user, film, "revisited", datetime(2026, 9, 1, 12))
    log(db_session, user, gone, "completed", datetime(2026, 9, 2, 12))
    log(db_session, user, book, "completed", datetime(2026, 9, 3, 12), category="books")
    db_session.delete(gone)
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True, show_diary=True))
    db_session.commit()
    html = client.get("/u/diarist").text
    assert "↻ Rewatch" in html
    assert "Hidden Book" not in html and "Removed" not in html


def test_profile_settings_toggle_the_diary(authenticated_client):
    settings = authenticated_client.get("/api/profile/settings").json()
    assert settings["show_diary"] is False
    saved = authenticated_client.put("/api/profile/settings", json={"enabled": True, "show_diary": True}).json()
    assert saved["show_diary"] is True
    # Saving other settings leaves the diary choice alone.
    assert authenticated_client.put("/api/profile/settings", json={"bio": "Hi"}).json()["show_diary"] is True


def test_diary_migration_keeps_existing_profiles_unchanged(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    from app import migrations

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE public_profiles (id INTEGER PRIMARY KEY, user_id INTEGER, enabled BOOLEAN)"))
        conn.execute(text("INSERT INTO public_profiles (id, user_id, enabled) VALUES (1, 7, 1)"))
        conn.commit()
    monkeypatch.setattr(migrations, "engine", engine)

    migrations.add_public_diary_column()
    migrations.add_public_diary_column()  # Safe to run on every boot.

    assert "show_diary" in {c["name"] for c in inspect(engine).get_columns("public_profiles")}
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, user_id, enabled, show_diary FROM public_profiles")).one()
    assert tuple(row) == (1, 7, 1, 0)


# ---------------------------------------------------------------- Letterboxd diary dates

def _preview(client, name, content, kind="application/zip"):
    response = client.post("/import-studio/preview/", files={"file": (name, content, kind)}, data={"source": "auto"})
    assert response.status_code == 200, response.text
    return response.json()


def _apply(client, name, content, fingerprint, kind="application/zip"):
    response = client.post("/import-studio/apply/", files={"file": (name, content, kind)},
                           data={"source": "auto", "fingerprint_confirmation": fingerprint})
    assert response.status_code == 200, response.text
    return response.json()


def test_letterboxd_diary_dates_land_in_the_journal(authenticated_client, db_session):
    preview = _preview(authenticated_client, "letterboxd.zip", letterboxd_zip())
    # Two Arrival visits; the deleted folder's diary is ignored.
    assert preview["diary_count"] == 2
    applied = _apply(authenticated_client, "letterboxd.zip", letterboxd_zip(), preview["fingerprint"])
    assert applied["diary_created"] == 2
    arrival = db_session.query(models.Movie).filter(models.Movie.title == "Arrival").one()
    entries = db_session.query(models.ActivityEntry).order_by(models.ActivityEntry.occurred_at).all()
    assert [(e.title, e.action, e.occurred_at, e.item_id, e.source, e.rating) for e in entries] == [
        ("Arrival", "completed", datetime(2024, 1, 1, 12), arrival.id, "import", 6.0),
        ("Arrival", "revisited", datetime(2024, 6, 1, 12), arrival.id, "import", 9.0),
    ]
    month = authenticated_client.get("/activity/diary/?month=2024-06").json()
    assert month["days"]["2024-06-01"][0]["visit_label"] == "Rewatch"

    # Importing the same export again adds nothing to the library or the journal.
    again = _preview(authenticated_client, "letterboxd.zip", letterboxd_zip())
    assert again["diary_count"] == 0 and again["ready_count"] == 0


def test_diary_dates_import_even_when_every_film_is_already_tracked(authenticated_client, db_session):
    user = owner(db_session)
    movie(db_session, user, rating=7.0)
    preview = _preview(authenticated_client, "diary.csv", LB_DIARY.encode(), "text/csv")
    assert (preview["ready_count"], preview["diary_count"]) == (0, 2)
    applied = _apply(authenticated_client, "diary.csv", LB_DIARY.encode(), preview["fingerprint"], "text/csv")
    assert (applied["created_count"], applied["diary_created"]) == (0, 2)
    film = db_session.query(models.Movie).one()
    assert film.rating == 7.0  # The library entry keeps its own values.


def test_other_sources_bring_no_diary(authenticated_client):
    csv = b"title,director,year,rating,watched\nHeat,Michael Mann,1995,8,yes\n"
    preview = _preview(authenticated_client, "movies.csv", csv, "text/csv")
    assert preview["diary_count"] == 0
