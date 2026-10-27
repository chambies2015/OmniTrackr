"""Library visual refresh: stylesheet order, toolbar grouping and the empty state."""
import re
from pathlib import Path

from app import dashboard_assets

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "app" / "static" / "library-refresh.css").read_text(encoding="utf-8")
APP_JS = dashboard_assets.full_source()


def test_refresh_loads_right_after_the_shelf_styles():
    links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', INDEX.split("</head>")[0])
    shelf = next(i for i, href in enumerate(links) if href.startswith("/static/library-shelf.css"))
    assert links[shelf + 1].startswith("/static/library-refresh.css?v=")


def test_each_library_groups_its_data_tools_and_keeps_their_ids():
    assert INDEX.count('<div class="library-utilities" role="group" aria-label="Library data">') == 7
    for prefix in ("Movies", "TVShows", "Anime", "Music", "Books", "VideoGames", "Manga"):
        for action in ("load", "export", "import"):
            assert f'id="{action}{prefix}"' in INDEX


def test_empty_state_reuses_existing_add_and_clear_buttons():
    assert "function renderLibraryEmptyState(table, state)" in APP_JS
    assert "renderLibraryEmptyState(table, error ? 'error'" in APP_JS
    body = APP_JS[APP_JS.index("function renderLibraryEmptyState"):APP_JS.index("async function fetchLibraryPage")]
    assert ".library-filter-reset')?.click()" in body and ".library-add-toggle" in body
    assert "innerHTML" in body and "${" not in body.split("innerHTML", 1)[1].split(";", 1)[0]


def test_edit_mode_rows_are_left_to_the_existing_styles():
    # Every card rule that moves the status badge or restyles actions skips rows being edited.
    for line in CSS.splitlines():
        if 'data-card-field="status"' in line and "position" in line:
            assert ":not(:has(input, textarea, select))" in line
    assert "prefers-reduced-motion" in CSS and "body.app-shell.dark-mode" in CSS
