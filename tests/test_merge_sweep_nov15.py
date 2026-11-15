"""Checks from the sweep of the Nov 15 merges (#217 security, #218 speed)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _update_metadata_body() -> str:
    script = (ROOT / "app/static/review_detail.js").read_text()
    body = script[script.index("function updateMetadata"):]
    return body[:body.index("\n}\n")]


def test_review_page_tab_title_and_previews_use_plain_text():
    # escapeHtml now turns ' into &#39;. document.title and setAttribute() take plain
    # text, so escaping there showed "Ocean&#39;s Eleven Review" in the tab and in
    # link previews. The page body still escapes (see test_security_sweep_nov15b).
    body = _update_metadata_body()
    assert "escapeHtml(" not in body
    assert "document.title = reviewTitle" in body
    assert "innerHTML" not in body


def test_review_page_script_version_moved_on():
    template = (ROOT / "app/templates/review_detail.html").read_text()
    assert "review_detail.js?v=20261115-review-quotes-2" in template
