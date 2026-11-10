"""The binge calculator (/binge-calculator) and its "how long does it take" guides (Nov 2026)."""
import json
import re
from datetime import datetime
from html import unescape
from pathlib import Path

import pytest

from app import binge_calculator as binge, funnel, in_order, models, title_metadata, title_pages, title_search
from app.auth import AUTH_COOKIE_NAME
from app.binge_guides import GUIDES
from app.routers import binge_calculator as pages

APP = Path(__file__).parents[1] / "app"


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def member(db_session, username="testuser"):
    return db_session.query(models.User).filter_by(username=username).one()


def numbers(text):
    return set(re.findall(r"\d[\d,]*", text))


# ---------------------------------------------------------------- the guides themselves

def test_every_guide_is_complete_and_hand_written():
    assert len(GUIDES) == 30
    assert list(binge.by_kind()) == list(binge.KIND_ORDER)
    assert sum(len(slugs) for slugs in binge.by_kind().values()) == len(GUIDES)
    for slug, entry in GUIDES.items():
        assert re.fullmatch(r"[a-z0-9-]{1,80}", slug)
        assert entry["kind"] in binge.KIND_ORDER and entry["name"]
        assert 60 <= len(entry["summary"]) <= 170, slug
        assert len(entry["lead"]) == 2 and len(entry["sections"]) == 2 and len(entry["faq"]) == 3, slug
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["reviewed"])
        assert binge.words(entry) >= binge.MIN_INDEX_WORDS and binge.is_indexable(entry), slug
        ids = [section_id for section_id, _, _ in entry["sections"]]
        assert all(re.fullmatch(r"[a-z-]{2,40}", section_id) for section_id in ids) and len(set(ids)) == 2, slug
        assert len(entry["see_also"]) == 3 and slug not in entry["see_also"], slug
        assert set(entry["see_also"]) <= set(GUIDES), slug
        if entry.get("in_order"):
            from app.in_order_guides import GUIDES as ORDERS
            assert entry["in_order"] in ORDERS, slug
        assert binge.core(entry), slug
        for part in entry["parts"]:
            assert part["name"] and binge.minutes(entry, part) > 0 and binge.count(part) >= 1, (slug, part["name"])
        saved = [binge.saveable(item)["id"] for item in binge.titles(entry)]
        assert saved and len(saved) == len(set(saved)), slug
        for item in binge.titles(entry):
            assert item["kind"] in title_pages.KINDS and 1900 < item["year"] < 2030, (slug, item["title"])


def test_the_prose_states_the_total_the_parts_add_up_to():
    # The headline figure is computed from the parts, so the written summary has to agree with it.
    for slug, entry in GUIDES.items():
        total = binge.totals(entry)
        said = numbers(entry["summary"])
        if entry["kind"] == "film":
            hours, rest = divmod(round(total["minutes"]), 60)
            assert {str(hours), str(rest)} <= said, slug
        else:
            assert pages._hours(total["minutes"]) in said, slug
        if entry["kind"] in ("tv", "anime"):
            assert f"{total['episodes']:,}" in said, slug
        if entry["kind"] == "book":
            assert str(round(total["audio"] / 60)) in said, slug


def test_totals_use_the_stated_reading_and_viewing_model():
    bad = GUIDES["breaking-bad"]
    assert binge.totals(bad) == {"minutes": 62 * 47, "parts": 5, "episodes": 62, "extras": 0}
    assert binge.days_at(62 * 47, 2) == 25 and binge.days_at(62 * 47, 1) == 49
    potter = binge.totals(GUIDES["harry-potter"])
    assert potter["parts"] == 7 and potter["pages"] == sum(binge.pages(part) for part in GUIDES["harry-potter"]["parts"])
    assert potter["minutes"] == pytest.approx(potter["words"] / binge.WORDS_PER_MINUTE)
    # 300 words a page at 40 pages an hour is the same 200 words a minute.
    assert binge.WORDS_PER_PAGE * binge.PAGES_PER_HOUR == binge.WORDS_PER_MINUTE * 60
    # Optional parts stay out of the headline, and the other version changes it.
    naruto = GUIDES["naruto-and-shippuden"]
    assert binge.totals(naruto)["episodes"] == 720 and binge.totals(naruto, alt=True)["episodes"] == 425
    assert binge.totals(naruto)["extras"] == 0 and len(naruto["parts"]) == 3
    rings = GUIDES["middle-earth-films"]
    assert binge.totals(rings)["minutes"] == 558 and binge.totals(rings, alt=True)["minutes"] == 726
    assert sum(binge.count(part) for part in GUIDES["one-piece"]["parts"]) == 1180


