"""Completed Discover guides must be useful publicly and safe to index."""
from copy import deepcopy
from datetime import date
from html.parser import HTMLParser
import json
from urllib.parse import urlsplit
from xml.etree import ElementTree

import pytest

from app.discover_catalog import MONTHLY_EDITIONS, TRAILS
from app.discover_guides import GUIDES


PROMOTED_TRAILS = {
    "one-evening-well-spent", "finding-your-feet", "beautifully-strange-worlds",
}
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class GuidePage(HTMLParser):
    """Read the response itself: guide content must not depend on a JS fetch."""

    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.text = []
        self.structured = []
        self._script = None
        self._skip = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if tag in {"script", "style"}:
            self._skip += 1
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self._script = []

    def handle_data(self, text):
        if self._script is not None:
            self._script.append(text)
        elif not self._skip and text.strip():
            self.text.append(text.strip())

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            self.structured.append(json.loads("".join(self._script)))
            self._script = None
        if tag in {"script", "style"} and self._skip:
            self._skip -= 1

    def attrs(self, tag):
        return [attrs for name, attrs in self.elements if name == tag]

    @property
    def visible_text(self):
        return " ".join(self.text)

    @property
    def articles(self):
        return [item for item in self.structured if item.get("@type") == "Article"]


def sitemap_entries(client):
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    root = ElementTree.fromstring(response.text)
    return {
        node.findtext("sm:loc", namespaces=SITEMAP_NS): node
        for node in root.findall("sm:url", SITEMAP_NS)
    }


def test_only_complete_guides_are_promoted():
    assert set(GUIDES) == PROMOTED_TRAILS
    for slug, guide in GUIDES.items():
        item_keys = {item["key"] for item in TRAILS[slug]["items"]}
        assert date.fromisoformat(guide["reviewed"]).isoformat() == guide["reviewed"]
        assert guide["summary"] and guide["lead"] and guide["comparison_intro"]
        assert {choice["key"] for choice in guide["choices"]} == item_keys
        assert len(guide["choices"]) == len(item_keys)
        assert set(guide["item_notes"]) == item_keys
        for choice in guide["choices"]:
            assert all(choice[field] for field in ("pace", "commitment", "best_for", "consider"))
        assert all(paragraphs and all(paragraphs) for paragraphs in guide["item_notes"].values())
        assert guide["sections"] and all(section["heading"] and section["paragraphs"] for section in guide["sections"])
        assert len({section["id"] for section in guide["sections"]}) == len(guide["sections"])
        assert guide["sources"]
        assert len({source["key"] for source in guide["sources"]}) == len(guide["sources"])
        assert item_keys.issubset({source["key"] for source in guide["sources"]})
        for source in guide["sources"]:
            url = urlsplit(source["url"])
            assert url.scheme == "https" and url.netloc
            assert source["label"] and source["supports"]
        assert guide["related"]
        assert all(link["slug"] in TRAILS and link["slug"] != slug and link["reason"] for link in guide["related"])


@pytest.mark.parametrize("slug", sorted(PROMOTED_TRAILS))
def test_guides_render_complete_comparisons_analysis_and_sources_without_js(client, slug):
    response = client.get(f"/discover/{slug}")
    assert response.status_code == 200
    page = GuidePage(response.text)
    guide = GUIDES[slug]
    visible = page.visible_text
    for paragraph in guide["lead"]:
        assert paragraph in visible
    assert guide["comparison_intro"] in visible
    assert page.attrs("table") and page.attrs("caption") and page.attrs("thead")
    assert page.attrs("th")
    for choice in guide["choices"]:
        for field in ("pace", "commitment", "best_for", "consider"):
            assert choice[field] in visible
    for section in guide["sections"]:
        assert section["heading"] in visible
        for paragraph in section["paragraphs"]:
            assert paragraph in visible
    for item in TRAILS[slug]["items"]:
        assert item["title"] in visible
        assert item["why"] in visible
        assert item["caveat"] in visible
        for paragraph in guide["item_notes"][item["key"]]:
            assert paragraph in visible
    links = {attrs.get("href") for attrs in page.attrs("a")}
    for source in guide["sources"]:
        assert source["label"] in visible
        assert source["supports"] in visible
        assert source["url"] in links
    for related in guide["related"]:
        assert related["reason"] in visible
        assert f'/discover/{related["slug"]}' in links
    assert "/static/ad-loader.js" not in response.text


@pytest.mark.parametrize("slug", sorted(PROMOTED_TRAILS))
def test_guide_jumps_resolve_to_unique_sections_and_individual_picks(client, slug):
    page = GuidePage(client.get(f"/discover/{slug}").text)
    ids = [attrs["id"] for _, attrs in page.elements if "id" in attrs]
    assert len(ids) == len(set(ids))
    expected = {
        "compare-picks", "connections", "guide-sources", "editorial-method",
        "related-trails", "save-picks",
        *{f'pick-{item["key"]}' for item in TRAILS[slug]["items"]},
    }
    assert expected.issubset(ids)
    links = {attrs["href"] for attrs in page.attrs("a") if "href" in attrs}
    fragment_links = {link[1:] for link in links if link.startswith("#")}
    assert fragment_links.issubset(ids)
    assert {f'pick-{item["key"]}' for item in TRAILS[slug]["items"]}.issubset(fragment_links)
    assert "compare-picks" in fragment_links and "save-picks" in fragment_links


