"""Bounded library reads preserve search, ordering and ownership."""
import pytest
from app import models
from app.routers.library import CATEGORIES


@pytest.mark.parametrize("category,fixture", [
    ("movies", "test_movie_data"), ("tv-shows", "test_tv_show_data"),
    ("anime", "test_anime_data"), ("video-games", "test_video_game_data"),
    ("music", "test_music_data"), ("books", "test_book_data"),
])
def test_pages_and_exact_navigation(authenticated_client, db_session, request, category, fixture):
    payload = request.getfixturevalue(fixture)
    # API creates a correctly typed template (notably game release dates).
    result = authenticated_client.post(f"/{category}/", json=payload)
    assert result.status_code == 201
    model = CATEGORIES[category][0]
    template = db_session.get(model, result.json()["id"])
    values = {column.name: getattr(template, column.name) for column in model.__table__.columns if column.name != "id"}
    rows = [model(**{**values, "title": "Duplicate title", "rating": float(i % 10)}) for i in range(120)]
    db_session.add_all(rows)
    db_session.commit()
    endpoint = f"/library/page/{category}?search=Duplicate&sort_by=rating&order=desc"
    pages = [authenticated_client.get(f"{endpoint}&offset={offset}").json() for offset in (0, 50, 100)]
    assert [len(page["items"]) for page in pages] == [50, 50, 20]
    assert all(page["total"] == 120 for page in pages)
    items = [item for page in pages for item in page["items"]]
    assert len({item["id"] for item in items}) == 120
    assert [item["rating"] for item in items] == sorted((item["rating"] for item in items), reverse=True)
    target = items[-1]["id"]
    assert authenticated_client.get(f"{endpoint}&focus_id={target}").json()["items"][0]["id"] == target
    assert authenticated_client.get(f"{endpoint}&offset=5000").json()["offset"] == 100
    # Old callers still receive the complete list.
    assert len(authenticated_client.get(f"/{category}/").json()) == 121


def test_search_and_pages_are_private(authenticated_client, db_session):
    owner = db_session.query(models.User).filter_by(username="testuser").one()
    other = models.User(username="other", email="other@example.com", hashed_password="unused")
    db_session.add(other)
    db_session.flush()
    db_session.add(models.Movie(user_id=other.id, title="Secret target", director="Other", year=2020))
    db_session.add_all([
        models.Movie(user_id=owner.id, title=f"Other {i}", director="Director", year=2020, review="target in private notes")
        for i in range(20)
    ])
    db_session.add(models.Book(user_id=owner.id, title="target", author="Writer", year=2020))
    db_session.add(models.Movie(user_id=owner.id, title="100% literal_", director="Director", year=2020))
    db_session.commit()
    response = authenticated_client.get('/library/search?q=target')
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert len(response.json()) == 8
    assert response.json()[0]['title'] == 'target'
    assert 'Secret target' not in response.text
    assert 'private notes' not in response.text
    assert {item['title'] for item in authenticated_client.get('/library/search?q=%25').json()} == {'100% literal_'}
    page = authenticated_client.get('/library/page/movies?search=Secret').json()
    assert page['total'] == 0
    assert page['items'] == []


def test_library_read_validation(client, authenticated_client):
    for url in ('/library/page/movies?limit=101', '/library/page/movies?offset=-1', '/library/search?q=' ):
        assert authenticated_client.get(url).status_code == 422
    assert authenticated_client.get('/library/page/unknown').status_code == 404
    authenticated_client.headers.clear()
    authenticated_client.cookies.clear()
    assert client.get('/library/page/movies').status_code == 401
    assert client.get('/library/search?q=title').status_code == 401