def test_planner_payload_is_one_small_row_per_part():
    plan = binge.planner(GUIDES["naruto-and-shippuden"])
    assert plan["slug"] == "naruto-and-shippuden" and plan["kind"] == "anime" and plan["alt"] == "Skip filler"
    assert plan["skip"] == 3 and [row["id"] for row in plan["parts"]] == ["0", "1", "2"]
    assert plan["parts"][0] == {"id": "0", "name": "Naruto", "unit": "episode", "n": 220, "min": 5060, "altN": 130, "altMin": 2990}
    assert plan["parts"][2]["optional"] is True and plan["parts"][2]["unit"] == "film"
    book = binge.planner(GUIDES["harry-potter"])["parts"][0]
    assert book["pages"] == 256 and book["audio"] > 0 and book["unit"] == "book"
    # Names written to sit mid-sentence are capitalised when shown alone.
    assert binge.planner(GUIDES["marvel-infinity-saga"])["name"] == "The Marvel Infinity Saga"
    assert binge.planner(GUIDES["friends"])["skip"] == 1


# ---------------------------------------------------------------- pages

def test_hub_is_public_indexable_and_lists_every_guide(client):
    response = client.get("/binge-calculator")
    assert response.status_code == 200
    html = response.text
    assert '<link rel="canonical" href="https://omnitrackr.xyz/binge-calculator">' in html
    assert 'content="index, follow' in html
    assert '"@type": "FAQPage"' in html
    assert "/static/binge-calculator.js" in html and "/static/ad-loader.js" in html
    assert " style=" not in html.split("<main", 1)[1]
    for slug, entry in GUIDES.items():
        assert f'<li class="bc-card" id="{slug}">' in html and f'href="/binge-calculator/{slug}"' in html
    # Each card carries its numbers, so the list reads without scripts.
    assert "62 episodes · about 49 hours" in html
    assert "data-binge-custom" in html and 'name="mode" value="date"' in html
    for kind in ("screen", "film", "book", "audio", "game"):
        assert f'name="kind" value="{kind}"' in html
    assert "data-binge-mine" not in html and 'href="/#signup"' in html


def test_guide_page_answers_the_question_without_an_account(client):
    response = client.get("/binge-calculator/breaking-bad")
    assert response.status_code == 200
    html = response.text
    assert '<meta name="robots" content="index, follow' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/binge-calculator/breaking-bad">' in html
    assert "<title>How long does it take to watch Breaking Bad? About 49 hours | OmniTrackr</title>" in html
    assert "How long does it take to watch Breaking Bad?</h1>" in html
    assert '"@type": "Article"' in html and '"@type": "FAQPage"' in html
    # The answer, the season table and the paces are in the HTML itself.
    assert 'id="answer"' in html and "Breaking Bad takes about 49 hours" in html
    assert html.count('class="bc-part') >= 5
    for days in (49, 25, 13):
        assert f"{days} days" in html
    entry = GUIDES["breaking-bad"]
    for _, heading, _ in entry["sections"]:
        assert heading in html
    for question, _ in entry["faq"]:
        assert question in html
    plan = json.loads(unescape(re.search(r'data-binge-plan="([^"]+)"', html).group(1)))
    assert plan == binge.planner(entry)
    # Saving works without an account and points at sign-up.
    assert 'data-guest-kind="tv" data-guest-slug="breaking-bad-2008"' in html
    assert "data-binge-guest-save" in html and "data-guest-bar" in html and "/static/guest-list.js" in html
    assert "/static/ad-loader.js" in html and "data-binge-track=" not in html
    assert html.count('href="/binge-calculator/') >= 3 and 'href="/binge-calculator"' in html
    assert "Cookie" in response.headers["vary"]
    assert " style=" not in html.split("<main", 1)[1]


