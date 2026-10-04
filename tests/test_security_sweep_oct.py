"""October security sweep: regression tests for the issues found and fixed."""
from app import auth, for_you, models, title_metadata, title_pages

LONG_REVIEW = (
    "Interstellar works because the science never crowds out the family story at its center. The docking "
    "sequence is one of the most tense scenes I have seen, and the score keeps building pressure without "
    "feeling cheap. Some dialogue is clumsy, yet the time-dilation planet hit me hard on a rewatch and the final "
    "act ties the father and daughter threads together better than I remembered."
)


def member(db, name, **extra):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, **extra)
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------- private shelves stay private

def test_a_title_only_a_private_shelf_tracks_has_no_page(client, db_session):
    secret = member(db_session, "secretive", movies_private=True)
    db_session.add(models.Movie(user_id=secret.id, title="Obscure Film", director="x", year=1977, rating=9))
    db_session.commit()
    assert title_pages.find(db_session, "movie", "obscure-film-1977") is None
    assert client.get("/titles/movie/obscure-film-1977").status_code == 404


def test_private_shelves_are_not_counted_or_suggested(db_session):
    a, b = member(db_session, "open_a"), member(db_session, "open_b")
    hidden = member(db_session, "hidden_c", movies_private=True, books_private=True)
    for user in (a, b, hidden):
        db_session.add(models.Movie(user_id=user.id, title="Arrival", director="Denis Villeneuve", year=2016, rating=9))
    # Both open members and the private member share a book; only the private member's shelf has "Private Book".
    for user in (a, b):
        db_session.add(models.Book(user_id=user.id, title="Dune", author="Frank Herbert", year=1965))
    db_session.add(models.Book(user_id=hidden.id, title="Private Book", author="Me", year=2020))
    db_session.commit()
    group = title_pages.find(db_session, "movie", "arrival-2016")
    summary = title_pages.summarize(db_session, group)
    assert summary["members"] == 2
    related = {item["title"] for item in summary["related"]}
    assert "Private Book" not in related
    popular = {item["title"]: item["members"] for item in title_pages.popular(db_session, "movie")}
    assert popular["Arrival"] == 2


def test_related_titles_ignore_a_members_private_categories(db_session):
    a = member(db_session, "rel_a")
    b = member(db_session, "rel_b", books_private=True)
    for user in (a, b):
        db_session.add(models.Movie(user_id=user.id, title="Arrival", director="x", year=2016))
        db_session.add(models.Book(user_id=user.id, title="Shared Secret", author="x", year=2001))
    db_session.commit()
    group = title_pages.find(db_session, "movie", "arrival-2016")
    assert all(item["title"] != "Shared Secret" for item in title_pages.summarize(db_session, group)["related"])


def test_published_reviews_still_reach_their_title_page(client, db_session):
    """A review the member chose to make public stays public even on a private shelf."""
    writer = member(db_session, "writer_private", movies_private=True)
    db_session.add(models.Movie(user_id=writer.id, title="Interstellar", director="Christopher Nolan", year=2014,
                                rating=9, review=LONG_REVIEW, review_public=True))
    db_session.commit()
    page = client.get("/titles/movie/interstellar-2014")
    assert page.status_code == 200 and "time-dilation planet" in page.text


def test_starter_picks_skip_private_shelves(db_session):
    a = member(db_session, "pick_a")
    b = member(db_session, "pick_b", movies_private=True)
    c = member(db_session, "pick_c", movies_private=True)
    for user in (a, b, c):
        db_session.add(models.Movie(user_id=user.id, title="Hidden Gem", director="x", year=2001))
    db_session.commit()
    assert for_you.popular_titles(db_session, "movies") == []
    assert for_you.popular_entry_payload(db_session, "movies", "Hidden Gem") is None


def test_deactivated_members_do_not_make_titles_popular(db_session):
    a = member(db_session, "act_a")
    gone = member(db_session, "gone_b")
    gone.is_active = False
    for user in (a, gone):
        db_session.add(models.Movie(user_id=user.id, title="Ghost Pick", director="x", year=2001))
    db_session.commit()
    assert for_you.popular_titles(db_session, "movies") == []


# ---------------------------------------------------------------- external data

def test_only_real_imdb_ids_become_links():
    import re
    pattern = re.compile(r"tt\d{5,10}")
    assert pattern.fullmatch("tt0816692")
    assert not pattern.fullmatch("tt/../../evil")
    source = open(title_metadata.__file__, encoding="utf-8").read()
    assert 're.fullmatch(r"tt\\d{5,10}", v)' in source
