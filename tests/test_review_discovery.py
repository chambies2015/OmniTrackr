"""Public discovery pagination and explicit, private library saves."""
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import event

from app import auth, models
from app.routers import reviews


COMMUNITY = (
    "This compact review explains the patient pacing, warm tone, and audience fit. "
    "I would recommend it to viewers who enjoy quiet character work."
)
STANDALONE = (
    "This story uses patient pacing to support the lead performance instead of simply slowing the action down. "
    "The middle section repeats one conflict, but the final act rewards that setup with a credible emotional turn. "
    "I would recommend it to viewers who enjoy quiet character work, careful sound design, and endings that value "
    "resolution over surprise. The setting feels lived in, and the conversations reward close attention."
)


class Elements(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.elements = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@pytest.fixture
def members(db_session):
    author = models.User(username="review_author", email="author@example.test", hashed_password="unused", is_active=True)
    reader = models.User(username="review_reader", email="reader@example.test", hashed_password="unused", is_active=True)
    db_session.add_all([author, reader])
    db_session.commit()
    return author, reader


def sign_in(client, user):
    client.headers["Authorization"] = "Bearer " + auth.create_access_token({"sub": user.username})


def add_review(db, owner, category="movie", title="Patient Story", text=STANDALONE, **fields):
    item = reviews.CATEGORY_MODELS[category](user_id=owner.id, title=title, review=text, review_public=True, rating=9, **fields)
    db.add(item)
    db.flush()
    return item


def preview(client, item, category="movie"):
    return client.get(f"/api/public/reviews/{item.id}/save-preview", params={"category": category})


def save(client, item, version, category="movie"):
    return client.post(f"/api/public/reviews/{item.id}/save", params={"category": category}, json={"version": version})


def test_feed_paginates_all_eligible_reviews_before_slicing(client, db_session, members):
    author, _ = members
    expected = []
    for index in range(53):
        category = "book" if index % 7 == 0 else "movie"
        item = add_review(db_session, author, category, title=f"Quiet {index}", text=COMMUNITY if index % 3 else STANDALONE)
        expected.append((not (index % 3 == 0), -item.id, category))
    # High IDs for suppressed rows must never leave holes or conceal older reviews.
    for index in range(45):
        add_review(db_session, author, title=f"Spam {index}", text="same words repeat again. " * 30)
    suspended = add_review(db_session, author, title="Unlisted")
    db_session.add(models.PublicReviewState(user_id=author.id, category="movie", item_id=suspended.id,
        content_hash=reviews._review_content_hash("movie", suspended.id, suspended.review), suspended_at=datetime.utcnow()))
    db_session.commit()
    found = []
    offset = 0
    while True:
        response = client.get("/api/public/review-feed", params={"offset": offset, "limit": 7})
        assert response.status_code == 200
        feed = response.json()
        assert feed["next_offset"] == offset + len(feed["reviews"])
        found.extend((not row["search_ready"], -row["id"], row["category"]) for row in feed["reviews"])
        if not feed["has_more"]:
            break
        assert len(feed["reviews"]) == 7
        offset = feed["next_offset"]
    assert found == sorted(expected)
    assert len(set(found)) == 53
    legacy = client.get("/api/public/reviews", params={"limit": 100}).json()
    assert isinstance(legacy, list) and len(legacy) == 53


def test_blank_titles_are_excluded_before_pagination_without_changing_records(client, db_session, members):
    author, _ = members
    valid = add_review(db_session, author, title="An actual title")
    blanks = [add_review(db_session, author, title=title) for title in (None, "", "   ", "\t\n", "\u2003")]
    db_session.commit()
    feed = client.get("/api/public/review-feed?limit=1").json()
    assert [row["id"] for row in feed["reviews"]] == [valid.id]
    assert feed["has_more"] is False and feed["next_offset"] == 1
    assert len(client.get("/api/public/reviews?limit=1").json()) == 1
    sitemap = client.get("/sitemap.xml").text
    for item in blanks:
        assert client.get(f"/reviews/{item.id}?category=movie").status_code == 404
        assert f"/reviews/{item.id}?category=movie" not in sitemap
    assert db_session.query(models.Movie).count() == 6
    assert [item.title for item in blanks] == [None, "", "   ", "\t\n", "\u2003"]


def test_title_search_is_literal_case_insensitive_and_shared_with_ssr(client, db_session, members):
    author, _ = members
    for title in ["Elsewhere", "100% Quiet_Story", "100 percent Quiet Story"]:
        add_review(db_session, author, title=title)
    db_session.commit()
    feed = client.get("/api/public/review-feed", params={"q": "QUIET_", "category": "movie"}).json()
    assert [row["title"] for row in feed["reviews"]] == ["100% Quiet_Story"]
    assert len(client.get("/api/public/review-feed", params={"q": "%"}).json()["reviews"]) == 1
    page = client.get("/reviews", params={"q": "QUIET_", "category": "movie"})
    assert page.status_code == 200
    assert "100% Quiet_Story" in page.text and "100 percent Quiet Story" not in page.text
    assert '<meta name="robots" content="noindex, follow">' in page.text
    assert page.headers["x-robots-tag"] == "noindex, follow"
    assert '<link rel="canonical" href="https://omnitrackr.xyz/reviews?category=movie">' in page.text
    attrs = next(attrs for _, attrs in Elements(page.text).elements if attrs.get("id") == "reviewsContainer")
    assert attrs["data-hydrated"] == "true" and attrs["data-query"] == "QUIET_"
    assert attrs["data-next-offset"] == "1" and attrs["data-has-more"] == "false"
    form = next(attrs for tag, attrs in Elements(page.text).elements if tag == "form" and attrs.get("id") == "reviewFilters")
    assert form["method"].lower() == "get" and form["action"] == "/reviews"


def test_ssr_first_page_exactly_matches_feed_and_hydrates_empty(client, db_session, members):
    author, _ = members
    for index in range(25):
        add_review(db_session, author, title=f"Readable {index}")
    db_session.commit()
    feed = client.get("/api/public/review-feed").json()
    page = client.get("/reviews").text
    keys = [attrs["data-review-key"] for tag, attrs in Elements(page).elements if tag == "article" and "data-review-key" in attrs]
    assert keys == [f"{row['category']}:{row['id']}" for row in feed["reviews"]]
    assert len(keys) == 20 and 'data-next-offset="20"' in page and 'data-has-more="true"' in page
    empty = client.get("/reviews", params={"q": "missing title"}).text
    assert 'data-hydrated="true"' in empty and 'data-has-more="false"' in empty
    assert "No matching reviews yet" in empty and "/static/ad-loader.js" not in page


def test_directory_requires_standalone_content_before_indexing(client, db_session, members):
    author, _ = members
    empty = client.get("/reviews")
    assert empty.status_code == 200
    assert '<meta name="robots" content="noindex, follow">' in empty.text
    assert empty.headers["x-robots-tag"] == "noindex, follow"
    assert "/static/ad-loader.js" not in empty.text
    item = add_review(db_session, author, text=COMMUNITY)
    db_session.commit()
    thin = client.get("/reviews")
    assert thin.headers["x-robots-tag"] == "noindex, follow"
    assert item.title in thin.text
    item.review = STANDALONE
    db_session.commit()
    qualified = client.get("/reviews")
    assert '<meta name="robots" content="index, follow, max-image-preview:large">' in qualified.text
    assert "x-robots-tag" not in qualified.headers
    assert "/static/ad-loader.js" not in qualified.text
    assert client.get("/reviews?category=movie").headers.get("x-robots-tag") is None
    assert client.get("/reviews?category=book").headers["x-robots-tag"] == "noindex, follow"


def test_feed_uses_joined_queries_without_per_review_lookups(client, db_session, members):
    author, _ = members
    for index in range(80):
        add_review(db_session, author, title=f"Story {index}")
    db_session.commit()
    queries = []
    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)
    event.listen(db_session.bind, "before_cursor_execute", capture)
    try:
        assert len(client.get("/api/public/review-feed", params={"limit": 40}).json()["reviews"]) == 40
    finally:
        event.remove(db_session.bind, "before_cursor_execute", capture)
    assert len(queries) == 6


