"""Synthetic large-library checks; uses the isolated test database only."""
from time import perf_counter

from app import models


def test_large_library_baseline(authenticated_client, db_session):
    owner = db_session.query(models.User).filter_by(username="testuser").one()
    db_session.add_all([
        models.Movie(user_id=owner.id, title=f"Synthetic movie {index:05}", director="Synthetic director", year=2020,
                     review="A private review. " * 100, watched=False)
        for index in range(3000)
    ])
    db_session.commit()
    start = perf_counter()
    response = authenticated_client.get('/movies/')
    elapsed = perf_counter() - start
    assert response.status_code == 200
    assert len(response.json()) == 3000
    print(f"Legacy list: {len(response.content):,} bytes, {elapsed:.3f}s, 3000 rows")
    start = perf_counter()
    page = authenticated_client.get('/library/page/movies')
    elapsed = perf_counter() - start
    assert page.status_code == 200
    assert len(page.json()['items']) == 50
    assert page.json()['total'] == 3000
    assert len(page.content) < len(response.content) / 40
    print(f"Paged list: {len(page.content):,} bytes, {elapsed:.3f}s, 50 rows")
    start = perf_counter()
    search = authenticated_client.get('/library/search?q=Synthetic')
    elapsed = perf_counter() - start
    assert search.status_code == 200
    assert len(search.json()) == 8
    assert len(search.content) < 3000
    print(f"Search: {len(search.content):,} bytes, {elapsed:.3f}s, 8 results")
