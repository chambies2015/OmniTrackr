"""Length limits on library titles, names, reviews and links (app/text_limits.py).

New text is held to the limits. Text saved before they existed is left exactly as it is: it can be read,
exported, restored and edited, and an edit may shorten it but not make it longer. Imports shorten what is
too long instead of turning rows (or the whole file) away.
"""
import json

import pytest

from app import models, text_limits
from tests.test_title_pages import LONG_REVIEW, add_movie, member

TITLE = text_limits.TITLE_MAX
REVIEW = text_limits.REVIEW_MAX

# Minimal create payloads per library endpoint.
KINDS = [
    ("/movies/", models.Movie, {"director": "Someone", "year": 2001}),
    ("/tv-shows/", models.TVShow, {"year": 2001}),
    ("/anime/", models.Anime, {"year": 2001}),
    ("/video-games/", models.VideoGame, {}),
    ("/music/", models.Music, {"artist": "Someone", "year": 2001}),
    ("/books/", models.Book, {"author": "Someone", "year": 2001}),
    ("/manga/", models.Manga, {}),
    ("/podcasts/", models.Podcast, {}),
    ("/audiobooks/", models.Audiobook, {}),
]


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def _legacy(db, model, **fields):
    """A row written straight to the database, as one saved before the limits would be."""
    row = model(user_id=_me(db).id, **fields)
    db.add(row)
    db.commit()
    return row


# ---------------------------------------------------------------- the rule itself

def test_problem_allows_text_no_longer_than_what_is_saved():
    assert text_limits.problem("title", "x" * TITLE) is None
    assert text_limits.problem("title", "x" * (TITLE + 1)) == "Titles can be up to 500 characters. This one has 501."
    assert text_limits.problem("review", "x" * (REVIEW + 1)) == "Reviews can be up to 20,000 characters. This one has 20,001."
    # Saved before the limit: the same length, or shorter, is fine; longer is not.
    assert text_limits.problem("title", "y" * 700, current="x" * 700) is None
    assert text_limits.problem("title", "y" * 650, current="x" * 700) is None
    message = text_limits.problem("title", "y" * 701, current="x" * 700)
    assert message.startswith("This title was saved before the 500-character limit") and "700 characters now" in message
    # Under the limit before, over it now: the plain rule.
    assert text_limits.problem("review", "x" * (REVIEW + 1), current="short").startswith("Reviews can be up to")
    # Fields without a limit, and non-text values, are never a problem.
    assert text_limits.problem("rating", "x" * 100_000) is None
    assert text_limits.problem("review", None) is None


def test_clipping_shortens_text_and_drops_links():
    values = {"title": "a" * 600, "review": "fine", "poster_url": "https://example.com/" + "p" * 3000, "rating": 8}
    assert text_limits.clip_fields(values) == ["title", "poster_url"]
    assert len(values["title"]) == TITLE and values["title"].endswith(text_limits.ELLIPSIS)
    assert values["poster_url"] is None and values["review"] == "fine" and values["rating"] == 8
    # A restore keeps up to RESTORE_FACTOR times the limit.
    restored = {"title": "a" * 600}
    assert text_limits.clip_fields(restored, restore=True) == [] and len(restored["title"]) == 600
    assert text_limits.describe(["title", "review"]) == "The title and review were shortened to fit the length limit."
    assert text_limits.describe([]) is None


# ---------------------------------------------------------------- adding and editing in the library

@pytest.mark.parametrize("path, model, extra", KINDS)
def test_new_entries_keep_to_the_limits(authenticated_client, db_session, path, model, extra):
    too_long = authenticated_client.post(path, json={"title": "t" * (TITLE + 1), **extra})
    assert too_long.status_code == 422
    detail = too_long.json()["detail"][0]
    # A whole-body error, so the dashboard shows the sentence as it is.
    assert detail["loc"] == ["body"] and "Titles can be up to 500 characters. This one has 501." in detail["msg"]
    review = authenticated_client.post(path, json={"title": "Fine", "review": "r" * (REVIEW + 1), **extra})
    assert review.status_code == 422 and "Reviews can be up to 20,000 characters" in review.json()["detail"][0]["msg"]
    assert db_session.query(model).count() == 0

    at_limit = authenticated_client.post(path, json={"title": "t" * TITLE, "review": "r" * REVIEW, **extra})
    assert at_limit.status_code == 201, at_limit.text
    assert len(db_session.query(model).one().review) == REVIEW