def test_every_guide_page_renders(client):
    for slug, entry in GUIDES.items():
        response = client.get(f"/binge-calculator/{slug}")
        assert response.status_code == 200, slug
        assert binge.heading(entry) in response.text.replace("&#x27;", "'"), slug
        assert f'href="https://omnitrackr.xyz/binge-calculator/{slug}"' in response.text


def test_book_and_film_guides_show_their_own_options(client):
    potter = client.get("/binge-calculator/harry-potter").text
    assert 'name="how" value="listen"' in potter and 'name="speed"' in potter and 'name="seen"' not in potter
    assert potter.count("data-guest-kind=\"book\"") == 7 and "Save all 7 books to my list" in potter
    assert 'href="/in-order/harry-potter"' in potter
    rings = client.get("/binge-calculator/middle-earth-films").text
    assert 'name="alt"' in rings and "Extended editions" in rings and 'name="skip"' not in rings
    naruto = client.get("/binge-calculator/naruto-and-shippuden").text
    assert 'name="alt"' in naruto and 'name="skip"' in naruto and 'name="seen"' in naruto


def test_members_get_their_progress_panel_and_no_ads(client):
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    html = client.get("/binge-calculator/dune").text
    assert 'data-binge-track="dune"' in html and "data-binge-add" in html
    assert "data-guest-bar" not in html and "/static/guest-list.js" not in html
    assert "/static/ad-loader.js" not in html
    hub = client.get("/binge-calculator").text
    assert "data-binge-mine" in hub and "/static/ad-loader.js" not in hub


def test_unknown_guides_are_not_found(client, authenticated_client):
    assert client.get("/binge-calculator/not-a-guide").status_code == 404
    assert authenticated_client.get("/api/binge-calculator/not-a-guide/progress").status_code == 404
    assert authenticated_client.post("/api/binge-calculator/not-a-guide/add").status_code == 404


def test_a_short_guide_would_not_be_indexed(client, monkeypatch):
    monkeypatch.setattr(binge, "MIN_INDEX_WORDS", 100000)
    html = client.get("/binge-calculator/breaking-bad").text
    assert '<meta name="robots" content="noindex' in html
    assert "/binge-calculator/breaking-bad" not in client.get("/sitemap.xml").text


# ---------------------------------------------------------------- members

def test_member_endpoints_need_an_account(client):
    assert client.get("/api/binge-calculator/breaking-bad/progress").status_code == 401
    assert client.post("/api/binge-calculator/breaking-bad/add").status_code == 401
    assert client.get("/api/binge-calculator/mine").status_code == 401


def test_progress_unticks_what_the_member_has_finished(authenticated_client, db_session):
    user = member(db_session)
    db_session.add_all([
        # Saved under the short name the page uses, and under the US title.
        models.Book(user_id=user.id, title="Chamber of Secrets", author="J. K. Rowling", year=1998, read=True),
        models.Book(user_id=user.id, title="Harry Potter and the Sorcerer's Stone", author="J. K. Rowling", year=1997, read=True),
        models.Book(user_id=user.id, title="Harry Potter and the Prisoner of Azkaban", author="J. K. Rowling", year=1999, read=False),
    ])
    db_session.commit()
    progress = authenticated_client.get("/api/binge-calculator/harry-potter/progress").json()
    assert sorted(progress["done_parts"]) == ["0", "1"]
    assert progress["done"] == 2 and progress["tracked"] == 3 and progress["total"] == 7
    assert sorted(progress["missing"]) == ["3", "4", "5", "6"] and progress["watched"] is None


def test_progress_counts_episodes_from_the_members_place(authenticated_client, db_session):
    user = member(db_session)
    show = models.TVShow(user_id=user.id, title="Breaking Bad", year=2008, watched=False)
    db_session.add(show)
    db_session.commit()
    assert authenticated_client.get("/api/binge-calculator/breaking-bad/progress").json()["watched"] is None
    # No episode list has been looked up, so the guide's own season lengths place season 2 episode 6.
    db_session.add(models.ProgressCheckpoint(user_id=user.id, category="tv-shows", item_id=show.id, unit="episode",
                                             season=2, position=6, revision=1))
    db_session.commit()
    progress = authenticated_client.get("/api/binge-calculator/breaking-bad/progress").json()
    assert progress["watched"] == 7 + 6 and progress["tracked"] == 1 and progress["done"] == 0
    show.watched = True
    db_session.commit()
    done = authenticated_client.get("/api/binge-calculator/breaking-bad/progress").json()
    assert done["done"] == 1 and done["watched"] is None


