"""Nov 20 2026 accessibility and speed pass on the public pages: readable filled buttons, link names that
match their words, keyboard access to the genre row, no timed reload, sized profile posters and a
homepage that only lays out what is near the screen."""
import re
from pathlib import Path
from types import SimpleNamespace

from app import image_sizes
from app.routers import profiles
from tests.test_a11y_polish import _contrast

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _brighter(hex_color: str, factor: float) -> str:
    channels = [min(255, round(int(hex_color.lstrip("#")[i:i + 2], 16) * factor)) for i in (0, 2, 4)]
    return "#" + "".join(f"{c:02x}" for c in channels)


def test_filled_button_colours_keep_white_text_at_4_5_to_1_including_hover():
    site = _read("site.css")
    landing = _read("public-landing.css")
    for css, prefix in ((site, "--site-cta"), (landing, "--lp-cta")):
        start = re.search(rf"{prefix}: (#[0-9a-f]{{6}});", css).group(1)
        end = re.search(rf"{prefix}-2: (#[0-9a-f]{{6}});", css).group(1)
        for colour in (start, end):
            assert _contrast("#ffffff", colour) >= 4.5, colour
            # Hover brightens by 4%; it must still read.
            assert _contrast("#ffffff", _brighter(colour, 1.04)) >= 4.5, colour
    # The old pair read at 4.2:1 and 4.0:1.
    assert _contrast("#ffffff", "#8b5cf6") < 4.5 and _contrast("#ffffff", "#a855f7") < 4.5


def test_public_filled_buttons_use_the_readable_pair():
    old = "linear-gradient(135deg, var(--site-violet), var(--site-violet-2))"
    for name in ("site.css", "discover.css", "reviews.css", "demo.css", "collection-save.css", "review-save.css",
                 "release-radar.css", "public-reader.css", "collections-public.css"):
        css = _read(name)
        assert old not in css, name
        assert "var(--site-cta" in css, name
    landing = _read("public-landing.css")
    assert "linear-gradient(135deg, var(--lp-violet), var(--lp-violet-2))" not in landing
    assert ".lp-btn--primary { background: linear-gradient(135deg, var(--lp-cta), var(--lp-cta-2));" in landing
    auth = _read("auth-forms.css")
    assert "--auth-accent: var(--lp-cta, #7f4ef0);" in auth and "filter: brightness(1.08)" not in auth
    for name in ("site.css", "discover.css", "reviews.css", "release-radar.css", "public-reader.css"):
        assert "brightness(1.08)" not in _read(name) and "brightness(1.1)" not in _read(name), name


def test_initials_and_step_numbers_sit_on_dark_enough_colours():
    assert _contrast("#ffffff", "#0f766e") >= 4.5
    assert ".guide-path__number { align-items: center; background: linear-gradient(135deg, var(--site-cta, #7f4ef0), #0f766e);" in _read("public-reader.css")
    assert ".site-finder__mark--person { background: linear-gradient(135deg, var(--site-cta), #0f766e);" in _read("site.css")
    assert "linear-gradient(135deg, var(--site-cta, #7f4ef0), #0f766e)" in _read("collections-public.css")
    assert "linear-gradient(135deg, var(--site-cta, #7f4ef0), #0f766e)" in _read("search-page.css")
    assert ".lp-vg-match__face.is-friend { background: linear-gradient(140deg, #0f766e, #115e59); }" in _read("public-landing.css")
    assert ".lp .faq-answer a { color: var(--lp-violet-soft); text-decoration: underline;" in _read("public-landing.css")


def test_changed_stylesheets_are_asked_for_again():
    for template in ("public_landing.html", "discover.html", "release_radar.html", "demo.html", "reviews.html", "about.html"):
        html = (ROOT / "app" / "templates" / template).read_text(encoding="utf-8")
        tags = re.findall(r"/static/(site|discover|reviews|demo|release-radar|public-reader|public-landing|auth-forms)\.css\?v=([\w-]+)", html)
        assert tags, template
        assert all(version >= "20261120-a11y" for _, version in tags), (template, tags)
    from app import site_chrome
    assert site_chrome.SITE_CSS_VERSION >= "20261120-a11y"