@pytest.mark.parametrize("path, model, extra", KINDS)
def test_entries_saved_before_the_limits_stay_readable_and_editable(authenticated_client, db_session, path, model, extra):
    long_title, long_review = "Old " + "t" * 900, "Old review. " * 3000  # 904 and 36,000 characters
    row = _legacy(db_session, model, title=long_title, review=long_review, rating=6, **extra)

    listed = authenticated_client.get(path)
    assert listed.status_code == 200 and listed.json()[0]["title"] == long_title
    assert authenticated_client.get(f"{path}{row.id}").json()["review"] == long_review

    # The dashboard sends every field on save; changing only the rating must not trip the limits.
    response = authenticated_client.put(f"{path}{row.id}", json={"title": long_title, "review": long_review, "rating": 9})
    assert response.status_code == 200, response.text
    db_session.refresh(row)
    assert (row.title, row.review, row.rating) == (long_title, long_review, 9)

    # Fixing a typo or shortening is fine, even while still over the limit.
    shorter = long_review[:-50]
    assert authenticated_client.put(f"{path}{row.id}", json={"review": shorter}).status_code == 200
    db_session.refresh(row)
    assert row.review == shorter

    # Making it longer is not, and the entry is left as it was.
    grown = authenticated_client.put(f"{path}{row.id}", json={"title": long_title + "!", "rating": 2})
    assert grown.status_code == 422
    assert grown.json()["detail"] == ("This title was saved before the 500-character limit, so it can be edited and "
                                      "shortened but not made longer. It has 904 characters now.")
    db_session.refresh(row)
    assert (row.title, row.rating) == (long_title, 9)


def test_edits_of_ordinary_entries_keep_to_the_limits(authenticated_client, db_session):
    movie = authenticated_client.post("/movies/", json={"title": "Arrival", "director": "Denis Villeneuve", "year": 2016}).json()
    response = authenticated_client.put(f"/movies/{movie['id']}", json={"review": "x" * (REVIEW + 1)})
    assert response.status_code == 422
    assert response.json()["detail"] == "Reviews can be up to 20,000 characters. This one has 20,001."
    for field, limit in (("director", text_limits.CREATOR_MAX), ("poster_url", text_limits.LINK_MAX)):
        value = "https://example.com/" + "x" * limit if field == "poster_url" else "x" * (limit + 1)
        assert authenticated_client.put(f"/movies/{movie['id']}", json={field: value}).status_code == 422
    assert authenticated_client.put(f"/movies/{movie['id']}", json={"review": "x" * REVIEW}).status_code == 200
    stored = db_session.get(models.Movie, movie["id"])
    assert stored.director == "Denis Villeneuve" and len(stored.review) == REVIEW


# ---------------------------------------------------------------- title page and finish screen

