"""Best-of-the-year lists (/best-of): hand-written picks of each year's best new titles (Oct 2026; nine formats and the
year-end hub since Nov 2026)."""
import re

import pytest

from app import best_of, editorial_index, models, pick, title_pages, title_search
from app.best_of_guides import GUIDES, YEARS


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def words(entry):
    texts = entry["lead"] + entry["start"] + entry["coming"] + [title + " " + text for title, text in entry["also"]]
    texts += [item["why"] + " " + item["note"] + " " + item["caveat"] for item in entry["picks"]]
    return sum(len(text.split()) for text in texts)


def test_every_list_is_complete_and_substantial():
    assert {GUIDES[slug]["format"] for slug in best_of.for_year(2026)} == set(best_of.FORMAT_ORDER)
    for slug, entry in GUIDES.items():
        assert slug == f"{entry['year']}-{entry['format']}"
        assert entry["format"] in best_of.FORMAT_ORDER and entry["kind"] in title_pages.KINDS
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["reviewed"])
        assert 60 <= len(entry["summary"]) <= 170 and entry["search_title"] and entry["name"]
        assert len(entry["lead"]) >= 2 and entry["start"] and len(entry["sources"]) >= 5
        assert 7 <= len(entry["picks"]) <= 10
        assert words(entry) >= 1000, slug
        for label, url in entry["sources"]:
            assert label and url.startswith("https://")
        seen = set()
        for item in entry["picks"]:
            assert item["kind"] == entry["kind"], item["title"]
            assert item["title"] and item["released"] and item["why"] and item["note"] and item["caveat"]
            # Returning shows are filed under their first season; festival films under their premiere.
            assert 2000 < item["year"] <= entry["year"]
            assert (item["creator"] is None) == (title_pages.KINDS[item["kind"]][4] is None)
            if item.get("link"):
                assert item["link"][1].startswith("https://")
            key = title_pages.slugify(item["title"])
            assert key not in seen
            seen.add(key)


def test_every_pick_can_be_saved():
    for slug, entry in GUIDES.items():
        for item in entry["picks"]:
            pooled = best_of.pool_entry(item)
            assert pooled is not None, item["title"]
            if item["kind"] in best_of.EXTRA_KINDS:
                # Manga, podcasts and audiobooks save straight to their tracker, never through Pick for me.
                assert pick.find_id(pooled["id"]) is None
                assert best_of.find_extra(item["kind"], pooled["slug"]) == (pooled["browse_kind"], pooled)
            else:
                assert pick.find_id(pooled["id"]) is pooled
    # A pick only these lists recommend keeps the list as its source and links to the pick.
    heron = pick.find("movie", "blue-heron-2025")
    assert heron["source_label"] == "The best movies of 2026"
    assert heron["source_url"] == "/best-of/2026/movies#pick-blue-heron"


def test_list_page_reads_completely_without_an_account(client):
    response = client.get("/best-of/2026/movies")
    assert response.status_code == 200
    html = response.text
    assert '<meta name="robots" content="index, follow' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/best-of/2026/movies">' in html
    assert "<title>Best movies of 2026: 9 films" in html
    assert "<h1>The best movies of 2026</h1>" in html
    assert "Also worth a look" in html and "Still to come in 2026" in html and "How we chose" in html
    assert "Sources we checked" in html and 'href="https://www.metacritic.com/' in html
    for item in GUIDES["2026-movies"]["picks"]:
        assert f'id="pick-{title_pages.slugify(item["title"])}"' in html
    assert html.count("Save to my list") == len(GUIDES["2026-movies"]["picks"])
    assert 'data-guest-kind="movie" data-guest-slug="project-hail-mary-2026"' in html
    assert "/static/guest-list.js" in html and "/static/if-you-liked.js" in html and "/static/best-of.css" in html
    assert "/static/ad-loader.js" in html
    assert '"@type": "Article"' in html and '"ItemList"' in html
    # The other formats, the hub and the related guides are linked.
    for other in ("tv", "anime", "games", "books", "music", "manga", "podcasts", "audiobooks"):
        assert f'href="/best-of/2026/{other}"' in html
    assert 'href="/best-of"' in html and 'href="/if-you-liked/interstellar"' in html
    assert "Cookie" in response.headers["vary"]


