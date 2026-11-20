"""Release guides (/new-releases): hand-written picks from a month's or a season's new releases (Nov 2026)."""
import re
from datetime import date

import pytest

from app import editorial_index, new_releases, pick, title_pages, title_search
from app.auth import AUTH_COOKIE_NAME
from app.release_guides import GUIDES


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def words(entry):
    texts = entry["lead"] + entry["plan"] + [title + " " + text for title, text in entry["also"]]
    texts += [paragraph for section in entry["sections"] for paragraph in section["intro"]]
    texts += [" ".join((item["why"], item["note"], item.get("first", ""), item["caveat"]))
              for item in new_releases.picks(entry)]
    return sum(len(text.split()) for text in texts)


def test_every_guide_is_complete_and_substantial():
    for slug, entry in GUIDES.items():
        for field in ("published", "reviewed", "starts", "ends"):
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry[field]), (slug, field)
        assert entry["starts"] <= entry["ends"] and entry["published"] <= entry["reviewed"]
        assert 60 <= len(entry["summary"]) <= 170 and entry["search_title"] and entry["name"] and entry["period"]
        assert len(entry["lead"]) >= 2 and entry["plan"] and entry["plan_heading"] and len(entry["sources"]) >= 8
        assert words(entry) >= 2500, slug
        formats = [section["format"] for section in entry["sections"]]
        assert all(fmt in new_releases.FORMAT_ORDER for fmt in formats)
        ids = [new_releases.section_id(section) for section in entry["sections"]]
        assert len(ids) == len(set(ids)), slug
        if entry.get("focus"):
            # A one-format guide (an anime season) splits its picks into several groups of that format.
            assert set(formats) == {entry["focus"]} and len(formats) >= 3, slug
            assert all(section.get("id") and section.get("label") for section in entry["sections"]), slug
        else:
            assert len(formats) == len(set(formats)) >= 4
        for label, url in entry["sources"]:
            assert label and url.startswith("https://")
        for label, href in entry["related"]:
            assert label and href.startswith("/")
        seen = set()
        for section in entry["sections"]:
            assert section["heading"] and section["intro"] and len(section["picks"]) >= 2
            for item in section["picks"]:
                assert item["kind"] in title_pages.KINDS
                assert item["title"] and item["released"] and item["why"] and item["note"] and item["caveat"]
                assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["date"]), item["title"]
                # Every pick is out (or out again, for a returning series) by the end of the guide's stretch.
                assert item["date"] <= entry["ends"], item["title"]
                assert 1950 < item["year"] <= int(entry["ends"][:4])
                assert (item["creator"] is None) == (title_pages.KINDS[item["kind"]][4] is None), item["title"]
                assert bool(item.get("first_link")) == bool(item.get("first_label"))
                key = (item["kind"], title_pages.slugify(item["title"]))
                assert key not in seen
                seen.add(key)


def test_guides_publish_on_their_date():
    assert new_releases.published(date(2026, 10, 31)) == {}
    live = new_releases.published(date(2026, 11, 1))
    assert set(live) == {"november-2026", "winter-2026-27"}
    assert "winter-2027-anime" in new_releases.published(date(2026, 11, 4))
    assert "winter-2027-tv" not in new_releases.published(date(2026, 11, 19))
    assert "winter-2027-tv" in new_releases.published(date(2026, 11, 20))
    assert "winter-2027-games" not in new_releases.published(date(2026, 11, 19))
    assert "winter-2027-games" in new_releases.published(date(2026, 11, 20))
    for slug in ("winter-2027-movies", "winter-2027-books"):
        assert slug not in new_releases.published(date(2026, 11, 19))
        assert slug in new_releases.published(date(2026, 11, 20))
    assert new_releases.current(date(2026, 11, 15)) == "november-2026"
    # The anime season guide is newer and covers January too, but Release Radar keeps pointing at the all-format guide.
    assert new_releases.current(date(2027, 1, 20)) == "winter-2026-27"
    assert new_releases.current(date(2027, 3, 20)) != "winter-2027-anime"
    # Once every stretch has passed, the newest guide still counts as current.
    assert new_releases.current(date(2027, 6, 1)) in live


