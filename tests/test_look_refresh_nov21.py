"""Nov 21 2026 look refresh of the public pages: format tokens, header line and scroll
state, the reworked footer, the light header on reader pages and big-title spacing."""
import re
from pathlib import Path

from app import site_chrome

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
SITE_CSS = (STATIC / "site.css").read_text(encoding="utf-8")
SITE_JS = (STATIC / "site.js").read_text(encoding="utf-8")
READER_CSS = (STATIC / "public-reader.css").read_text(encoding="utf-8")
LANDING_CSS = (STATIC / "public-landing.css").read_text(encoding="utf-8")


def _footer(html):
    return html[html.index('<footer class="site-footer">'):html.index("</footer>")]


def test_format_colours_and_spectrum_are_site_tokens():
    root = SITE_CSS[SITE_CSS.index(":root {"):SITE_CSS.index("\n}", SITE_CSS.index(":root {"))]
    for kind, colour in (("movie", "#f472b6"), ("tv", "#60a5fa"), ("anime", "#f87171"), ("game", "#34d399"),
                         ("album", "#a78bfa"), ("book", "#fbbf24"), ("manga", "#fb923c"), ("podcast", "#2dd4bf"),
                         ("audiobook", "#e879f9")):
        assert f"--fmt-{kind}: {colour};" in root
        assert colour in root[root.index("--site-spectrum:"):]
    # The a11y pass's button tokens stay as they were.
    assert "--site-cta: #7f4ef0;" in root and "--site-cta-2: #963cf0;" in root


def test_header_draws_the_spectrum_line_and_firms_up_on_scroll(client):
    assert ".site-header::after { background: var(--site-spectrum);" in SITE_CSS
    assert ".site-header.is-scrolled {" in SITE_CSS
    assert "classList.toggle('is-scrolled', window.scrollY > 8)" in SITE_JS
    assert "{ passive: true }" in SITE_JS
    html = client.get("/discover").text
    assert f"/static/site.js?v={site_chrome.SITE_JS_VERSION}" in html
    assert f"/static/site.css?v={site_chrome.SITE_CSS_VERSION}" in html


def test_long_menus_open_as_two_columns():
    explore = next(items for key, _, items in site_chrome.NAV_MENUS if key == "explore")
    assert len(explore) >= 7
    assert ".site-dd__panel:has(> a:nth-child(7)) { grid-template-columns: repeat(2, minmax(0, 1fr));" in SITE_CSS


def test_footer_top_band_has_both_asks_and_all_nine_trackers(client):
    footer = _footer(client.get("/faq").text)
    top = footer[:footer.index("site-footer__grid")]
    assert 'class="site-footer__cta site-btn site-btn--primary site-btn--sm" href="/#signup" data-guest-only>' in top
    assert 'href="https://ko-fi.com/omnitrackr" target="_blank" rel="noopener noreferrer">' in top
    assert len(site_chrome.FOOTER_FORMATS) == 9
    for kind, label, href in site_chrome.FOOTER_FORMATS:
        assert f'<a href="{href}" data-kind="{kind}">{label}</a>' in top
        assert f'[data-kind="{kind}"] {{ --fmt: var(--fmt-{kind}); }}' in SITE_CSS
        assert client.get(href).status_code == 200, href
    # Members don't get a sign-up button: site-nav.js hides it and the CSS honours hidden.
    assert ".site-footer__actions [hidden] { display: none; }" in SITE_CSS


def test_footer_columns_fold_on_phones_with_scripts_only(client):
    footer = _footer(client.get("/about").text)
    for index, (title, _) in enumerate(site_chrome.FOOTER_GROUPS):
        assert f'<h2>{title}</h2><div class="site-footer__links" id="site-footer-{index}">' in footer
    assert "matchMedia('(max-width: 640px)')" in SITE_JS
    assert "setAttribute('aria-expanded'" in SITE_JS and "setAttribute('aria-controls', links.id)" in SITE_JS
    assert "innerHTML" not in SITE_JS
    phones = SITE_CSS[SITE_CSS.index("@media (max-width: 640px) {"):]
    phones = phones[:phones.index("\n}")]
    # Only a footer that site.js marked as folding hides its links.
    assert ".site-footer.is-folding .site-footer__col:not(.is-open) .site-footer__links { display: none; }" in phones
    assert SITE_CSS.count(".site-footer__links { display: none; }") == 1


def test_light_reader_pages_get_a_light_header():
    for block in ('html[data-reader]:not([data-theme="dark"]) .public-reader .site-header {',
                  'html[data-reader][data-theme="light"] .public-reader .site-header {'):
        start = READER_CSS.index(block)
        rules = READER_CSS[start:READER_CSS.index("}", start)]
        assert "--site-header-bg: rgba(246, 245, 251, .8);" in rules
        assert "--site-strong: #16132b;" in rules and "color-scheme: light;" in rules
    # Header text and hover colours come from tokens, so the light values reach them.
    for rule in (".site-dd.is-current > summary { color: var(--site-strong); }",
                 ".site-header .site-nav__links > .site-nav__login { color: var(--site-strong);",
                 ".site-header { backdrop-filter: blur(18px) saturate(160%); -webkit-backdrop-filter: blur(18px) saturate(160%); background: var(--site-header-bg);"):
        assert rule in SITE_CSS


def test_big_titles_use_the_shared_letter_spacing():
    assert "--site-display-track: -.032em;" in SITE_CSS
    assert "letter-spacing: var(--site-display-track)" in SITE_CSS[SITE_CSS.index(".site-hero h1 {"):]
    assert "body.discover-page .discover-main .hero h1 { letter-spacing: var(--site-display-track);" in SITE_CSS
    assert ".lp-title { letter-spacing: var(--site-display-track, -.032em);" in LANDING_CSS
    assert "letter-spacing: var(--site-display-track, -.032em)" in READER_CSS


def test_homepage_loads_the_refreshed_stylesheet(client):
    html = client.get("/").text
    version = re.search(r"/static/public-landing\.css\?v=([\w-]+)", html).group(1)
    assert version >= "20261121-refresh-1"
    assert ".lp .lp-hero::before { background-image: radial-gradient(" in LANDING_CSS
    assert ".lp-hero__grid { position: relative; z-index: 1; }" in LANDING_CSS