def test_lists_without_extras_skip_those_sections(client):
    html = client.get("/best-of/2026/tv").text
    assert 'id="also"' not in html and 'id="coming"' not in html
    assert 'href="#also"' not in html and 'href="#coming"' not in html


def test_members_get_add_buttons_and_no_ads(authenticated_client):
    html = authenticated_client.get("/best-of/2026/games").text
    assert html.count("data-liked-add=") == len(GUIDES["2026-games"]["picks"])
    assert "data-guest-bar" not in html and "/static/guest-list.js" not in html
    assert "/static/ad-loader.js" not in html
    assert "None of these 9 are in your library yet" in html


def test_an_unrecognised_cookie_gets_the_visitor_page(client):
    client.cookies.set("omnitrackr_session", "anything")
    html = client.get("/best-of/2026/games").text
    assert "Save to my list" in html and "/static/ad-loader.js" in html


@pytest.mark.parametrize("path", ["/best-of/2026/comics", "/best-of/1999/movies", "/best-of/1999"])
def test_unknown_lists_are_not_found(client, path):
    assert client.get(path).status_code == 404


def test_year_path_points_at_the_hub(client):
    response = client.get("/best-of/2026", follow_redirects=False)
    assert response.status_code == 301 and response.headers["location"] == "/best-of"


def test_hub_lists_every_guide(client):
    response = client.get("/best-of")
    assert response.status_code == 200
    for slug in GUIDES:
        assert f'href="{best_of.path(slug)}"' in response.text
    assert '<meta name="robots" content="index, follow' in response.text
    assert "Cookie" in response.headers["vary"]


def test_every_related_link_resolves(client):
    for entry in GUIDES.values():
        for _, href in entry["related"]:
            assert client.get(href).status_code == 200, href


def test_sitemap_site_map_and_guide_index_include_the_lists(client):
    sitemap = client.get("/sitemap.xml").text
    assert "<loc>https://omnitrackr.xyz/best-of</loc>" in sitemap
    for slug, entry in GUIDES.items():
        assert f"<loc>https://omnitrackr.xyz{best_of.path(slug)}</loc><lastmod>{entry['reviewed']}</lastmod>" in sitemap
    assert 'href="/best-of/2026/books"' in client.get("/site-map").text
    sections = {piece["section"] for piece in editorial_index.entries()}
    assert "best-of" in sections
    assert 'href="/best-of"' in client.get("/about").text


NEW_FORMATS = {"music": "album", "manga": "manga", "podcasts": "podcast", "audiobooks": "audiobook"}


@pytest.mark.parametrize("fmt, kind", NEW_FORMATS.items())
def test_the_four_new_formats_read_like_the_others(client, fmt, kind):
    entry = GUIDES[f"2026-{fmt}"]
    assert entry["kind"] == kind and entry["published"] == "2026-11-09"
    html = client.get(f"/best-of/2026/{fmt}").text
    assert f"<h1>{entry['name']}</h1>" in html
    assert html.count("Save to my list") == len(entry["picks"])
    assert f'data-guest-kind="{kind}"' in html
    assert "First published November 9, 2026" in html and "Sources we checked" in html


def test_audiobook_picks_show_narrator_and_length(client):
    html = client.get("/best-of/2026/audiobooks").text
    assert "read by Alfred Molina · 13 hr 31 min" in html
    assert "read by Seth Numrich · 4 hr 15 min" in html


def test_podcast_picks_link_to_the_show_not_a_shop(client, monkeypatch):
    monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", "omnitrackr-20")
    html = client.get("/best-of/2026/podcasts").text
    assert "https://podcasts.apple.com/us/podcast/city-of-lights/id1867051800" in html
    assert "amazon.com" not in html
    assert "each show&#x27;s own page, not shops" in html


def test_shop_links_only_when_affiliate_links_are_on(client, monkeypatch):
    assert "amazon.com" not in client.get("/best-of/2026/music").text
    monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", "omnitrackr-20")
    html = client.get("/best-of/2026/music").text
    assert html.count('rel="sponsored noopener noreferrer"') == len(GUIDES["2026-music"]["picks"])
    assert "As an Amazon Associate" in html
    # TV and anime live on streaming services, so they never get shop links.
    assert "amazon.com" not in client.get("/best-of/2026/tv").text