def test_title_page_review_keeps_to_the_limit_but_edits_an_older_long_review(authenticated_client, db_session):
    api = "/api/titles/movie/interstellar-2014"
    add_movie(db_session, member(db_session, "a"))
    db_session.commit()
    page = authenticated_client.get("/titles/movie/interstellar-2014").text
    assert f'maxlength="{REVIEW}"' in page

    response = authenticated_client.put(f"{api}/review", json={"review": "x" * (REVIEW + 1), "public": False})
    assert response.status_code == 422 and response.json()["detail"].startswith("Reviews can be up to 20,000")
    # Refused before anything was added to the library.
    assert db_session.query(models.Movie).filter_by(user_id=_me(db_session).id).count() == 0

    old = (LONG_REVIEW + " ") * 80  # about 32,000 characters, saved before the limit
    mine = add_movie(db_session, _me(db_session), review=old, review_public=False)
    db_session.commit()
    loaded = authenticated_client.get(f"{api}/my-review").json()["review"]
    assert loaded == old
    edited = old.strip().replace("Interstellar", "INTERSTELLAR", 1)
    response = authenticated_client.put(f"{api}/review", json={"review": edited, "public": False, "expected_review": old})
    assert response.status_code == 200, response.text
    db_session.refresh(mine)
    assert mine.review == edited
    grown = authenticated_client.put(f"{api}/review", json={"review": edited + " More.", "public": False, "expected_review": edited})
    assert grown.status_code == 422 and "saved before the 20,000-character limit" in grown.json()["detail"]


def test_finish_screen_review_allows_the_full_limit(authenticated_client, db_session):
    movie = authenticated_client.post("/movies/", json={"title": "Arrival", "director": "Denis Villeneuve", "year": 2016,
                                                       "watched": True}).json()
    moment = authenticated_client.post("/completion-moments/", json={"category": "movies", "item_id": movie["id"]}).json()
    too_long = authenticated_client.post(f"/completion-moments/{moment['id']}/review", json={"review": "word " * 4001})
    assert too_long.status_code == 422 and "Reviews can be up to 20,000 characters" in too_long.json()["detail"][0]["msg"]
    assert authenticated_client.post(f"/completion-moments/{moment['id']}/review",
                                     json={"review": "x" * 15000}).status_code == 200


# ---------------------------------------------------------------- restoring an OmniTrackr backup

def _backup(**lists):
    return {"movies": [], "tv_shows": [], **lists}


def _movie(title, review=None, **extra):
    return {"title": title, "director": "Someone", "year": 2001, "rating": None, "watched": True,
            "review": review, "review_public": False, "poster_url": None, **extra}


def test_a_restore_brings_back_text_saved_before_the_limits_whole(authenticated_client, db_session):
    title, review = "T" * 900, "R" * 36000
    response = authenticated_client.post("/import/", json=_backup(movies=[_movie(title, review)]))
    assert response.status_code == 200 and response.json()["shortened"] == 0
    restored = db_session.query(models.Movie).one()
    assert (restored.title, restored.review) == (title, review)
    # Restoring the same file again updates that entry and adds nothing.
    again = authenticated_client.post("/import/", json=_backup(movies=[_movie(title, review)])).json()
    assert (again["movies_created"], again["movies_updated"], again["shortened"]) == (0, 1, 0)
    assert db_session.query(models.Movie).count() == 1


def test_a_restore_shortens_only_text_far_past_the_limits(authenticated_client, db_session):
    huge_title = "H" * (TITLE * text_limits.RESTORE_FACTOR + 100)
    huge_review = "R" * (REVIEW * text_limits.RESTORE_FACTOR + 1)
    entry = _movie(huge_title, huge_review, poster_url="https://example.com/" + "p" * 30000)
    response = authenticated_client.post("/import/", json=_backup(movies=[entry]))
    assert response.status_code == 200
    assert response.json()["shortened"] == 3 and response.json()["errors"] == []
    saved = db_session.query(models.Movie).one()
    assert len(saved.title) == TITLE * text_limits.RESTORE_FACTOR and saved.title.endswith(text_limits.ELLIPSIS)
    assert len(saved.review) == REVIEW * text_limits.RESTORE_FACTOR and saved.poster_url is None
    # The shortened copy is found again on a second restore rather than added twice.
    again = authenticated_client.post("/import/", json=_backup(movies=[entry])).json()
    assert (again["movies_created"], again["movies_updated"]) == (0, 1)
    assert db_session.query(models.Movie).count() == 1
    db_session.refresh(saved)
    assert len(saved.title) == TITLE * text_limits.RESTORE_FACTOR


