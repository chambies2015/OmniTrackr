from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "app.js"
INDEX_HTML = Path(__file__).resolve().parents[1] / "app" / "templates" / "index.html"


def test_review_modal_does_not_decode_attributes_with_inner_html():
    """Review modal should not reinterpret attribute text as HTML."""
    source = APP_JS.read_text(encoding="utf-8")
    review_modal_start = source.index("function openReviewModal")
    review_modal_end = source.index("function closeReviewModal")
    review_modal_source = source[review_modal_start:review_modal_end]

    assert "innerHTML" not in review_modal_source
    assert "replaceChildren(review)" in review_modal_source
    assert "textContent = reviewRaw" in review_modal_source


def test_music_and_books_privacy_controls_are_wired():
    """Music and books settings should save the same fields the API exposes."""
    source = APP_JS.read_text(encoding="utf-8")
    template = INDEX_HTML.read_text(encoding="utf-8")

    for control_id in ("musicPrivate", "booksPrivate", "musicVisible", "booksVisible"):
        assert f'id="{control_id}"' in template
        assert f"document.getElementById('{control_id}')" in source

    for field_name in ("music_private", "books_private", "music_visible", "books_visible"):
        assert field_name in source


def test_library_insights_frontend_is_wired():
    """Statistics dashboard should expose and request the library insights panel."""
    source = APP_JS.read_text(encoding="utf-8")
    template = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-toggle-category-accordion="library-insights"' in template
    assert 'id="libraryInsightsStatsData"' in template
    assert "'library-insights': 'insights'" in source
    assert "displayLibraryInsights(stats)" in source