def test_every_pick_can_be_saved_but_is_only_suggested_once_out():
    for entry in GUIDES.values():
        for item in new_releases.picks(entry):
            pooled = new_releases.pool_entry(item)
            assert pooled is not None, item["title"]
            assert pick.find_id(pooled["id"]) is pooled
    gta = pick.find("game", "grand-theft-auto-vi-2026")
    assert gta["source_url"] == "/new-releases/november-2026#pick-grand-theft-auto-vi"
    assert gta["out"] == "2026-11-19"
    assert not pick.is_available(gta, date(2026, 11, 18))
    assert pick.is_available(gta, date(2026, 11, 19))
    assert gta not in pick.candidates("game", today=date(2026, 11, 1))
    assert gta in pick.candidates("game", today=date(2026, 12, 1))
    # Picks from the other guides have no release date and are always available.
    assert all(pick.is_available(entry, date(2000, 1, 1)) for entry in pick.pool() if not entry["out"])


def test_guide_page_reads_completely_without_an_account(client):
    response = client.get("/new-releases/november-2026")
    assert response.status_code == 200
    html = response.text
    assert '<meta name="robots" content="index, follow' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/new-releases/november-2026">' in html
    assert "<h1>November 2026 releases worth your time</h1>" in html
    entry = GUIDES["november-2026"]
    for item in new_releases.picks(entry):
        assert f'id="{new_releases.anchor_id(item)}"' in html
    assert html.count("Save to my list") == len(new_releases.picks(entry))
    for section in entry["sections"]:
        assert f'id="{new_releases.section_id(section)}"' in html
    assert "Also on the calendar" in html and "A plan for the month" in html and "How we chose" in html
    assert "Sources we checked" in html and "with AI assistance" in html
    assert 'href="/in-order/hunger-games"' in html and 'href="/new-releases/winter-2026-27"' in html
    assert "/static/new-releases.css" in html and "/static/ad-loader.js" in html
    assert '"@type": "Article"' in html and '"ItemList"' in html


def test_members_get_add_buttons_and_no_ads(client):
    client.cookies.set(AUTH_COOKIE_NAME, "anything")
    html = client.get("/new-releases/winter-2026-27").text
    client.cookies.clear()
    assert html.count("Add to my library") == len(new_releases.picks(GUIDES["winter-2026-27"]))
    assert "/static/ad-loader.js" not in html and "Save to my list" not in html


@pytest.mark.parametrize("path", ["/new-releases/october-2026", "/new-releases/winter-2027"])
def test_unknown_guides_are_not_found(client, path):
    assert client.get(path).status_code == 404


def test_hub_lists_every_live_guide(client):
    html = client.get("/new-releases").text
    for slug, entry in new_releases.published().items():
        assert f'href="{new_releases.path(slug)}"' in html
        assert entry["name"] in html
    assert 'href="/release-radar"' in html


def test_every_related_link_resolves(client):
    for entry in GUIDES.values():
        for _, href in entry["related"]:
            assert client.get(href).status_code == 200, href
        for item in new_releases.picks(entry):
            if item.get("first_link"):
                assert client.get(item["first_link"]).status_code == 200, item["first_link"]


def test_sitemap_site_map_menu_and_guide_index_include_the_guides(client):
    sitemap = client.get("/sitemap.xml").text
    assert "https://omnitrackr.xyz/new-releases</loc>" in sitemap
    for slug in new_releases.published():
        assert f"https://omnitrackr.xyz/new-releases/{slug}</loc>" in sitemap
    site_map = client.get("/site-map").text
    assert 'href="/new-releases/november-2026"' in site_map
    assert any(piece["section"] == "new-releases" for piece in editorial_index.entries())
    assert 'href="/new-releases"' in client.get("/best-of/2026/movies").text


def test_release_radar_points_at_this_months_guide():
    from app.routers.release_radar import _guide_note

    note = _guide_note()
    slug = new_releases.current()
    assert f'href="/new-releases/{slug}"' in note


