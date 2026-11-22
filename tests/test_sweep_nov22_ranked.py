"""Sweep of #309 (Nov 22 2026): Rankings share links, /ranked/<token>, and keeping a ranking made there."""
import pytest

from app import models, rankings
from app.routers import ranked_share
from app.routers import tier_list as tier_list_router

from tests.test_ranking_shares import (  # noqa: F401
    CHROME, counting, headers, member, ranked_films, share_on, shared,
)

FILMS = ["Alien", "Arrival", "Brazil", "Casablanca", "Dune"]


@pytest.fixture
def poster_fetches(client, monkeypatch):
    """Every poster address the card drawing asks the image fetcher for."""
    asked = []

    async def fake_poster_bytes(_client, url):
        asked.append(url)
        return b"not an image"

    monkeypatch.setattr(tier_list_router, "_poster_bytes", fake_poster_bytes)
    monkeypatch.setattr(ranked_share, "_CARDS", None)
    if getattr(client.app.state, "external_api_client", None) is None:
        monkeypatch.setattr(client.app.state, "external_api_client", _NoNetwork(), raising=False)
    return asked


class _NoNetwork:
    async def aclose(self):
        return None


def test_the_pictures_only_fetch_posters_from_poster_hosts(client, db_session, poster_fetches):
    """A library poster can be any address the member typed in. Drawing the card must not make the
    server fetch internal or unknown addresses for whoever turned the link on."""
    user = member(db_session)
    rows = ranked_films(db_session, user, FILMS)
    rows[0].poster_url = "https://127.0.0.1:8799/admin.jpg"
    rows[1].poster_url = "https://169.254.169.254.nip.io/latest/meta-data.jpg"
    rows[2].poster_url = "https://m.media-amazon.com/images/M/poster.jpg"
    rows[3].poster_url = "https://covers.openlibrary.org/b/id/1-L.jpg"
    rows[4].poster_url = "https://user:pass@m.media-amazon.com/x.jpg"
    db_session.commit()
    path = share_on(client, user).json()["share"]["path"]
    for picture in ("card.png", "story.png"):
        assert client.get(f"{path}/{picture}", headers=CHROME).status_code == 200
    assert sorted(set(poster_fetches)) == ["https://covers.openlibrary.org/b/id/1-L.jpg",
                                           "https://m.media-amazon.com/images/M/poster.jpg"]


def test_keeping_a_ranking_brings_posters_only_from_poster_hosts(client, db_session):
    owner = member(db_session)
    rows = ranked_films(db_session, owner, FILMS)
    rows[0].poster_url = "https://tracker.example/pixel.gif?who=everyone"
    rows[1].poster_url = "https://m.media-amazon.com/images/M/arrival.jpg"
    db_session.commit()
    path = share_on(client, owner).json()["share"]["path"]
    viewer = member(db_session, "kit")
    response = client.post("/api/rankings/take", headers=headers(viewer),
                           json={"token": path.rsplit("/", 1)[1], "titles": ["Alien", "Arrival"]})
    assert response.status_code == 200, response.text
    posters = dict(db_session.query(models.Movie.title, models.Movie.poster_url).filter_by(user_id=viewer.id).all())
    assert posters == {"Alien": None, "Arrival": "https://m.media-amazon.com/images/M/arrival.jpg"}


def _two_dunes(db_session):
    owner = member(db_session)
    titles = ["Dune", "Dune", "Heat", "Jaws"]
    rows = [models.Movie(title=title, year=year, director=f"Director {index}", watched=True, user_id=owner.id)
            for index, (title, year) in enumerate(zip(titles, [1984, 2021, 1995, 1975]))]
    db_session.add_all(rows)
    db_session.commit()
    db_session.add(models.Ranking(user_id=owner.id, category="movies", ranked="[" + ",".join(str(row.id) for row in rows) + "]"))
    db_session.commit()
    return owner


def _taken(client, db_session, viewer, body):
    response = client.post("/api/rankings/take", headers=headers(viewer), json=body)
    assert response.status_code == 200, response.text
    films = {row.id: (row.title, row.year) for row in db_session.query(models.Movie).filter_by(user_id=viewer.id)}
    ranked = client.get("/api/rankings?category=movies", headers=headers(viewer)).json()["detail"]["ranked"]
    return response.json(), [films[item["id"]] for item in ranked]


