"""Sweep of the Nov 10 merges that followed the last one: the sign-in refresh (#199) and
the binge calculator's "how long does it take" guides (#200)."""
import re
from pathlib import Path

from app import binge_calculator as binge, in_order, models, title_pages, title_search
from app.binge_guides import GUIDES
from app.routers import auth as auth_router
from app.routers import binge_calculator as pages
from tests.test_security_sweep_nov06 import _limited

STATIC = Path(__file__).parents[1] / "app" / "static"


# ---------------------------------------------------------------- signing up and resetting

def test_every_sign_in_step_is_rate_limited():
    """Confirming an email was the one step anyone could call without a limit. Logging out stays open."""
    checked = 0
    for route in auth_router.router.routes:
        for method in route.methods:
            if route.path == "/auth/logout":
                continue
            assert _limited(auth_router.router, route.path, method), (method, route.path)
            checked += 1
    assert checked == 12
    assert _limited(auth_router.router, "/auth/verify-email", "GET")


def test_confirming_an_email_still_works_through_the_limited_route(client, db_session):
    client.post("/auth/register", json={"email": "new@example.com", "username": "newperson", "password": "a long enough phrase 7"})
    user = db_session.query(models.User).filter_by(username="newperson").one()
    assert not user.is_verified
    response = client.get("/auth/verify-email", params={"token": user.verification_token})
    assert response.status_code == 200
    db_session.refresh(user)
    assert user.is_verified
    assert client.get("/auth/verify-email", params={"token": "made-up"}).status_code == 400


def test_analytics_is_given_an_address_without_emailed_keys():
    """The homepage is where reset and confirmation links land, and the only page that loads Analytics."""
    loader = (STATIC / "analytics.js").read_text(encoding="utf-8")
    for name in ("token", "reset_token", "email_change_token"):
        assert f"'{name}'" in loader
    assert "page_location: pageLocation()" in loader
    # The address is cleaned when the visit is queued, before gtag.js is even requested.
    assert loader.index("function pageLocation()") < loader.index("window.gtag('config'") < loader.index("function load()")
    # Every key an email of ours puts in an address is on the list.
    mail = (Path(__file__).parents[1] / "app" / "email.py").read_text(encoding="utf-8")
    assert set(re.findall(r"APP_URL\}/\?(\w+)=\{token\}", mail)) == {"token", "reset_token", "email_change_token"}


# ---------------------------------------------------------------- the binge calculator

def _scan(kind, title, year):
    """The guide a title belongs to, found the slow way: every guide, every title, every name."""
    wanted = title_pages.normalize(title)
    for slug, entry in GUIDES.items():
        for item in binge.titles(entry):
            if item["kind"] == kind and wanted in in_order.names(item) and in_order._same_year(item, year):
                return slug
    return None


def test_the_title_index_answers_the_same_as_reading_every_guide():
    checked = 0
    for entry in GUIDES.values():
        for item in binge.titles(entry):
            for name in [item["title"], *item.get("aka", ())]:
                for year in (item["year"], None, item["year"] + 1, item["year"] + 9):
                    for kind in ("tv", "anime", "book", "movie"):
                        assert binge.for_title(kind, f"  {name.upper()} ", year) == _scan(kind, name, year), (kind, name, year)
                        checked += 1
    assert checked > 1000
    assert binge.for_title("tv", "Nobody Tracks This", 2020) is None and binge.known_length("game", "Dune", 1965) == {}


def test_matching_a_library_title_no_longer_reads_every_guide(monkeypatch):
    """"What you have left" matches each unfinished title twice; a big library walked the guides thousands of times."""
    binge._TITLE_INDEX.clear()
    calls = []
    real = binge.titles
    monkeypatch.setattr(binge, "titles", lambda entry: calls.append(1) or real(entry))
    for number in range(300):
        assert binge.for_title("movie", f"Unknown Film {number}", 2001) is None
        assert binge.known_length("tv", f"Unknown Show {number}", 2001) == {}
    assert binge.known_length("tv", "Breaking Bad", 2008)["episodes"] == 62
    assert binge.for_title("book", "The Fellowship of the Ring", 1954) == "the-lord-of-the-rings"
    assert len(calls) == len(GUIDES)  # once each, to build the index