@pytest.mark.parametrize("params", [{"q": "x" * 101}, {"limit": 41}, {"offset": -1}, {"category": "unknown"}])
def test_feed_rejects_unbounded_or_invalid_filters(client, params):
    assert client.get("/api/public/review-feed", params=params).status_code in {400, 422}


def test_save_failures_are_private_and_noindexed(client, db_session, members):
    _, reader = members
    unauthorized = client.get("/api/public/reviews/1/save-preview?category=movie")
    assert unauthorized.status_code == 401
    assert unauthorized.headers["cache-control"] == "private, no-store"
    assert unauthorized.headers["x-robots-tag"].startswith("noindex")
    sign_in(client, reader)
    malformed = client.post("/api/public/reviews/1/save?category=movie", json={"version": "invalid"})
    assert malformed.status_code == 422
    assert malformed.headers["cache-control"] == "private, no-store"
    assert malformed.headers["x-robots-tag"].startswith("noindex")
    malformed_page = client.get("/reviews/not-an-id/save?category=movie")
    assert malformed_page.status_code == 422
    assert malformed_page.headers["cache-control"] == "private, no-store"
    assert malformed_page.headers["x-robots-tag"].startswith("noindex")


@pytest.mark.parametrize("category", list(reviews.CATEGORY_MODELS))
def test_save_copies_only_public_metadata_and_repeated_saves_reuse(client, db_session, members, category):
    author, reader = members
    fields = {
        "movie": {"director": "Director", "year": 2024, "poster_url": "https://example.test/art.jpg", "watched": True},
        "tv_show": {"year": 2024, "seasons": 2, "episodes": 12, "watched": True},
        "anime": {"year": 2024, "seasons": 1, "episodes": 6, "watched": True},
        "video_game": {"release_date": datetime(2024, 1, 2), "genres": "Adventure", "rawg_link": "https://example.test/private-metadata", "played": True},
        "music": {"artist": "Artist", "year": 2024, "genre": "Unexposed genre", "listened": True},
        "book": {"author": "Author", "year": 2024, "genre": "Unexposed genre", "read": True},
    }[category]
    source = add_review(db_session, author, category, **fields)
    db_session.commit()
    assert preview(client, source, category).status_code == 401
    assert save(client, source, "0" * 64, category).status_code == 401
    sign_in(client, reader)
    before = preview(client, source, category)
    assert before.status_code == 200 and before.headers["cache-control"] == "private, no-store"
    payload = before.json()
    assert payload["category"] == category and payload["library_category"] == reviews.LIBRARY_CATEGORIES[category]
    assert payload["existing"] is False
    model = reviews.CATEGORY_MODELS[category]
    assert db_session.query(model).filter_by(user_id=reader.id).count() == 0
    response = save(client, source, payload["version"], category)
    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    assert response.json()["created"] is True and response.json()["reused"] is False
    item = db_session.get(model, response.json()["item_id"])
    assert item.user_id == reader.id and item.title == source.title
    assert item.rating is None and item.review is None and item.review_public is False
    for field in reviews.PUBLIC_METADATA_FIELDS[category]:
        assert getattr(item, field) == getattr(source, field)
    completion = {"movie": "watched", "tv_show": "watched", "anime": "watched", "video_game": "played", "music": "listened", "book": "read"}[category]
    assert getattr(item, completion) is False
    if category in {"book", "music"}:
        assert item.genre is None
    if category == "video_game":
        assert item.rawg_link is None
    again = save(client, source, payload["version"], category).json()
    assert again["reused"] is True and again["created"] is False and again["item_id"] == item.id
    assert db_session.query(model).filter_by(user_id=reader.id).count() == 1
    assert preview(client, source, category).json()["item_id"] == item.id
    opened = client.get(f"/library/item/{reviews.LIBRARY_CATEGORIES[category]}/{item.id}")
    assert opened.status_code == 200 and opened.json() == {"id": item.id, "title": source.title}


