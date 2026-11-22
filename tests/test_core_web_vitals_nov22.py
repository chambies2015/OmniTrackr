"""Nov 22 2026 Core Web Vitals pass on the public pages: the back/forward cache on ad pages,
prefetching guide links on hover, a small file for Latin Extended-A letters, and Wikimedia
thumbnails instead of full-size Wikipedia posters."""
import json
import re
from pathlib import Path

from app import html_finish, image_sizes, page_hints

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
POSTER = ("https://upload.wikimedia.org/wikipedia/en/f/f2/The_Secret_Life_of_Walter_Mitty_2013_poster.jpg"
          "?utm_source=en.wikipedia.org&amp;utm_campaign=api&amp;utm_content=thumbnail_unscaled")
THUMB_250 = ("https://upload.wikimedia.org/wikipedia/en/thumb/f/f2/The_Secret_Life_of_Walter_Mitty_2013_poster.jpg/"
             "250px-The_Secret_Life_of_Walter_Mitty_2013_poster.jpg")
SITE_JS = '<script src="/static/site.js?v=1" defer></script>'


# --- Back/forward cache ---------------------------------------------------------------------

def test_unload_listeners_are_turned_off_so_back_restores_the_page(client):
    # Google's viewability script (lidar.js) adds an unload listener on every ad page, and any
    # unload listener keeps Chrome from keeping the page for the Back button.
    for path in ("/guides", "/in-order/star-wars", "/static/site.css"):
        policy = client.get(path).headers["permissions-policy"]
        assert "unload=()" in policy, path
        assert "geolocation=()" in policy and "camera=()" in policy and "microphone=()" in policy


def test_no_script_of_ours_listens_for_unload():
    offenders = []
    for path in list(STATIC.rglob("*.js")) + [ROOT / "app" / "auth.js"]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"""addEventListener\(\s*['"]unload['"]|\bonunload\s*=""", text):
            offenders.append(path.name)
    assert offenders == []


# --- Prefetch on hover ----------------------------------------------------------------------