def test_two_titles_with_one_name_both_come_along_in_the_order_picked(client, db_session):
    """A film and its remake on one top ten: the second used to be dropped, and the first name
    always took the higher place, so the visitor's number one could be the wrong Dune."""
    owner = _two_dunes(db_session)
    token = share_on(client, owner).json()["share"]["path"].rsplit("/", 1)[1]
    viewer = member(db_session, "kit")
    body, order = _taken(client, db_session, viewer,
                         {"token": token, "titles": ["Dune", "Heat", "Dune"], "positions": [2, 3, 1]})
    assert body["added"] == 3 and body["ranked"] is True
    assert order == [("Dune", 2021), ("Heat", 1995), ("Dune", 1984)]


def test_a_take_without_places_still_keeps_both(client, db_session):
    """Rankings kept in a browser before this sweep carry names only."""
    owner = _two_dunes(db_session)
    token = share_on(client, owner).json()["share"]["path"].rsplit("/", 1)[1]
    viewer = member(db_session, "kit")
    body, order = _taken(client, db_session, viewer, {"token": token, "titles": ["Jaws", "Dune", "Dune"]})
    assert body["added"] == 3
    assert order == [("Jaws", 1975), ("Dune", 1984), ("Dune", 2021)]


def test_a_place_that_no_longer_holds_that_title_falls_back_to_the_name(client, db_session):
    _, path = shared(client, db_session)  # Alien is #1, Arrival #2, Brazil #3 ...
    viewer = member(db_session, "kit")
    token = path.rsplit("/", 1)[1]
    body, order = _taken(client, db_session, viewer,
                         {"token": token, "titles": ["Brazil", "Alien"], "positions": [1, 1]})
    assert [title for title, _ in order] == ["Brazil", "Alien"]
    bad = client.post("/api/rankings/take", headers=headers(viewer),
                      json={"token": token, "titles": ["Alien", "Arrival"], "positions": [0, 11]})
    assert bad.status_code == 422


def test_a_title_that_reads_like_a_page_placeholder_stays_text(client, db_session):
    """discover.page filled its placeholders one after another, so a library title "{{CONTENT}}" in
    the description pulled the whole page into the meta tag (four copies of the list)."""
    user = member(db_session)
    ranked_films(db_session, user, ["{{CONTENT}}", "{{STRUCTURED_DATA}}", "{{PATH}}", "Heat"])
    path = share_on(client, user).json()["share"]["path"]
    page = client.get(path, headers=CHROME)
    assert page.status_code == 200
    html = page.text
    assert html.count('id="rankedShare"') == 1
    assert html.count("/static/ranked-share.js") == 1
    assert 'data-title="{{CONTENT}}"' in html and 'data-title="{{STRUCTURED_DATA}}"' in html
    assert 'Number one: {{CONTENT}}, then {{STRUCTURED_DATA}} and {{PATH}}.' in html


def test_a_placement_does_not_offer_a_link_that_shows_nothing(client, db_session):
    user, path = shared(client, db_session)
    assert rankings._shared_path(db_session, user.id, "movies") == path
    user.movies_private = True
    db_session.commit()
    assert rankings._shared_path(db_session, user.id, "movies") is None
    assert client.get(path, headers=CHROME).status_code == 404
    share = client.get("/api/rankings?category=movies", headers=headers(user)).json()["detail"]["share"]
    assert share["path"] == path and share["allowed"] is False  # still listed, so it can be turned off
    user.movies_private = False
    db_session.commit()
    assert rankings._shared_path(db_session, user.id, "movies") == path


def test_the_page_and_tab_load_the_new_scripts():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    index = (root / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    assert "/static/rankings.js?v=20261122-ranked-sweep-1" in index
    assert ranked_share.JS_VERSION == ranked_share.CSS_VERSION == "20261122-ranked-sweep-1"
    script = (root / "app" / "static" / "rankings.js").read_text(encoding="utf-8")
    assert "Your share link is paused" in script
    styles = (root / "app" / "static" / "ranked-share.css").read_text(encoding="utf-8")
    assert "scroll-margin-top" in styles