def test_existing_match_is_untouched_and_uses_same_category_only(client, db_session, members):
    author, reader = members
    source = add_review(db_session, author)
    existing = models.Movie(user_id=reader.id, title="  PATIENT STORY  ", year=1980, rating=2, review="Private opinion", review_public=False, watched=True)
    db_session.add(existing)
    db_session.commit()
    sign_in(client, reader)
    state = {field: getattr(existing, field) for field in ("title", "year", "rating", "review", "review_public", "watched")}
    data = preview(client, source).json()
    assert data["existing"] is True and data["item_id"] == existing.id
    assert save(client, source, data["version"]).json()["item_id"] == existing.id
    db_session.refresh(existing)
    assert state == {field: getattr(existing, field) for field in state}
    book = add_review(db_session, author, "book")
    db_session.commit()
    assert preview(client, book, "book").json()["existing"] is False


@pytest.mark.parametrize("change", ["private", "inactive", "short", "spam", "suspended", "deleted"])
def test_withdrawn_reviews_cannot_be_previewed_or_saved(client, db_session, members, change):
    author, reader = members
    item = add_review(db_session, author)
    db_session.commit()
    sign_in(client, reader)
    version = preview(client, item).json()["version"]
    if change == "private": item.review_public = False
    if change == "inactive": author.is_active = False
    if change == "short": item.review = "Fine."
    if change == "spam": item.review = "same words repeat again. " * 30
    if change == "suspended":
        db_session.add(models.PublicReviewState(user_id=author.id, category="movie", item_id=item.id,
            content_hash=reviews._review_content_hash("movie", item.id, item.review), suspended_at=datetime.utcnow()))
    if change == "deleted": db_session.delete(item)
    db_session.commit()
    assert preview(client, item).status_code == 404
    assert save(client, item, version).status_code == 404
    assert client.get(f"/reviews/{item.id}/save?category=movie").status_code == 404
    assert client.get("/api/public/review-feed").json()["reviews"] == []
    assert db_session.query(models.Movie).filter_by(user_id=reader.id).count() == 0


