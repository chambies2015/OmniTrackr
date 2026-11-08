"""The homepage hero's poster wall, the nine-format ribbon and the merged How it works section."""
import re

from app import guest_picks, main


def items(count):
    kinds = ("Movie", "Anime", "Video game", "TV show", "Book", "Album")
    return [{"title": f"Title {n} <b>", "label": kinds[n % len(kinds)], "image": f"https://img.example/{n}.jpg",
             "kind": "movie", "url": f"/titles/movie/title-{n}"} for n in range(count)]


def test_stage_needs_enough_covers():
    assert guest_picks.stage_html(items(guest_picks.STAGE_MIN - 1)) == ""
    assert guest_picks.stage_html([]) == ""


def test_stage_renders_columns_and_rows_of_real_covers():
    html = guest_picks.stage_html(items(15))
    assert html.startswith('<div class="lp-hero__visual lp-stage" aria-hidden="true">')
    assert html.count('class="lp-stage__col"') == 3
    assert html.count('class="lp-stage__row"') == 2
    # Each column and row lists its covers twice so the drift loops cleanly.
    assert html.count('src="https://img.example/0.jpg"') == 2 + 4
    assert "<b>" not in html and "Title 0 &lt;b&gt;" in html
    assert 'loading="lazy"' not in html  # the copies reuse the same requests, so nothing waits on scroll


def test_homepage_swaps_the_vortex_for_the_stage(client, monkeypatch):
    monkeypatch.setattr(guest_picks, "hero_stage", lambda *a, **k: guest_picks.stage_html(items(12)))
    html = client.get("/").text
    assert "lp-stage__wall" in html
    assert '<img src="/vortex.webp"' not in html
    assert "<!--HERO_STAGE-->" not in html and "<!--/HERO_STAGE-->" not in html
    assert html.count('class="lp-hero__visual') == 1


def test_homepage_keeps_the_vortex_without_covers(client, monkeypatch):
    monkeypatch.setattr(guest_picks, "hero_stage", lambda *a, **k: "")
    html = client.get("/").text
    assert '<img src="/vortex.webp"' in html and "lp-stage__wall" not in html
    assert "HERO_STAGE" not in html


def test_homepage_survives_a_broken_stage(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("stage exploded")

    monkeypatch.setattr(guest_picks, "hero_stage", boom)
    response = client.get("/")
    assert response.status_code == 200
    assert '<img src="/vortex.webp"' in response.text and "stage exploded" not in response.text


def test_format_ribbon_links_every_tracker_page(client):
    html = client.get("/").text
    ribbon = html[html.index('class="lp-formats"'):]
    ribbon = ribbon[:ribbon.index("</nav>")]
    hrefs = re.findall(r'<a href="([^"]+)"', ribbon)
    assert hrefs == ["/movie-tracker", "/tv-show-tracker", "/anime-tracker", "/game-tracker", "/book-tracker",
                     "/music-tracker", "/manga-tracker", "/podcast-tracker", "/audiobook-tracker"]
    for href in hrefs:
        assert client.get(href).status_code == 200, href


def test_how_it_works_sits_beside_the_example_library(client):
    html = client.get("/").text
    section = html[html.index('id="how-it-works"'):]
    section = section[:section.index('id="features"')]
    assert "From recommendation to a memory you can revisit" in section
    assert "landing-library-showcase" in section
    assert section.count('<span class="lp-flow__num">') == 4
    assert html.count('id="how-it-works"') == 1


def test_stage_motion_respects_reduced_motion():
    css = open("app/static/public-landing.css", encoding="utf-8").read()
    reduced = css[css.rindex("@media (prefers-reduced-motion: reduce)"):]
    assert ".lp-stage__col, .lp-stage__row, .lp-stage__card { animation: none; }" in reduced