def test_anime_season_guide_groups_its_picks(client):
    entry = GUIDES["winter-2027-anime"]
    html = client.get("/new-releases/winter-2027-anime").text
    assert f"<h1>{entry['name']}</h1>" in html and "ANIME SEASON GUIDE" in html
    for section in entry["sections"]:
        assert f'id="{new_releases.section_id(section)}"' in html
        assert f'href="#{new_releases.section_id(section)}">{section["label"]}</a>' in html
    assert f"{len(new_releases.picks(entry))} anime picks in {len(entry['sections'])} groups." in html
    # Its own note on how the picks were chosen replaces the standard one.
    assert entry["method"][0][:60] in html and "left out anything without a firm date" not in html
    # The broad winter guide links here, and the anime picks from it are not repeated.
    assert 'href="/new-releases/winter-2027-anime"' in client.get("/new-releases/winter-2026-27").text
    winter = {title_pages.slugify(item["title"]) for item in new_releases.picks(GUIDES["winter-2026-27"])}
    assert not winter & {title_pages.slugify(item["title"]) for item in new_releases.picks(entry)}
    assert 'href="/new-releases/winter-2027-anime"' in client.get("/anime-tracker").text
    # On the hub, this month's all-format guide comes first and the anime guide counts shows, not releases.
    hub = client.get("/new-releases").text
    assert hub.index("This month") < hub.index("Winter 2027 anime season")
    assert f"{len(new_releases.picks(entry))} anime, including Historie" in hub


def test_tv_season_guide_groups_its_picks(client):
    entry = GUIDES["winter-2027-tv"]
    total = len(new_releases.picks(entry))
    html = client.get("/new-releases/winter-2027-tv").text
    assert f"<h1>{entry['name']}</h1>" in html and "TV PREMIERES GUIDE" in html
    for section in entry["sections"]:
        assert f'href="#{new_releases.section_id(section)}">{section["label"]}</a>' in html
    assert f"{total} TV picks in {len(entry['sections'])} groups." in html
    assert html.count("Save to my list") == total
    assert entry["method"][0][:60] in html and "left out anything without a firm date" not in html
    # A month-only date reads as the month, not as the first of it.
    assert "Out January 2027" in html and "Out January 1<" not in html
    # Shows already written up in the broad winter guide are only mentioned here, not repeated as picks.
    winter = {title_pages.slugify(item["title"]) for item in new_releases.picks(GUIDES["winter-2026-27"])
              if item["kind"] == "tv"}
    assert not winter & {title_pages.slugify(item["title"]) for item in new_releases.picks(entry)}
    assert any(title.startswith("Neuromancer") for title, _ in entry["also"])
    assert 'href="/new-releases/winter-2027-tv"' in client.get("/tv-show-tracker").text
    # Never the guide Release Radar points at, and its hub card counts series.
    assert new_releases.current(date(2027, 1, 20)) != "winter-2027-tv"
    hub = client.get("/new-releases").text
    assert f"{total} series, including The Pitt" in hub
    assert hub.index("This month") < hub.index('nr-card__label">Winter 2027 TV premieres<')


def test_games_season_guide_groups_its_picks(client):
    entry = GUIDES["winter-2027-games"]
    total = len(new_releases.picks(entry))
    html = client.get("/new-releases/winter-2027-games").text
    assert f"<h1>{entry['name']}</h1>" in html and "GAMES RELEASE GUIDE" in html
    for section in entry["sections"]:
        assert f'href="#{new_releases.section_id(section)}">{section["label"]}</a>' in html
    assert f"{total} game picks in {len(entry['sections'])} groups." in html
    assert html.count("Save to my list") == total
    assert entry["method"][0][:60] in html
    # Two picks only have a month so far.
    assert html.count("Out March 2027") == 2 and "Out March 1<" not in html
    # Games already written up in the broad winter guide are only listed here, not repeated as picks.
    winter = {title_pages.slugify(item["title"]) for item in new_releases.picks(GUIDES["winter-2026-27"])
              if item["kind"] == "game"}
    assert not winter & {title_pages.slugify(item["title"]) for item in new_releases.picks(entry)}
    assert any(title.startswith("Fable") for title, _ in entry["also"])
    # A delayed game is named in the list but is not a pick.
    assert not any("Laufey" in item["title"] for item in new_releases.picks(entry))
    assert 'href="/new-releases/winter-2027-games"' in client.get("/game-tracker").text
    assert new_releases.current(date(2027, 2, 10)) != "winter-2027-games"
    hub = client.get("/new-releases").text
    assert f"{total} games, including Stranger Than Heaven" in hub
    assert hub.index("This month") < hub.index('nr-card__label">Winter 2027 games<')