def test_a_restore_never_cuts_what_the_library_already_holds(authenticated_client, db_session):
    huge = "K" * (REVIEW * text_limits.RESTORE_FACTOR + 500)
    row = _legacy(db_session, models.Movie, title="Kept", director="Someone", year=2001, review=huge)
    longer = _movie("Kept", huge + "more")
    response = authenticated_client.post("/import/", json=_backup(movies=[longer])).json()
    assert response["movies_updated"] == 1
    db_session.refresh(row)
    assert row.review == huge


def test_journal_entries_with_long_titles_no_longer_fail_the_whole_restore(authenticated_client, db_session):
    title = "J" * 700  # journal titles copy library titles, which had no limit
    backup = _backup(movies=[_movie(title)], activities=[
        {"category": "movies", "title": title, "action": "completed", "occurred_at": "2026-05-01T20:00:00"}])
    response = authenticated_client.post("/import/", json=backup)
    assert response.status_code == 200, response.text
    assert response.json()["activities_created"] == 1
    entry = db_session.query(models.ActivityEntry).one()
    assert entry.title == title and entry.item_id == db_session.query(models.Movie).one().id
    assert authenticated_client.post("/import/", json=backup).json()["activities_skipped"] == 1


def test_a_restore_file_upload_reports_what_was_shortened(authenticated_client, db_session):
    entry = _movie("Fine", "R" * (REVIEW * text_limits.RESTORE_FACTOR + 10))
    upload = {"file": ("backup.json", json.dumps(_backup(movies=[entry])).encode(), "application/json")}
    response = authenticated_client.post("/import/file/", files=upload)
    assert response.status_code == 200 and response.json()["shortened"] == 1


# ---------------------------------------------------------------- Import Studio (other services' exports)

def _csv(name, content):
    return {"file": (name, content.encode("utf-8"), "text/csv")}


def test_import_studio_shortens_long_text_and_says_so(authenticated_client, db_session):
    long_title, long_review = "L" * 650, "Long thoughts. " * 2000  # 650 and 30,000 characters
    content = ("Title,Category,Year,Review\n"
               f"{long_title},movies,2001,{long_review}\n"
               "Arrival,movies,2016,Short and sweet.\n")
    preview = authenticated_client.post("/import-studio/preview/", files=_csv("list.csv", content),
                                        data={"source": "generic"})
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["ready_count"] == 2 and data["invalid_count"] == 0
    rows = {row["row"]: row for row in data["preview"]}
    assert rows[2]["reason"] == "The title and review were shortened to fit the length limit."
    assert len(rows[2]["title"]) == TITLE and len(rows[2]["values"]["review"]) == REVIEW
    assert rows[3]["reason"] is None

    applied = authenticated_client.post("/import-studio/apply/", files=_csv("list.csv", content),
                                        data={"source": "generic", "fingerprint_confirmation": data["fingerprint"]})
    assert applied.status_code == 200 and applied.json()["created_count"] == 2
    saved = db_session.query(models.Movie).filter(models.Movie.title.like("LLL%")).one()
    assert len(saved.title) == TITLE and len(saved.review) == REVIEW and saved.review.endswith(text_limits.ELLIPSIS)

    # The same file again finds both titles already there.
    repeated = authenticated_client.post("/import-studio/preview/", files=_csv("list.csv", content),
                                         data={"source": "generic"}).json()
    assert repeated["ready_count"] == 0 and repeated["duplicate_count"] == 2


def test_import_studio_matches_a_long_title_saved_before_the_limit(authenticated_client, db_session):
    long_title = "Saved " + "s" * 700
    _legacy(db_session, models.Movie, title=long_title, director="Someone", year=2001)
    content = f"Title,Category,Year\n{long_title},movies,2001\n"
    data = authenticated_client.post("/import-studio/preview/", files=_csv("list.csv", content),
                                     data={"source": "generic"}).json()
    assert data["duplicate_count"] == 1 and data["ready_count"] == 0