def test_what_you_have_left_is_quick_for_a_big_library(authenticated_client, db_session):
    user = db_session.query(models.User).filter_by(username="testuser").one()
    rows = [models.Movie(user_id=user.id, title=f"Film {number}", year=2000 + number % 20, watched=False) for number in range(300)]
    rows += [models.TVShow(user_id=user.id, title=f"Show {number}", year=2000 + number % 20, watched=False) for number in range(300)]
    wire = models.TVShow(user_id=user.id, title="the wire", year=2002, watched=False)
    db_session.add_all([*rows, wire])
    db_session.commit()
    # Started titles are listed first, so the one a guide covers is among the twelve sent back.
    db_session.add(models.ProgressCheckpoint(user_id=user.id, category="tv-shows", item_id=wire.id, unit="episode",
                                             season=1, position=3, revision=1))
    db_session.commit()
    binge.for_title("tv", "warm", None)
    calls = []
    real = title_pages.normalize

    def counted(title):
        calls.append(title)
        return real(title)

    title_pages.normalize, kept = counted, title_pages.normalize
    try:
        data = authenticated_client.get("/api/binge-calculator/mine").json()
    finally:
        title_pages.normalize = kept
    assert data["count"] == 601
    assert data["titles"][0]["title"] == "the wire" and data["titles"][0]["guide"] == "the-wire"
    assert not data["titles"][0]["typical"] and data["started"] == 1
    # A handful of clean-ups for each title. It was more than a hundred each: every name in every guide, twice.
    assert len(calls) < 601 * 8


def test_guide_pages_build_their_title_page_links_once_per_index(client, db_session, monkeypatch):
    index = [{"kind": "tv", "slug": "breaking-bad-2008", "base": "breaking-bad", "members": 3, "image": "https://img.example/bb.jpg"}]
    monkeypatch.setattr(title_search, "index", lambda db: index)
    monkeypatch.setitem(pages._details_cache, "index", None)
    built = []
    real = binge.saveable
    monkeypatch.setattr(binge, "saveable", lambda item: built.append(1) or real(item))
    first = pages._details(db_session)
    assert first == {"tv/breaking-bad-2008": {"url": "/titles/tv/breaking-bad-2008", "image": "https://img.example/bb.jpg"}}
    walked = len(built)
    assert walked > 30
    assert pages._details(db_session) is first and len(built) == walked
    assert 'href="/titles/tv/breaking-bad-2008"' in client.get("/binge-calculator/breaking-bad").text
    assert len(built) < walked + 5  # the page view reused it (the few calls are the page's own links and buttons)
    # A rebuilt index (every ten minutes) is a new list, and the links follow it.
    index = [{"kind": "tv", "slug": "the-wire-2002", "base": "the-wire", "members": 2, "image": None}]
    assert pages._details(db_session) == {"tv/the-wire-2002": {"url": "/titles/tv/the-wire-2002", "image": None}}


def test_search_titles_fit_and_still_give_the_answer(client):
    titles = {slug: pages.page_title(entry) for slug, entry in GUIDES.items()}
    assert len(set(titles.values())) == len(GUIDES)
    for slug, title in titles.items():
        assert len(title) <= pages.TITLE_ROOM, (slug, len(title))
        assert re.fullmatch(r"How long .+\? ((About )?[\d,.]+ hours( so far)?|\d+ h( \d+ min)?)", title), title
    assert titles["breaking-bad"] == "How long does it take to watch Breaking Bad? About 49 hours"
    assert titles["a-song-of-ice-and-fire"] == "How long to read A Song of Ice and Fire? About 148 hours"
    assert titles["fullmetal-alchemist-brotherhood"] == "How long to watch Fullmetal Alchemist: Brotherhood? 26 hours"
    assert titles["marvel-infinity-saga"].startswith("How long to watch the Marvel Infinity Saga? 49 h")
    html = client.get("/binge-calculator/the-stormlight-archive").text
    assert "<title>How long to read The Stormlight Archive? About 182 hours | OmniTrackr</title>" in html
    # The heading on the page keeps the full question.
    assert "<h1>How long does it take to read The Stormlight Archive?</h1>" in html
