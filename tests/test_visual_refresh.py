"""October visual refresh: library Shelf view, cover tiles and guide reading aids."""
from pathlib import Path

from app import dashboard_assets

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "templates"


def test_dashboard_loads_shelf_styles_after_library_theme():
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert html.index("/static/library-theme.css") < html.index("/static/library-shelf.css")


def test_shelf_toggle_is_a_per_browser_preference_defaulting_to_list():
    source = dashboard_assets.full_source()
    assert "omnitrackr_library_view" in source
    assert "return VIEWS.includes(value) ? value : 'list';" in source
    assert "library-view-shelf" in source


def test_shelf_layout_is_desktop_only_and_keeps_edit_rows_full_width():
    css = (STATIC / "library-shelf.css").read_text(encoding="utf-8")
    assert "@media (min-width: 1025px)" in css
    assert "tr:has(input, textarea, select)" in css
    assert "grid-column: 1 / -1;" in css


def test_coverless_titles_get_a_letter_tile():
    source = dashboard_assets.full_source()
    assert "cell.dataset.initial" in source
    css = (STATIC / "library-shelf.css").read_text(encoding="utf-8")
    assert "content: attr(data-initial);" in css


def test_guides_get_reading_aids(client):
    html = client.get("/movie-tracker").text
    assert '<style data-from="public-reader.css"' in html
    assert "/static/site.js?v=20261028-nav-1" in html
    script = (STATIC / "site.js").read_text(encoding="utf-8")
    assert "reader-progress" in script and "aria-current', 'location'" in script