def test_a_remake_with_the_same_title_is_not_counted(authenticated_client, db_session):
    user = member(db_session)
    db_session.add(models.TVShow(user_id=user.id, title="The Office", year=2001, watched=True))
    db_session.commit()
    assert authenticated_client.get("/api/binge-calculator/the-office/progress").json()["tracked"] == 0


def test_member_adds_the_series_without_touching_what_they_have(authenticated_client, db_session, monkeypatch):
    recorded = []
    monkeypatch.setattr(funnel, "record", lambda event, request=None: recorded.append(event))
    user = member(db_session)
    db_session.add(models.Movie(user_id=user.id, title="The Fellowship of the Ring", year=2001, watched=True, rating=9.5))
    db_session.commit()
    body = authenticated_client.post("/api/binge-calculator/middle-earth-films/add").json()
    assert len(body["added"]) == 2 and len(body["existing"]) == 1
    assert body["progress"]["missing"] == [] and body["progress"]["tracked"] == 3 and body["progress"]["done"] == 1
    assert recorded == ["binge_saved"]
    kept = db_session.query(models.Movie).filter_by(user_id=user.id, title="The Fellowship of the Ring").one()
    assert kept.watched and kept.rating == 9.5
    towers = db_session.query(models.Movie).filter_by(user_id=user.id, year=2002).one()
    assert "Two Towers" in towers.title and not towers.watched and towers.rating is None
    # The optional Hobbit films are left out, and adding again creates nothing.
    assert db_session.query(models.Movie).filter_by(user_id=user.id).count() == 3
    again = authenticated_client.post("/api/binge-calculator/middle-earth-films/add").json()
    assert again["added"] == [] and recorded == ["binge_saved"]
    assert db_session.query(models.Movie).filter_by(user_id=user.id).count() == 3


def test_a_guest_saved_series_moves_into_the_new_library(authenticated_client, db_session):
    response = authenticated_client.post("/api/guest-list/import", json={"items": [
        {"kind": "tv", "slug": "succession-2018"}, {"kind": "book", "slug": "the-way-of-kings-2010"}]})
    assert sorted(item["title"] for item in response.json()["added"]) == ["Succession", "The Way of Kings"]
    book = db_session.query(models.Book).filter_by(title="The Way of Kings").one()
    assert book.author == "Brandon Sanderson" and not book.read
    assert binge.find("tv", "not-a-show") is None


def test_what_you_have_left_uses_guide_lengths_and_the_members_place(authenticated_client, db_session):
    user = member(db_session)
    empty = authenticated_client.get("/api/binge-calculator/mine").json()
    assert empty["count"] == 0 and empty["titles"] == []
    show = models.TVShow(user_id=user.id, title="Breaking Bad", year=2008, watched=False)
    db_session.add_all([
        show,
        models.TVShow(user_id=user.id, title="The Wire", year=2002, watched=True),
        models.Movie(user_id=user.id, title="Some Unknown Film", year=2020, watched=False),
        models.Book(user_id=user.id, title="Harry Potter and the Goblet of Fire", author="J. K. Rowling", year=2000, read=False),
    ])
    db_session.commit()
    db_session.add(models.ProgressCheckpoint(user_id=user.id, category="tv-shows", item_id=show.id, unit="episode",
                                             season=1, position=7, revision=1))
    db_session.commit()
    data = authenticated_client.get("/api/binge-calculator/mine").json()
    assert data["count"] == 3 and data["started"] == 1 and data["typical"] == 1
    by_title = {row["title"]: row for row in data["titles"]}
    assert "The Wire" not in by_title
    bad = by_title["Breaking Bad"]
    assert bad["started"] and bad["guide"] == "breaking-bad" and bad["minutes"] == (62 - 7) * 47 and bad["percent"] == 11
    assert data["titles"][0]["title"] == "Breaking Bad"  # what is in progress comes first
    goblet = by_title["Harry Potter and the Goblet of Fire"]
    assert goblet["minutes"] == round(190637 / binge.WORDS_PER_MINUTE) and not goblet["typical"] and goblet["guide"] == "harry-potter"
    assert by_title["Some Unknown Film"]["typical"] and by_title["Some Unknown Film"]["guide"] is None
    assert data["minutes"] == sum(row["minutes"] for row in data["titles"])


