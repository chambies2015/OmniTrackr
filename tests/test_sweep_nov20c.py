"""Nov 20 2026 evening sweep of #264 (February challenge), #265 (library view) and #266 (public pages).

The browser walk (desktop, phone, 320 px, light and dark) is in the memory note; these pin the fixes.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
LIBRARY_VIEW = (STATIC / "library-view.css").read_text(encoding="utf-8")
HOME_CSS = (STATIC / "dashboard-home.css").read_text(encoding="utf-8")
HOME_HERO = (STATIC / "home-hero.js").read_text(encoding="utf-8")
QUICK = (STATIC / "library-quick.js").read_text(encoding="utf-8")
LIBRARY_JS = (STATIC / "dashboard" / "library.js").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "app" / "templates" / "changelog.html").read_text(encoding="utf-8")


def _phone_block(css: str) -> str:
    start = css.index("@media (max-width: 760px) {\n  body.app-shell .library-section:not(#lv) .library-panel > .library-heading h2")
    return css[start:css.index("\n}\n", start)]


def test_library_heading_wraps_on_the_smallest_phones():
    # "Audiobooks" at 1.3rem plus the List/Shelf switch was 339 px wide on a 320 px screen.
    block = _phone_block(LIBRARY_VIEW)
    assert ".library-panel > .library-heading { flex-wrap: wrap;" in block
    assert ".library-panel > .library-heading > .library-heading__tools { margin-left: auto; }" in block


def test_open_shelf_menu_sits_above_the_next_covers():
    corner = re.search(r"td\.library-cell\[data-card-field=\"actions\"\] \{[^}]*z-index: (\d+);", LIBRARY_VIEW)
    assert corner, "the cover-corner actions have their own stacking layer"
    rule = re.search(r"([^{}]+):has\(details\.row-menu\[open\]\) \{ position: relative; z-index: (\d+); \}", LIBRARY_VIEW)
    assert rule and int(rule.group(2)) > int(corner.group(1))
    # Both the plain corner and the expanded-card layout are covered.
    assert rule.group(1).count(":has(details.row-menu[open])") == 1
    assert "tr:not(.card-expanded):not(:has(input, textarea, select)) td.library-cell[data-card-field=\"actions\"]:has(details.row-menu[open])" in LIBRARY_VIEW


def test_row_menu_placement_counts_the_phone_dock():
    place = LIBRARY_JS[LIBRARY_JS.index("const place = () => {"):LIBRARY_JS.index("menu.rowMenuPlace = place;")]
    assert "getElementById('appDock')" in place
    assert "floor - 8" in place and "window.innerHeight - 8" not in place


def test_quick_saves_refresh_the_shelf_numbers_once():
    assert "hero?.refreshSoon || hero?.refresh" in QUICK
    assert "window.OmniHomeHero?.refresh?.();" not in QUICK
    assert "window.OmniHomeHero = { refresh, refreshSoon, reset, render };" in HOME_HERO
    assert "seq < state.shown" in HOME_HERO


def test_challenge_step_button_drops_under_its_label_on_narrow_cards():
    assert "body.app-shell .month-challenge__step { flex-wrap: wrap;" in HOME_CSS
    assert "body.app-shell .month-challenge__step > .month-challenge__label { flex: 1 1 9rem; min-width: 0; }" in HOME_CSS


def test_changed_files_have_new_version_tags():
    for tag in ('/static/library-view.css?v=20261120-sweep-1', '/static/dashboard-home.css?v=20261121-sweep-1',
                '/static/library-quick.js?v=20261120-sweep-1', '/static/home-hero.js?v=20261120-sweep-1'):
        assert tag in INDEX, tag


def test_changelog_mentions_the_sweep():
    assert 'id="security-nov20c-2026-heading"' in CHANGELOG
    assert CHANGELOG.index("security-nov20c-2026-heading") < CHANGELOG.index("library-nov20-2026-heading")
