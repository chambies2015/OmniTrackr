"""Nov 22 2026 sweep of #296 (guides library), #297 (public look refresh) and #298 (security audit)."""
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from app import guide_library

ROOT = Path(__file__).resolve().parents[1]


def _rail_links(rail: str) -> list[tuple[str, str]]:
    return re.findall(r'<a href="([^"]+)">([^<]+)</a>', rail)


def test_every_guide_rail_links_to_real_pages(client):
    # The shelf link used to take the first letter of the shelf's intro as its href
    # ("L" on /in-order/star-wars, so /in-order/L), a 404 on every guide page.
    hubs = {key: hubs[0][0] for key, _heading, _intro, hubs in guide_library.SHELVES}
    checked = 0
    for row in guide_library.rows():
        rail = guide_library.rail_html(row["href"])
        links = _rail_links(rail)
        assert links, row["href"]
        for href, _label in links:
            assert href.startswith("/"), (row["href"], href)
        shelf_href = links[0][0]
        expected = hubs[row["shelf"]] if hubs[row["shelf"]] != row["href"] else f"/guides#shelf-{row['shelf']}"
        assert shelf_href == expected, (row["href"], shelf_href)
        checked += 1
    assert checked > 100
    for href in sorted({href for href in hubs.values() if href.startswith("/")}):
        assert client.get(href).status_code == 200, href


def test_guide_page_rail_points_at_its_hub(client):
    html = client.get("/in-order/star-wars").text
    rail = re.search(r'<nav class="guide-rail__library".*?</nav>', html, re.S).group(0)
    assert '<a href="/in-order">Series in order</a>' in rail
    # On a hub that is itself a guide, the shelf link opens that shelf in the library.
    html = client.get("/holidays").text
    rail = re.search(r'<nav class="guide-rail__library".*?</nav>', html, re.S).group(0)
    assert '<a href="/guides#shelf-seasonal">Holidays and seasons</a>' in rail
    assert 'id="shelf-seasonal"' in client.get("/guides").text


def test_guide_pages_have_no_one_letter_links(client):
    for path in ("/in-order/star-wars", "/binge-calculator/breaking-bad", "/if-you-liked/interstellar",
                 "/discover/found-family", "/essentials/games", "/best-of/2026/movies", "/new-releases/spring-2027",
                 "/holidays/christmas", "/halloween", "/discover/monthly/november-2026"):
        response = client.get(path)
        assert response.status_code == 200, path
        for href in re.findall(r'<a [^>]*href="([^"#][^"]*)"', response.text):
            target = urlsplit(urljoin("https://omnitrackr.xyz" + path, href))
            if target.netloc != "omnitrackr.xyz":
                continue
            assert not re.fullmatch(r"/(?:[\w-]+/)*[A-Z]", target.path), (path, href)


def test_format_desks_survive_an_undated_guide(monkeypatch):
    rows = guide_library.rows()
    first = next(row for row in rows if row["shelf"] == "essentials" and row["main"] == "movie")
    undated = dict(first, href="/essentials/undated", name="An undated film list", updated="")
    malformed = dict(first, href="/essentials/odd-date", name="A film list with an odd date", updated="next week")
    monkeypatch.setattr(guide_library, "rows", lambda: rows + [undated, malformed])
    html = guide_library.formats_html()
    films = re.search(r'<article class="gl-desk" id="format-films">.*?</article>', html, re.S).group(0)
    # The dated list still leads the films desk; the undated ones sort after it.
    assert f'href="{first["href"]}"' in films
    assert "/essentials/undated" not in films and "/essentials/odd-date" not in films


def test_auth_script_tag_moved_past_the_audit_change():
    # #298 reworded the Google "unverified" message in auth.js, which is cached for a year
    # under its ?v= tag, so the tag has to change for returning visitors to get it.
    for template in ("app/templates/index.html", "app/templates/public_landing.html"):
        tag = re.search(r'/auth\.js\?v=([\w.-]+)"', (ROOT / template).read_text(encoding="utf-8")).group(1)
        assert tag >= "20261122-sweep-1", template
    assert "Google couldn't confirm current ownership of this address." in (ROOT / "app/static/auth.js").read_text(encoding="utf-8")
