"""Library view, Nov 20 2026: title page colours, a poster wall Shelf, drawn covers and filter chips with counts."""
import re
from pathlib import Path

from app import dashboard_assets

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "library-view.css").read_text(encoding="utf-8")
EXPLORE = (STATIC / "explore.css").read_text(encoding="utf-8")
HOME_HERO = (STATIC / "home-hero.js").read_text(encoding="utf-8")
QUICK = (STATIC / "library-quick.js").read_text(encoding="utf-8")
APP_JS = dashboard_assets.full_source()

TABS = {"movies": "movie", "tv-shows": "tv", "anime": "anime", "video-games": "game", "music": "album",
        "books": "book", "manga": "manga", "podcasts": "podcast", "audiobooks": "audiobook"}


def test_stylesheet_loads_between_workspace_and_accessibility_layers():
    links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', INDEX.split("</head>")[0])
    names = [href.split("?")[0] for href in links]
    view = names.index("/static/library-view.css")
    assert names[view - 1] == "/static/workspace-2026.css"
    # The member phone layer (Nov 21 2026) sits between the library view and accessibility.
    assert names[view + 1] == "/static/member-phone.css"
    assert names[view + 2] == "/static/a11y.css"


def test_each_library_uses_the_title_page_colour():
    explore = dict(re.findall(r'\[data-kind="(\w+)"\] \{ --kind: (#[0-9a-f]{6}); \}', EXPLORE))
    assert len(explore) == 9
    for tab, kind in TABS.items():
        match = re.search(rf'#{tab}-tab\) \{{ --fmt-hue: \d+; --kind: (#[0-9a-f]{{6}}); \}}', CSS)
        assert match, tab
        assert match.group(1) == explore[kind], tab


def test_rules_that_move_actions_or_marks_skip_rows_being_edited():
    # Edit mode keeps the earlier layout: any rule that places the actions or the
    # finished mark leaves rows with fields alone (reduced motion only drops transitions).
    for line in CSS.splitlines():
        if " tr" not in line or not re.search(r'data-card-field="(actions|status)"', line):
            continue
        if "transition: none" in line or line.rstrip().endswith(","):
            continue
        assert ":not(:has(input, textarea, select))" in line, line


def test_no_transform_on_shelf_rows_so_the_fixed_menu_stays_put():
    shelf_row = "tbody tr:not(:has(input, textarea, select)) {"
    block = CSS[CSS.index(shelf_row):CSS.index("}", CSS.index(shelf_row))]
    assert "transform: none;" in block


def test_drawn_cover_is_attributes_only_and_called_for_every_cover_cell():
    assert "drawLibraryCover(cell, row.cells[1]?.firstChild?.textContent.trim() || name);" in APP_JS
    assert "content: attr(data-cover-title);" in CSS
    assert "[data-cover-title]:empty::after" in CSS
    # The letter tile is still the fallback in List and on phone cards.
    assert "content: attr(data-initial);" in (STATIC / "library-shelf.css").read_text(encoding="utf-8")


def test_chip_counts_come_from_the_shelf_summary():
    body = APP_JS[APP_JS.index("function renderLibraryFilters"):APP_JS.index("function applyLibraryFilters")]
    assert body.rstrip().endswith("window.syncLibraryFilterCounts = syncLibraryFilterCounts;")
    assert "syncLibraryFilterCounts(category);\n}" in body
    assert "panel.dataset.shelfTotal = String(Number(library.total) || 0);" in HOME_HERO
    assert "window.syncLibraryFilterCounts(library.key)" in HOME_HERO
    assert "delete panel.dataset.shelfTotal;" in HOME_HERO
    assert "line.style.setProperty('--done'" in HOME_HERO
    assert "button[data-count]::after" in CSS


def test_quick_marks_refresh_the_counts():
    # Since the Nov 20 evening sweep a quick save asks once, after a short pause (test_sweep_nov20c).
    assert "(hero?.refreshSoon || hero?.refresh)?.();" in QUICK
    assert '<script src="/static/library-quick.js?v=20261120-sweep-1"></script>' in INDEX
    assert '<script src="/static/home-hero.js?v=20261120-sweep-1"></script>' in INDEX


def test_filter_checkboxes_stay_in_the_page_for_keyboards():
    rule = CSS[CSS.index(".library-filter-option > input[type=\"checkbox\"] {"):]
    rule = rule[:rule.index("}")]
    assert "clip-path: inset(50%);" in rule and "display: none" not in rule
    assert ":has(> input:focus-visible)" in CSS


def test_phone_sort_keeps_its_label_and_options_readable():
    assert 'aria-label="Sort this library"' in INDEX
    assert "select.library-sort option { background: var(--card-bg); color: var(--fg); }" in CSS


def test_reduced_motion_is_respected():
    assert "@media (prefers-reduced-motion: reduce)" in CSS
