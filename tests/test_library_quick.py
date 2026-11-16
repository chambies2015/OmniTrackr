"""Library sorts added in Nov 2026 and the quick mark-done / rating controls."""
from pathlib import Path

import pytest

from app import models
from app.routers.library import CATEGORIES

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
QUICK_JS = (ROOT / "app" / "static" / "library-quick.js").read_text(encoding="utf-8")
LIBRARY_JS = (ROOT / "app" / "static" / "dashboard" / "library.js").read_text(encoding="utf-8")
CORE_JS = (ROOT / "app" / "static" / "dashboard" / "core.js").read_text(encoding="utf-8")
WORKSPACE_CSS = (ROOT / "app" / "static" / "workspace-2026.css").read_text(encoding="utf-8")


def titles(client, category, **params):
    response = client.get(f"/library/page/{category}", params=params)
    assert response.status_code == 200, response.text
    return [item["title"] for item in response.json()["items"]]


def owner(db_session):
    return db_session.query(models.User).filter_by(username="testuser").one()


@pytest.mark.parametrize("category", list(CATEGORIES))
def test_title_and_added_sorts_cover_each_category(authenticated_client, db_session, category):
    user = owner(db_session)
    model = CATEGORIES[category][0]
    for title in ["banana", "Apple", "cherry"]:
        db_session.add(model(user_id=user.id, title=title))
        db_session.commit()
    assert titles(authenticated_client, category, sort_by="title", order="asc") == ["Apple", "banana", "cherry"]
    assert titles(authenticated_client, category, sort_by="title", order="desc") == ["cherry", "banana", "Apple"]
    assert titles(authenticated_client, category, sort_by="added", order="desc") == ["cherry", "Apple", "banana"]
    # The default order (oldest added first) is unchanged.
    assert titles(authenticated_client, category) == ["banana", "Apple", "cherry"]
    assert titles(authenticated_client, category, sort_by="added", order="asc") == ["banana", "Apple", "cherry"]


def test_title_sort_pages_without_gaps(authenticated_client, db_session):
    user = owner(db_session)
    db_session.add_all(models.Movie(user_id=user.id, title=f"Same {index % 3}") for index in range(7))
    db_session.commit()
    seen = []
    for offset in (0, 3, 6):
        page = authenticated_client.get("/library/page/movies", params={
            "sort_by": "title", "order": "asc", "limit": 3, "offset": offset,
        }).json()
        seen += [item["id"] for item in page["items"]]
    assert len(seen) == len(set(seen)) == 7


def test_audiobook_length_sort_works(authenticated_client, db_session):
    user = owner(db_session)
    db_session.add_all([
        models.Audiobook(user_id=user.id, title="Long", length_hours=30),
        models.Audiobook(user_id=user.id, title="Unknown", length_hours=None),
        models.Audiobook(user_id=user.id, title="Short", length_hours=4.5),
    ])
    db_session.commit()
    assert titles(authenticated_client, "audiobooks", sort_by="length", order="asc") == ["Short", "Long", "Unknown"]
    assert titles(authenticated_client, "audiobooks", sort_by="length", order="desc") == ["Long", "Short", "Unknown"]


@pytest.mark.parametrize("sort", ["title-asc", "title-desc", "added-desc", "length-asc"])
def test_saved_views_accept_the_new_sorts(authenticated_client, sort):
    category = "audiobooks" if sort.startswith("length") else "movies"
    response = authenticated_client.post(f"/library/views/{category}", json={"name": sort, "filters": {"sort": sort}})
    assert response.status_code == 200, response.text
    assert response.json()["filters"]["sort"] == sort


def test_every_sort_menu_offers_title_and_added_orders():
    assert INDEX.count('<option value="">Date added (oldest first)</option>') == 9
    assert INDEX.count('<option value="added-desc">Date added (newest first)</option>') == 9
    assert INDEX.count('<option value="title-asc">Title (A → Z)</option>') == 9
    assert "Sort by..." not in INDEX


def test_quick_controls_are_wired_into_every_library_row():
    script = '<script src="/static/library-quick.js?v='
    assert script in INDEX
    assert INDEX.index(script) < INDEX.index('<script src="./app.js"></script>')
    assert "window.OmniLibraryQuick?.decorate(row, tableId);" in LIBRARY_JS
    # Quick saves send one field through the same endpoint Edit uses.
    assert "{ [info.field]: !complete }" in QUICK_JS
    assert "{ rating: score }" in QUICK_JS
    assert "method: 'PUT'" in QUICK_JS
    # Edit-mode rows have no next-up anchor and are never decorated.
    assert "if (!info) return; // Edit mode rows keep their inputs untouched." in QUICK_JS
    # Finishing from the shelf opens the same reflection prompt as saving an edit.
    assert "window.openCompletionMoment(info.category, info.id)" in QUICK_JS


def test_quick_rating_scale_matches_the_server_range():
    assert "for (let score = 1; score <= 10; score += 1)" in QUICK_JS


def test_sort_choice_is_remembered_per_shelf():
    assert "const LIBRARY_SORT_KEY = 'omnitrackr_library_sort';" in CORE_JS
    assert "restoreLibrarySort(source.tab);" in CORE_JS
    assert "panel.dataset.libraryFiltered = String(filtered);" in CORE_JS


def test_phone_shelf_shows_two_covers_a_row():
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in WORKSPACE_CSS
    assert ".library-rate-pop" in WORKSPACE_CSS