# ---------------------------------------------------------------- lookups and links

def test_lookup_prefers_a_guides_checked_numbers(client, db_session):
    key = title_metadata.cache_key("tv", title_pages.normalize("Breaking Bad"), 2008)
    db_session.add(models.TitleMetadata(key=key, status="ok", fetched_at=datetime.utcnow(),
                                        data=json.dumps({"facts": [{"label": "Episode length", "value": "45 min"}]})))
    db_session.commit()
    data = client.get("/api/binge-calculator/length", params={"kind": "tv", "title": "Breaking Bad", "year": 2008}).json()
    assert data["episodes"] == 62 and data["minutes"] == 47 and data["guide"] == "breaking-bad"
    film = client.get("/api/binge-calculator/length", params={"kind": "movie", "title": "The Avengers", "year": 2012}).json()
    assert film["minutes"] == 143 and film["guide"] == "marvel-infinity-saga"
    book = client.get("/api/binge-calculator/length", params={"kind": "book", "title": "Dune", "year": 1965}).json()
    assert book["pages"] == binge.pages(GUIDES["dune"]["parts"][0]) and book["guide"] == "dune"
    other = client.get("/api/binge-calculator/length", params={"kind": "tv", "title": "Nothing Cached"}).json()
    assert other["guide"] is None and other["episodes"] is None
    assert client.get("/api/binge-calculator/length", params={"kind": "album", "title": "Arrival"}).status_code == 400


def test_titles_match_under_the_names_members_use():
    assert binge.for_title("anime", "Naruto: Shippuden", 2007) == "naruto-and-shippuden"
    assert binge.known_length("anime", "Naruto Shippuden", 2007)["episodes"] == 500
    assert binge.known_length("anime", "Naruto", 2002) == {"total": 220 * 23, "episodes": 220, "seasons": None}
    assert binge.for_title("tv", "The Office (US)", 2005) == "the-office"
    assert binge.for_title("tv", "The Office", 2001) is None
    assert binge.for_title("movie", "Star Wars", 1977) == "star-wars-films"
    assert binge.for_title("book", "Breaking Bad", 2008) is None
    assert binge.known_length("tv", "Severance", 2022) == {}
    # Every title a guide names resolves back to that guide.
    for slug, entry in GUIDES.items():
        for item in binge.titles(entry):
            assert binge.for_title(item["kind"], item["title"], item["year"]) is not None, (slug, item["title"])
            assert in_order.names(item)


def test_title_pages_link_to_the_guide_or_the_calculator():
    from app.routers.titles import _binge_link

    class Guided:
        kind, title, year = "tv", "Breaking Bad", 2008

    assert 'href="/binge-calculator/breaking-bad"' in _binge_link(Guided())

    class Other:
        kind, title, year = "tv", "Severance & Co", 2022

    link = _binge_link(Other())
    assert 'href="/binge-calculator?lookup=tv&amp;title=Severance+%26+Co&amp;year=2022"' in link
    assert _binge_link(Other(), guide_only=True) == ""


def test_guides_are_in_the_sitemap_ad_allowlist_and_funnel(client):
    sitemap = client.get("/sitemap.xml").text
    assert "https://omnitrackr.xyz/binge-calculator</loc>" in sitemap
    for slug in GUIDES:
        assert f"https://omnitrackr.xyz/binge-calculator/{slug}</loc>" in sitemap
    loader = (APP / "static" / "ad-loader.js").read_text(encoding="utf-8")
    assert r"/^\/binge-calculator(\/[a-z0-9-]{1,80})?$/" in loader
    assert "/binge-calculator/breaking-bad" in client.get("/llms.txt").text
    names = [name for name, _ in funnel.GUEST]
    assert "binge_planned" in names and "binge_saved" in names
    assert {"binge_planned", "binge_saved"} <= set(funnel.CLIENT_EVENTS)
    script = (APP / "static" / "binge-calculator.js").read_text(encoding="utf-8")
    assert "report('binge_planned')" in script and "report('binge_saved')" in script