@pytest.mark.parametrize("slug", sorted(PROMOTED_TRAILS))
def test_promoted_guide_metadata_matches_the_public_article(client, slug):
    response = client.get(f"/discover/{slug}?utm_source=shared")
    page = GuidePage(response.text)
    guide = GUIDES[slug]
    canonical = f"https://omnitrackr.xyz/discover/{slug}"
    assert "noindex" not in response.headers.get("x-robots-tag", "")
    assert [attrs["content"] for attrs in page.attrs("meta") if attrs.get("name") == "robots"] == [
        "index, follow, max-image-preview:large",
    ]
    assert [attrs["href"] for attrs in page.attrs("link") if attrs.get("rel") == "canonical"] == [canonical]
    assert [attrs["content"] for attrs in page.attrs("meta") if attrs.get("name") == "description"] == [guide["summary"]]
    assert len(page.attrs("h1")) == 1
    assert len(page.articles) == 1
    article = page.articles[0]
    assert article["headline"] == TRAILS[slug]["name"]
    assert article["description"] == guide["summary"]
    assert article["datePublished"] == "2026-09-08"
    assert article["dateModified"] == guide["reviewed"]
    assert article["author"]["@type"] == "Organization"
    assert article["author"]["name"] == "OmniTrackr"
    entity = article["mainEntityOfPage"]
    assert (entity.get("@id") if isinstance(entity, dict) else entity) == canonical


def test_sitemap_has_exact_promoted_trails_and_preserves_monthly_editions(client):
    entries = sitemap_entries(client)
    discover_paths = {urlsplit(url).path for url in entries if urlsplit(url).path.startswith("/discover")}
    assert discover_paths == {
        "/discover", *{f"/discover/{slug}" for slug in PROMOTED_TRAILS},
        *{f"/discover/monthly/{slug}" for slug in MONTHLY_EDITIONS},
    }
    for slug, guide in GUIDES.items():
        entry = entries[f"https://omnitrackr.xyz/discover/{slug}"]
        assert entry.findtext("sm:lastmod", namespaces=SITEMAP_NS) == guide["reviewed"]
    for slug in set(TRAILS) - PROMOTED_TRAILS:
        response = client.get(f"/discover/{slug}")
        page = GuidePage(response.text)
        assert response.headers["x-robots-tag"] == "noindex, follow"
        assert any(attrs.get("name") == "robots" and attrs["content"] == "noindex, follow" for attrs in page.attrs("meta"))
        assert not page.articles
    for slug in MONTHLY_EDITIONS:
        response = client.get(f"/discover/monthly/{slug}")
        assert "noindex" not in response.headers.get("x-robots-tag", "")
        assert MONTHLY_EDITIONS[slug]["essay"] in GuidePage(response.text).visible_text


def test_guide_last_modified_tracks_the_review_date_not_request_date(client, monkeypatch):
    slug = "finding-your-feet"
    monkeypatch.setitem(GUIDES[slug], "reviewed", "2026-09-20")
    entries = sitemap_entries(client)
    entry = entries[f"https://omnitrackr.xyz/discover/{slug}"]
    assert entry.findtext("sm:lastmod", namespaces=SITEMAP_NS) == "2026-09-20"
    article = GuidePage(client.get(f"/discover/{slug}").text).articles[0]
    assert article["dateModified"] == "2026-09-20"


def test_editorial_text_cannot_break_out_of_html_attributes_or_json_ld(client, monkeypatch):
    slug = "one-evening-well-spent"
    payload = '\" & </script><img src=x onerror=alert(1)><script>alert(2)</script>'
    guide = deepcopy(GUIDES[slug])
    guide["summary"] = payload
    guide["lead"] = [payload]
    guide["comparison_intro"] = payload
    guide["choices"][0].update({field: payload for field in ("pace", "commitment", "best_for", "consider")})
    guide["sections"][0].update(heading=payload, paragraphs=[payload])
    guide["item_notes"][guide["choices"][0]["key"]] = [payload]
    guide["sources"][0].update(label=payload, supports=payload)
    guide["related"][0]["reason"] = payload
    monkeypatch.setitem(GUIDES, slug, guide)
    monkeypatch.setitem(TRAILS[slug], "name", payload)
    response = client.get(f"/discover/{slug}")
    page = GuidePage(response.text)
    assert response.status_code == 200
    assert "Content-Security-Policy" in response.headers
    assert "<img src=x" not in response.text
    assert "<script>alert(2)</script>" not in response.text
    assert not any("onerror" in attrs for _, attrs in page.elements)
    assert page.articles[0]["headline"] == payload
    assert page.articles[0]["description"] == payload
    assert payload in page.visible_text
    assert [attrs["content"] for attrs in page.attrs("meta") if attrs.get("name") == "description"] == [payload]
