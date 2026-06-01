from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "app.js"


def test_review_modal_does_not_decode_attributes_with_inner_html():
    """Review modal should not reinterpret attribute text as HTML."""
    source = APP_JS.read_text(encoding="utf-8")
    review_modal_start = source.index("function openReviewModal")
    review_modal_end = source.index("function closeReviewModal")
    review_modal_source = source[review_modal_start:review_modal_end]

    assert "innerHTML" not in review_modal_source
    assert "replaceChildren(review)" in review_modal_source
    assert "textContent = reviewRaw" in review_modal_source