def test_members_save_manga_podcasts_and_audiobooks_through_best_of_add(authenticated_client, db_session):
    html = authenticated_client.get("/best-of/2026/audiobooks").text
    assert html.count('data-liked-endpoint="/api/best-of/add"') == len(GUIDES["2026-audiobooks"]["picks"])
    assert 'data-liked-endpoint' not in authenticated_client.get("/best-of/2026/music").text
    vigil = best_of.pool_entry(GUIDES["2026-audiobooks"]["picks"][0])
    response = authenticated_client.post("/api/best-of/add", json={"id": vigil["id"]})
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "created" and "library_category=audiobooks" in response.json()["library_url"]
    record = db_session.query(models.Audiobook).filter_by(title="Vigil").one()
    assert record.author == "George Saunders" and record.length_hours == 5.53 and not record.listened
    again = authenticated_client.post("/api/best-of/add", json={"id": vigil["id"]})
    assert again.json()["state"] == "existing"
    assert db_session.query(models.Audiobook).filter_by(title="Vigil").count() == 1
    # Once saved, the list says so instead of offering the button again.
    html = authenticated_client.get("/best-of/2026/audiobooks").text
    assert "In your library ✓" in html
    assert "Of these 8, 1 is in your library, not finished yet." in html


def test_best_of_add_refuses_unknown_and_pick_for_me_ids(authenticated_client):
    assert authenticated_client.post("/api/best-of/add", json={"id": "manga/not-a-pick"}).status_code == 404
    assert authenticated_client.post("/api/best-of/add", json={"id": "movie/project-hail-mary-2026"}).status_code == 404


def test_best_of_add_needs_an_account(client):
    assert client.post("/api/best-of/add", json={"id": "manga/cocoon-2009"}).status_code == 401


def test_hub_scorecard_counts_finished_picks(authenticated_client, db_session):
    user = db_session.query(models.User).first()
    db_session.add(models.Movie(user_id=user.id, title="Project Hail Mary", director="Phil Lord", year=2026, watched=True))
    db_session.add(models.Manga(user_id=user.id, title="Cocoon", author="Machiko Kyō", year=2009, read=True))
    db_session.add(models.Book(user_id=user.id, title="Kin", author="Tayari Jones", year=2026, read=False))
    db_session.commit()
    total = sum(len(entry["picks"]) for entry in GUIDES.values())
    html = authenticated_client.get("/best-of").text
    assert f"2 of {total} finished" in html
    assert "and 1 more is waiting in your library" in html
    assert "1 of 9 finished" in html  # the movies tile
    movies = authenticated_client.get("/best-of/2026/movies").text
    assert "Watched ✓" in movies and "Of these 9, you have finished 1." in movies
    assert "Read ✓" in authenticated_client.get("/best-of/2026/manga").text


def test_hub_reads_as_a_year_end_edition(client):
    html = client.get("/best-of").text
    assert "YEAR-END EDITION" in html and "If you only get to one from each" in html
    for fmt, title, _ in YEARS[2026]["nine"]:
        item = next(item for item in GUIDES[f"2026-{fmt}"]["picks"] if item["title"] == title)
        assert f'href="{best_of.path("2026-" + fmt)}#{best_of.anchor(item)}"' in html
    # The hub's own card is its one sign-up prompt, so the generic one at the foot of the page is left out.
    assert "How many of these" in html and "Start counting, free" in html
    assert 'href="/#signup">Start counting, free' in html and "data-site-join" not in html
    assert "/static/ad-loader.js" not in html


def test_guest_saves_of_new_formats_import_after_sign_up(authenticated_client, db_session):
    cocoon = best_of.pool_entry(next(item for item in GUIDES["2026-manga"]["picks"] if item["title"] == "Cocoon"))
    assert best_of.find_extra("movie", "project-hail-mary-2026") is None
    response = authenticated_client.post("/api/guest-list/import", json={"items": [{"kind": "manga", "slug": cocoon["slug"]}]})
    assert response.status_code == 200, response.text
    record = db_session.query(models.Manga).filter_by(title="Cocoon").one()
    assert record.author == "Machiko Kyō" and record.year == 2009