def test_review_links_are_named_starting_with_their_words():
    # WCAG 2.5.3: someone saying "Save to my library" or "Read full review" must hit the link.
    source = (ROOT / "app" / "routers" / "reviews.py").read_text(encoding="utf-8")
    assert 'aria-label="Read full review of {_escape(review.get("title"))}">Read full review</a>' in source
    assert "aria-label=\"Save to my library: {_escape(review.get('title'))}\">Save to my library</a>" in source
    script = _read("reviews.js")
    assert "save.setAttribute('aria-label', `Save to my library: ${review.title}`);" in script
    assert "read.setAttribute('aria-label', `Read full review of ${review.title}`);" in script


def test_discussion_starter_links_are_at_least_24px_tall():
    css = _read("discussions.css")
    assert ".disc-starter-links a { color: var(--site-violet-soft); display: inline-block; font-weight: 600; min-height: 24px;" in css


def test_genre_row_can_be_focused_and_shows_where_focus_is():
    css = _read("title-detail.css")
    assert ".title-detail .title-hero__chips:focus-visible { outline: 3px solid var(--site-violet-soft);" in css


def test_still_gathering_pages_check_again_with_a_stop_button():
    script = _read("release-radar.js")
    assert "meta[name=\"omnitrackr-recheck\"]" in script
    assert "stop.textContent = 'Stop checking';" in script and "window.clearTimeout(timer);" in script
    radar = (ROOT / "app" / "routers" / "release_radar.py").read_text(encoding="utf-8")
    roundup = (ROOT / "app" / "routers" / "weekly_roundup.py").read_text(encoding="utf-8")
    assert "<meta http-equiv=\"refresh\"" not in radar.replace("Not <meta http-equiv=\"refresh\">", "")
    assert "refreshes itself" not in radar and "refreshes itself" not in roundup
    template = (ROOT / "app" / "templates" / "release_radar.html").read_text(encoding="utf-8")
    assert "release-radar.js?v=20261120-a11y-1" in template


def test_profile_wall_posters_are_sized_and_the_first_load_early():
    view = SimpleNamespace(supporter=None, diary=[], favorites=[],
                           showcase=[{"image": f"https://m.media-amazon.com/images/M/MV5Bposter{i}._V1_SX300.jpg"} for i in range(6)])
    html = profiles._wall_html(view)
    tags = re.findall(r"<img [^>]+>", html)
    assert len(tags) == 6
    assert all('width="96" height="144"' in tag for tag in tags)
    assert [('fetchpriority="high"' in tag) for tag in tags] == [True, True, True, True, False, False]
    # html_finish then asks Amazon for a 240-pixel copy instead of the 300-pixel original.
    assert "_V1_QL75_UX240_.jpg" in image_sizes.shrink_html(html)


def test_small_declared_thumbnails_get_the_smallest_rawg_copy():
    rawg = "https://media.rawg.io/media/games/734/7342a1cd82c8997ec620084ae4c2e7e4.jpg"
    out = image_sizes.shrink_html(f'<img src="{rawg}" alt="" width="96" height="144" fetchpriority="high">')
    assert "/media/resize/200/-/games/" in out
    # Bigger tags keep their sizes.
    assert "/media/resize/420/-/games/" in image_sizes.shrink_html(f'<img src="{rawg}" alt="" width="200" height="300">')


def test_homepage_lays_out_sections_only_near_the_screen():
    landing = _read("public-landing.css")
    assert ".lp-section { content-visibility: auto; contain-intrinsic-size: auto 900px; }" in landing
    assert "@media (max-width: 760px) { .lp-section { contain-intrinsic-size: auto 1500px; } }" in landing
    # The sign-up section and the fixed save bar are not .lp-section, so they always render.
    assert not re.search(r"\.landing-auth[^{]*\{[^}]*content-visibility", landing)
    assert not re.search(r"\.lp-savebar[^{]*\{[^}]*content-visibility", landing)


def test_homepage_sign_up_section_and_save_bar_stay_outside_skipped_sections(client):
    html = client.get("/").text
    sections = re.findall(r'<section class="([^"]+)"', html)
    assert any("landing-auth" in s and "lp-section" not in s for s in sections)
    assert 'class="lp-savebar"' in html
    savebar = html.index('class="lp-savebar"')
    # The save bar is position: fixed; inside a contained section it would stop following the page.
    assert html.rfind("</section>", 0, savebar) > html.rfind("<section", 0, savebar)


def test_guide_reader_measures_after_the_first_layout():
    script = _read("guide-reader.js")
    assert "window.addEventListener('resize', queue);\n  // Measure in the next frame" in script
    assert "\n  update();\n" not in script
    from app import guide_layout
    assert guide_layout.JS_VERSION == "20261123-support-1"
