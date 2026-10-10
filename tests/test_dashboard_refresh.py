"""Signed-in dashboard refresh and the speed tune-up for public pages."""
import re
from pathlib import Path

import pytest

from app import dashboard_assets

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"
INDEX = (TEMPLATES / "index.html").read_text(encoding="utf-8")
APP_JS = dashboard_assets.full_source()
THEME = (ROOT / "app" / "static" / "dashboard-2026.css").read_text(encoding="utf-8")

READER_TEMPLATES = (
    "about", "advertising", "anime_tracker", "book_tracker", "changelog", "contact", "content_quality",
    "export_import_guide", "game_tracker", "guides", "media_statistics", "media_tracker_checklist",
    "media_tracking", "movie_tracker", "music_tracker", "privacy", "review_guidelines", "roadmap",
    "sample_library", "site_map", "terms", "tracking_templates", "tv_show_tracker", "use_cases",
    "public_collection",
)


def test_dashboard_loads_the_new_theme_last():
    links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', INDEX.split("</head>")[0])
    assert links[-1].startswith("/static/dashboard-2026.css?v=")


def test_dashboard_uses_the_vortex_mark_and_a_grouped_footer():
    assert '<span class="app-brand__mark" aria-hidden="true"><img src="/vortex-still.webp"' in INDEX
    footer = INDEX[INDEX.index('id="mainFooter"'):INDEX.index("</footer>", INDEX.index('id="mainFooter"'))]
    for heading in ("Explore", "Help", "OmniTrackr"):
        assert f"<h2>{heading}</h2>" in footer
    assert "📧" not in footer and "omnitrackr@gmail.com" not in footer
    assert "Statistics Dashboard</h2>" not in INDEX


def test_widgets_hide_on_non_library_tabs():
    assert '<body class="dark-mode app-shell" data-active-tab="movies">' in INDEX
    assert "document.body.dataset.activeTab = tabName" in APP_JS
    for tab in ("statistics", "collections", "activity", "recommendations"):
        assert f'[data-active-tab="{tab}"]' in THEME


def test_row_actions_are_grouped_without_changing_handlers():
    assert "function groupRowActions(cell)" in APP_JS
    assert "groupRowActions(actions);" in APP_JS
    # The edit-mode guard keeps Save/Cancel out of the menu.
    assert "if (!primary) return; // Edit mode" in APP_JS


@pytest.mark.parametrize("template", READER_TEMPLATES)
def test_reader_pages_skip_the_dashboard_stylesheet(template):
    html = (TEMPLATES / f"{template}.html").read_text(encoding="utf-8")
    assert "/styles.css" not in html


@pytest.mark.parametrize("template", ("public_landing", "release_radar", "reviews", "discover", "faq", "compare",
                                      "collection_gallery", "collection_save", "review_save"))
def test_pages_that_needed_it_use_the_small_subset(template):
    """These pages used a few legacy rules; they now load only those (public-legacy.css, ~5 KB gzipped)."""
    html = (TEMPLATES / f"{template}.html").read_text(encoding="utf-8")
    assert "/styles.css" not in html
    assert "/static/public-legacy.css?v=" in html


def test_versioned_static_files_are_cached_for_a_year(client):
    response = client.get("/static/site.css?v=20260928-site-1")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_unversioned_static_files_are_cached_for_a_day(client):
    response = client.get("/static/site.css")
    assert response.headers["cache-control"] == "public, max-age=86400"


def test_missing_static_files_are_not_cached(client):
    response = client.get("/static/does-not-exist.css?v=1")
    assert response.status_code == 404
    assert "immutable" not in response.headers.get("cache-control", "")