def test_changed_metadata_requires_new_preview_but_review_opinion_is_never_copied(client, db_session, members):
    author, reader = members
    item = add_review(db_session, author, year=2024)
    db_session.commit()
    sign_in(client, reader)
    version = preview(client, item).json()["version"]
    item.year = 2025
    db_session.commit()
    assert save(client, item, version).status_code == 409
    assert db_session.query(models.Movie).filter_by(user_id=reader.id).count() == 0
    updated = preview(client, item).json()["version"]
    assert updated != version
    item.review = COMMUNITY
    item.rating = 1
    db_session.commit()
    assert save(client, item, updated).status_code == 200


def test_pages_escape_titles_queries_and_offer_real_save_links(client, db_session, members):
    author, _ = members
    title = '\"><img src=x onerror=alert(1)> {{CATEGORY}}'
    item = add_review(db_session, author, title=title, poster_url="javascript:alert(1)")
    db_session.commit()
    page = client.get("/reviews", params={"q": title}).text
    assert '<img src=x' not in page and 'javascript:alert(1)' not in page
    assert '&lt;img src=x' in page and '{{CATEGORY}}' in page
    attrs = Elements(page).elements
    assert any(tag == "article" and a.get("data-review-key") == f"movie:{item.id}" for tag, a in attrs)
    assert any(tag == "a" and a.get("href") == f"/reviews/{item.id}/save?category=movie" for tag, a in attrs)
    result = client.get(f"/reviews/{item.id}/save?category=movie")
    assert result.status_code == 200 and result.headers["x-robots-tag"] == "noindex, follow"
    assert result.headers["cache-control"] == "private, no-store"
    assert '<meta name="robots" content="noindex, follow">' in result.text
    assert '<img src=x' not in result.text and '/static/ad-loader.js' not in result.text
    links = [a["href"] for tag, a in Elements(result.text).elements if tag == "a" and "href" in a]
    signin = next(link for link in links if link.startswith('/?next='))
    assert parse_qs(urlsplit(signin).query) == {"next": [f"/reviews/{item.id}/save?category=movie"]}
    detail = client.get(f"/reviews/{item.id}?category=movie")
    assert f'href="/reviews/{item.id}/save?category=movie"' in detail.text
    assert 'javascript:alert(1)' not in detail.text


def test_community_review_is_saveable_without_linking_to_unavailable_detail(client, db_session, members):
    author, _ = members
    item = add_review(db_session, author, text=COMMUNITY)
    db_session.commit()
    page = client.get("/reviews").text
    assert f'href="/reviews/{item.id}?category=movie"' not in page
    assert f'href="/reviews/{item.id}/save?category=movie"' in page
    assert client.get(f"/reviews/{item.id}/save?category=movie").status_code == 200
    assert 'data-review-report="true"' in page
