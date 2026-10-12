"""October SEO sweep: share tags on the newer public pages, homepage site identity for Google,
and structured data on the Discover, challenge and titles directories."""
import json
import re

import pytest

from app.discover_guides import GUIDES


def structured(html):
    return [json.loads(block) for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)]


def meta(html, attr, name):
    found = re.search(rf'<meta {attr}="{re.escape(name)}" content="([^"]*)"', html)
    return found.group(1) if found else None


@pytest.mark.parametrize("path", ["/discover", "/discover/finding-your-feet", "/discover/monthly/october-2026", "/pick", "/challenges"])
def test_discover_family_pages_carry_complete_share_tags(client, path):
    html = client.get(path).text
    assert meta(html, "property", "og:url") == f"https://omnitrackr.xyz{path}"
    assert meta(html, "property", "og:image") == "https://omnitrackr.xyz/omnitrackr_vortex.png"
    assert meta(html, "property", "og:site_name") == "OmniTrackr"
    assert meta(html, "name", "twitter:card") == "summary"
    assert meta(html, "name", "twitter:title") == meta(html, "property", "og:title")
    assert "{{" not in html


def test_homepage_declares_site_name_and_logo(client):
    types = {block["@type"]: block for block in structured(client.get("/").text)}
    assert types["WebSite"]["name"] == "OmniTrackr"
    assert types["WebSite"]["url"] == "https://omnitrackr.xyz/"
    assert types["Organization"]["logo"].endswith("/omnitrackr_vortex.png")


def test_discover_index_lists_every_trail(client):
    html = client.get("/discover").text
    assert "<title>Discover: what to watch, play, read or hear next | OmniTrackr</title>" in html
    page = next(block for block in structured(html) if block["@type"] == "CollectionPage")
    urls = [entry["url"] for entry in page["mainEntity"]["itemListElement"]]
    assert "https://omnitrackr.xyz/discover/finding-your-feet" in urls
    assert len(urls) == len(set(urls))


@pytest.mark.parametrize("slug", sorted(GUIDES))
def test_guides_use_a_descriptive_search_title_and_keep_their_heading(client, slug):
    html = client.get(f"/discover/{slug}").text
    title = re.search(r"<title>(.*?)</title>", html).group(1)
    assert title.startswith(GUIDES[slug]["search_title"].replace("'", "&#x27;"))
    assert len(GUIDES[slug]["search_title"]) <= 62


def test_challenges_index_lists_published_months(client):
    blocks = structured(client.get("/challenges").text)
    page = next(block for block in blocks if block["@type"] == "CollectionPage")
    for entry in page["mainEntity"]["itemListElement"]:
        assert entry["url"].startswith("https://omnitrackr.xyz/challenges/")


def test_titles_directory_has_share_tags(client):
    html = client.get("/titles").text
    assert meta(html, "property", "og:url") == "https://omnitrackr.xyz/titles"
    assert meta(html, "property", "og:title")


def test_radar_category_description_names_real_titles(client, monkeypatch):
    from app import release_radar as radar
    from tests.release_radar_fixtures import install_fixture_providers
    from datetime import date
    install_fixture_providers(today=date(2026, 9, 27), monkeypatch=monkeypatch)
    names = ["Alpha", "Bravo", "Charlie", "Delta"]
    shows = [radar.make_item(category="tv", key=f"tvm-{n}-s1", title=name, release_date=f"2026-10-0{n + 1}",
                             source_url=None, popularity=50) for n, name in enumerate(names)]

    async def provider(client, window):
        return list(shows) if window.slug == "2026-10" else []

    monkeypatch.setitem(radar.PROVIDERS, "tv", provider)
    html = client.get("/release-radar/tv").text
    description = meta(html, "name", "description")
    assert "including Alpha, Bravo and Charlie," in description
    assert meta(html, "name", "twitter:description") == description
