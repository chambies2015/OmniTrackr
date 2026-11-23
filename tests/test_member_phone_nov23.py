"""Member app phone pass, round two (Nov 23 2026): dialogs centred, Rankings rows, card menu
sheet, the streaming services picker, Watch together and Pick swap on small screens."""
import re
from pathlib import Path

from app import dashboard_assets
from app.routers import pick_swap, title_discussions, together

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "member-phone.css").read_text(encoding="utf-8")
ROUND_TWO = CSS[CSS.index("Phone pass, Nov 23 2026"):]


def _block(css: str, media: str, marker: str) -> str:
    """The @media block that holds `marker`."""
    at = css.index(marker)
    start = css.rindex(media, 0, at)
    end = css.index("\n}\n", at)
    return css[start:end]


def test_stylesheet_version_and_place_in_the_bundle():
    assert INDEX.count("/static/member-phone.css?v=20261123-phone-1") == 1
    _, _, hrefs = dashboard_assets.stylesheet_bundle()
    assert hrefs[-2].startswith("/static/member-phone.css?v=")
    assert hrefs[-1].startswith("/static/a11y.css?v=")


def test_dialog_backdrops_fit_the_screen():
    # styles.css pads the backdrop on phones while it stays 100% wide and tall.
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    phone = _block(styles, "@media (max-width: 768px)", "  .modal-overlay {\n    padding: 10px;")
    assert "padding: 10px;" in phone
    assert "body.app-shell .modal-overlay { box-sizing: border-box; }" in ROUND_TWO
    # The rank dialog is 100% wide with padding and a border; border-box keeps it on screen.
    rankings = (STATIC / "rankings.css").read_text(encoding="utf-8")
    assert re.search(r"\.rank-dialog \{[^}]*width: 100%;", rankings)
    assert "body.app-shell .rank-dialog { box-sizing: border-box; }" in _block(ROUND_TWO, "@media (max-width: 760px)", ".rank-dialog { box-sizing")


def test_rankings_rows_have_40px_buttons_under_the_title():
    phones = _block(ROUND_TWO, "@media (max-width: 640px)", "body.app-shell .rank-row {")
    assert "height: 40px; width: 40px;" in phones
    assert ".rank-row .rank-row__tools { grid-column: 3; grid-row: 2; }" in phones
    assert "white-space: normal;" in phones
    podium = _block(ROUND_TWO, "@media (max-width: 480px)", ".rank-podium { gap: 8px;")
    assert "grid-template-columns: minmax(0, 1fr);" in podium
    assert ".rank-podium__spot .rank-row__tools { grid-column: 2; grid-row: 2; }" in podium


def test_card_menu_is_a_sheet_above_the_dock():
    sheet = _block(ROUND_TWO, "@media (max-width: 760px)", ".row-menu[open] > .row-menu__panel {")
    # library.js pins the panel with inline left/top; the sheet must win over both.
    assert "left: 10px !important;" in sheet and "top: auto !important;" in sheet
    assert "bottom: calc(84px + env(safe-area-inset-bottom, 0px));" in sheet
    # The dim layer belongs to the summary, so tapping it closes the menu natively.
    assert ".row-menu[open] > summary::after" in sheet and "position: fixed;" in sheet
    # Shelf buttons have a backdrop filter, which would trap a fixed child inside the button.
    assert "backdrop-filter: none !important;" in sheet
    library = (STATIC / "dashboard" / "library.js").read_text(encoding="utf-8")
    assert "panel.style.left = `${left}px`;" in library and "panel.style.top = `${top}px`;" in library
    assert "@media (prefers-reduced-motion: reduce)" in ROUND_TWO


def test_services_picker_swipes_in_three_rows():
    picker = _block(ROUND_TWO, "@media (max-width: 640px)", ".on-services__chips {")
    assert "grid-auto-flow: column;" in picker and "grid-template-rows: repeat(3, auto);" in picker
    assert "overflow-x: auto;" in picker
    # The card's padding is 16px on phones; the row bleeds to its edges and no further.
    assert "margin-inline: -16px;" in picker


def test_together_puts_the_move_card_first_and_swipes_the_picks():
    css = (STATIC / "together.css").read_text(encoding="utf-8")
    phones = css[css.index("phones (Nov 23 2026)"):]
    assert ".tg-plan__main > .tg-move { order: -1; }" in phones
    assert ".tg-picks:not(.tg-picks--results) {" in phones and "grid-auto-flow: column;" in phones
    # The main column must stay a grid (or flex) container for order to apply.
    assert ".tg-plan__main { display: grid;" in css
    assert together.CSS_VERSION == "20261123-phone-1"


def test_swap_and_discussions_versions_moved_with_their_css():
    assert "Phones (Nov 23 2026)" in (STATIC / "pick-swap.css").read_text(encoding="utf-8")
    assert pick_swap.CSS_VERSION == "20261123-phone-1"
    assert "Phones (Nov 23 2026)" in (STATIC / "discussions.css").read_text(encoding="utf-8")
    assert title_discussions.ASSET_VERSION == "20261123-phone-1"
    titles = (ROOT / "app" / "routers" / "titles.py").read_text(encoding="utf-8")
    assert "/static/discussions.css?v=20261123-phone-1" in titles


def test_braces_balance():
    for name in ("member-phone.css", "together.css", "pick-swap.css", "discussions.css"):
        css = (STATIC / name).read_text(encoding="utf-8")
        assert css.count("{") == css.count("}"), name