def test_movies_season_guide_groups_its_picks(client):
    entry = GUIDES["winter-2027-movies"]
    total = len(new_releases.picks(entry))
    html = client.get("/new-releases/winter-2027-movies").text
    assert f"<h1>{entry['name']}</h1>" in html and "MOVIES RELEASE GUIDE" in html
    for section in entry["sections"]:
        assert f'href="#{new_releases.section_id(section)}">{section["label"]}</a>' in html
    assert f"{total} film picks in {len(entry['sections'])} groups." in html
    assert html.count("Save to my list") == total
    assert entry["method"][0][:60] in html
    # Films already written up in the broad winter guide are only listed here, not repeated as picks.
    winter = {title_pages.slugify(item["title"]) for item in new_releases.picks(GUIDES["winter-2026-27"])
              if item["kind"] == "movie"}
    assert not winter & {title_pages.slugify(item["title"]) for item in new_releases.picks(entry)}
    assert any(title.startswith("Narnia") for title, _ in entry["also"])
    assert 'href="/in-order/godzilla"' in html
    assert 'href="/new-releases/winter-2027-movies"' in client.get("/movie-tracker").text
    assert new_releases.current(date(2027, 2, 10)) != "winter-2027-movies"
    hub = client.get("/new-releases").text
    assert f"{total} films, including The Beekeeper 2" in hub
    assert hub.index("This month") < hub.index('nr-card__label">Winter 2027 movies<')


def test_books_season_guide_groups_its_picks(client):
    entry = GUIDES["winter-2027-books"]
    total = len(new_releases.picks(entry))
    html = client.get("/new-releases/winter-2027-books").text
    assert f"<h1>{entry['name']}</h1>" in html and "BOOKS RELEASE GUIDE" in html
    for section in entry["sections"]:
        assert f'href="#{new_releases.section_id(section)}">{section["label"]}</a>' in html
    assert f"{total} book picks in {len(entry['sections'])} groups." in html
    assert html.count("Save to my list") == total
    assert entry["method"][0][:60] in html
    # Every book has a firm US day, and it is a Tuesday, the usual US publishing day.
    assert not any(item.get("month_only") for item in new_releases.picks(entry))
    assert all(date.fromisoformat(item["date"]).weekday() == 1 for item in new_releases.picks(entry))
    winter = {title_pages.slugify(item["title"]) for item in new_releases.picks(GUIDES["winter-2026-27"])
              if item["kind"] == "book"}
    assert not winter & {title_pages.slugify(item["title"]) for item in new_releases.picks(entry)}
    assert any(title.startswith("A Court of Forgotten Melody") for title, _ in entry["also"])
    assert 'href="/new-releases/winter-2027-books"' in client.get("/book-tracker").text
    assert new_releases.current(date(2027, 2, 10)) != "winter-2027-books"
    hub = client.get("/new-releases").text
    assert f"{total} books, including In One Brief Moment All Eternity" in hub
    assert hub.index("This month") < hub.index('nr-card__label">Winter 2027 books<')


def test_season_guide_picks_save_as_themselves():
    # Pick for me keeps the first copy of a title it sees, so a new film or book must not be shadowed by an
    # older title of the same name and kind (The Nightingale is also a 2018 film): it would save the wrong year.
    for slug in ("winter-2027-movies", "winter-2027-books"):
        for item in new_releases.picks(GUIDES[slug]):
            pooled = new_releases.pool_entry(item)
            assert pooled["year"] == item["year"], (slug, item["title"])
            assert pooled["out"] == item["date"], (slug, item["title"])
