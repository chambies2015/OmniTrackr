"""Member app look refresh (Nov 22 2026): member-look.css, the footer's library buttons, the welcome name."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "member-look.css").read_text(encoding="utf-8")
SITE_CSS = (STATIC / "site.css").read_text(encoding="utf-8")
HOME_HERO = (STATIC / "home-hero.js").read_text(encoding="utf-8")
ACCOUNT_JS = (STATIC / "dashboard" / "account.js").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "app" / "templates" / "changelog.html").read_text(encoding="utf-8")

LIBRARIES = ("movies", "tv-shows", "anime", "video-games", "music", "books", "manga", "podcasts", "audiobooks")


def _footer() -> str:
    start = INDEX.index('id="mainFooter"')
    return INDEX[start:INDEX.index("</footer>", start)]


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def test_stylesheet_is_linked_once_with_a_version():
    assert INDEX.count("/static/member-look.css?v=20261127-sweep-1") == 1


def test_format_colours_and_spectrum_match_the_public_site():
    for name in ("movie", "tv", "anime", "game", "album", "book", "manga", "podcast", "audiobook"):
        public = re.search(rf"--fmt-{name}: (#[0-9a-f]{{6}});", SITE_CSS).group(1)
        assert f"--fmt-{name}: {public};" in CSS, name
    public_spectrum = re.search(r"--site-spectrum: (linear-gradient\([^;]+\));", SITE_CSS).group(1)
    assert f"--spectrum: {public_spectrum};" in CSS


def test_filled_buttons_keep_white_text_above_four_and_a_half():
    for token in ("--cta", "--cta-2"):
        colour = re.search(rf"  {token}: (#[0-9a-f]{{6}});", CSS).group(1)
        assert 1.05 / (_luminance(colour) + 0.05) >= 4.5, (token, colour)
    # The old gradient ended on #a855f7 (4.0:1); none of it comes back here.
    rules = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    assert "#a855f7" not in rules and "#8b5cf6" not in rules
    for button in ("#monthlyChallengeJoin", "#yearGoalsAdd", ".backlog-draw__btn--primary", ".quick-capture-trigger"):
        assert button in CSS, button


def test_supporter_themes_recolour_the_filled_buttons():
    block = CSS[CSS.index("body.app-shell[data-app-theme] {"):]
    block = block[:block.index("}")]
    assert "--cta: var(--accent-solid);" in block
    themes = (STATIC / "app-themes.css").read_text(encoding="utf-8")
    for colour in set(re.findall(r"--accent-solid: (#[0-9a-f]{6})", themes)):
        assert 1.05 / (_luminance(colour) + 0.05) >= 4.5, colour


def test_the_bar_only_sticks_on_wider_screens_and_anchors_clear_it():
    wide = CSS[CSS.index("@media (min-width: 769px) {"):]
    wide = wide[:wide.index("@keyframes")]
    assert "position: sticky;" in wide
    assert "html { scroll-padding-top: 112px; }" in wide
    # The account strip (bell, notifications) opens over the bar, not under it.
    assert "body.app-shell .account-toolbar { z-index: 45; }" in wide
    assert "z-index: 40;" in wide


def test_footer_has_a_button_for_each_library_and_the_ko_fi_ask():
    footer = _footer()
    buttons = re.findall(r'<button type="button" class="app-footer__lib" data-switch-tab="([a-z-]+)">', footer)
    assert tuple(buttons) == LIBRARIES
    for library in LIBRARIES:
        assert f'<button class="tab" data-switch-tab="{library}"' in INDEX or f'data-switch-tab="{library}">' in INDEX
    # A library hidden from the tab row is hidden in the footer too.
    assert "body.app-shell .app-footer__lib[hidden] { display: none; }" in CSS
    assert "link.hidden = getTabButton(link.dataset.switchTab)?.style.display === 'none';" in ACCOUNT_JS
    assert 'class="app-footer__support" href="https://ko-fi.com/omnitrackr" target="_blank" rel="noopener noreferrer"' in footer
    for heading in ("Explore", "Community", "Help", "OmniTrackr"):
        assert f"<h2>{heading}</h2>" in footer


def test_welcome_name_is_its_own_span_set_as_text():
    body = HOME_HERO[HOME_HERO.index("function setGreeting("):]
    body = body[:body.index("\n  }\n")]
    assert "el('span', 'home-hero__name', who)" in body
    assert "innerHTML" not in body
    assert "if (title) setGreeting(title, greeting(now, data.name), data.name);" in HOME_HERO
    assert '<script src="/static/home-hero.js?v=20261122-member-look-1"></script>' in INDEX
    # Without colours (Windows high contrast) the name falls back to plain text.
    assert "@media (forced-colors: active)" in CSS


def test_changelog_leads_with_the_refresh():
    assert CHANGELOG.index("member-look-nov22-2026-heading") < CHANGELOG.index("look-nov21-2026-heading")