def test_public_pages_point_chrome_at_the_prefetch_rules(client):
    for path in ("/guides", "/in-order/star-wars", "/essentials/movies", "/discover", "/movie-tracker"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers.get("speculation-rules") == '"/speculation-rules.json"', path


def test_pages_without_the_public_chrome_get_no_rules(client, authenticated_client):
    assert "speculation-rules" not in client.get("/speculation-rules.json").headers
    assert "speculation-rules" not in client.get("/sitemap.xml").headers
    dashboard = authenticated_client.get("/")
    assert dashboard.status_code == 200 and html_finish.PUBLIC_CHROME_MARK not in dashboard.text
    assert "speculation-rules" not in dashboard.headers


def test_prefetch_rules_file_is_served_as_speculation_rules(client):
    response = client.get("/speculation-rules.json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/speculationrules+json")
    assert "max-age=86400" in response.headers["cache-control"]
    rules = json.loads(response.text)
    assert rules == page_hints.SPECULATION_RULES
    rule = rules["prefetch"][0]
    assert rule["eagerness"] == "moderate" and rule["source"] == "document"
    assert "prerender" not in rules  # Prerendering would run analytics and ads for pages never opened.


def test_prefetch_list_leaves_out_pages_that_count_or_change_something():
    patterns = page_hints.PREFETCH_PATHS
    # The homepage records a sign-up funnel view and sends new accounts to /start once; public
    # collections count readers; list, poll and services links record that they were opened.
    for path in ("/", "/collections/public/*", "/lists", "/lists/*", "/tonight", "/tonight/*",
                 "/on-my-services/*", "/auth/*", "/api/*", "/account/*", "/u/*", "/start"):
        assert path not in patterns, path
    assert not any(p.startswith(("/auth", "/api", "/account", "/collections/public", "/lists", "/tonight")) for p in patterns)
    for path in ("/guides", "/in-order/*", "/essentials/*", "/best-of/*", "/titles/*", "/*-tracker"):
        assert path in patterns, path
    exclusions = page_hints.SPECULATION_RULES["prefetch"][0]["where"]["and"][1]["not"]["selector_matches"]
    assert "[rel~=nofollow]" in exclusions and "[target=_blank]" in exclusions and "[data-no-prefetch]" in exclusions


def test_prefetches_are_not_counted_as_page_views():
    traffic = (ROOT / "app" / "site_traffic.py").read_text(encoding="utf-8")
    assert '"prefetch" in purpose' in traffic


# --- Fonts ----------------------------------------------------------------------------------

def _faces(css: str) -> list[str]:
    return re.findall(r"@font-face \{(.*?)\}", css, re.S)


def test_latin_extended_a_letters_load_a_small_file():
    css = (STATIC / "fonts.css").read_text(encoding="utf-8")
    faces = {re.search(r"fonts/([\w.-]+)\)", face).group(1): face for face in _faces(css) if "url(" in face}
    small = faces["inter-var-latin-ext-a.woff2"]
    assert "unicode-range: U+0100-017F;" in small and "font-weight: 400 700;" in small and "font-display: swap;" in small
    rest = faces["inter-var-latin-ext.woff2"]
    assert "U+0180-02BA" in rest and "U+0100" not in rest
    assert (STATIC / "fonts" / "inter-var-latin-ext-a.woff2").stat().st_size < 20_000
    assert (STATIC / "fonts" / "inter-var-latin-ext.woff2").stat().st_size > 80_000


def test_public_pages_ask_for_the_new_font_stylesheet(client):
    for path in ("/", "/faq", "/movie-tracker", "/discover", "/sample-library"):
        html = client.get(path).text
        assert "/static/fonts.css?v=20261009-fonts-1" not in html, path
        if "/static/fonts.css?v=" in html:
            assert "/static/fonts.css?v=20261122-cwv-1" in html, path


# --- Wikimedia thumbnails -------------------------------------------------------------------

def test_small_wikipedia_posters_become_thumbnails():
    assert image_sizes.wikimedia_thumb(POSTER) == THUMB_250
    assert image_sizes.wikimedia_thumb(POSTER, display_width=28).endswith("/120px-The_Secret_Life_of_Walter_Mitty_2013_poster.jpg")
    assert image_sizes.wikimedia_thumb(POSTER, display_width=96) == THUMB_250
    # PNG stays PNG, and percent-escapes are kept as they are.
    png = "https://upload.wikimedia.org/wikipedia/en/d/db/Spirited_Away_Japanese_poster.png?utm_source=x"
    assert image_sizes.wikimedia_thumb(png) == ("https://upload.wikimedia.org/wikipedia/en/thumb/d/db/Spirited_Away_Japanese_poster.png/"
                                                "250px-Spirited_Away_Japanese_poster.png")
    kiki = "https://upload.wikimedia.org/wikipedia/en/0/07/Kiki%27s_Delivery_Service_%28Movie%29.jpg"
    assert image_sizes.wikimedia_thumb(kiki).endswith("/0/07/Kiki%27s_Delivery_Service_%28Movie%29.jpg/250px-Kiki%27s_Delivery_Service_%28Movie%29.jpg")


def test_large_posters_and_odd_urls_are_left_alone():
    # English Wikipedia's poster uploads are about 250 px wide already: the title-page poster keeps it.
    assert image_sizes.wikimedia_thumb(POSTER, image_sizes.HERO_WIDTH) == POSTER
    # Commons photos can be thousands of pixels wide, so even large slots get a thumbnail.
    commons = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Big_photo.jpg"
    assert image_sizes.wikimedia_thumb(commons, image_sizes.HERO_WIDTH).endswith("/thumb/a/ab/Big_photo.jpg/500px-Big_photo.jpg")
    assert image_sizes.wikimedia_thumb(commons, image_sizes.BACKDROP_WIDTH).endswith("/960px-Big_photo.jpg")
    for url in (THUMB_250, "https://upload.wikimedia.org/wikipedia/commons/a/ab/Drawing.svg",
                "https://upload.wikimedia.org/wikipedia/commons/a/ab/Anim.gif",
                "https://upload.wikimedia.org/wikipedia/en/a/ab/" + "Long_name_" * 14 + ".jpg",
                "https://example.org/wikipedia/en/a/ab/Poster.jpg", None, ""):
        assert image_sizes.wikimedia_thumb(url) == url
    for width in image_sizes.WIKIMEDIA_WIDTHS:
        assert width in (20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840)  # Wikimedia's standard steps


def test_pages_only_get_thumbnails_when_site_js_can_put_the_original_back():
    tile = f'<img src="{POSTER}" alt="" width="96" height="144" loading="lazy">'
    with_fallback = image_sizes.shrink_html(SITE_JS + tile)
    assert f'src="{THUMB_250}"' in with_fallback and 'width="96" height="144" loading="lazy"' in with_fallback
    assert image_sizes.shrink_html("<body>" + tile) == "<body>" + tile


def test_hero_posters_and_srcsets_keep_their_urls_in_pages():
    hero = f'<img class="title-hero__poster" src="{POSTER}" alt="" width="300" height="450" fetchpriority="high">'
    assert image_sizes.shrink_html(SITE_JS + hero) == SITE_JS + hero
    srcset = f'<img src="{POSTER}" srcset="{POSTER} 1x" alt="">'
    assert image_sizes.shrink_html(SITE_JS + srcset) == SITE_JS + srcset
    # A small tile marked high priority (the first profile wall posters) still gets the thumbnail.
    wall = f'<img src="{POSTER}" alt="" width="96" height="144" fetchpriority="high">'
    assert THUMB_250 in image_sizes.shrink_html(SITE_JS + wall)


def test_site_js_puts_failed_thumbnails_back():
    js = (STATIC / "site.js").read_text(encoding="utf-8")
    block = js[js.index("/* Wikipedia posters arrive as Wikimedia thumbnails"):]
    assert "document.addEventListener('error'" in block and ", true);" in block
    assert "img.complete && img.naturalWidth === 0" in block


def test_site_js_version_moved_on():
    from app import site_chrome
    assert site_chrome.SITE_JS_VERSION >= "20261122-cwv-1"
