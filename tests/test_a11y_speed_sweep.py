"""Late-October accessibility and page speed sweep: no layout jumps, readable text, sensible landmarks."""
import re
from collections import Counter
from pathlib import Path

from tests.test_a11y_polish import _contrast
from tests.test_clubs import _club, _day
from tests.test_shared_lists import _new_list

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
TEMPLATES = ROOT / "app" / "templates"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dashboard_keeps_home_cards_library_and_footer_still_until_settled():
    index = _read(TEMPLATES / "index.html")
    assert "html.dashboard-settling :is(.home-board,#movies-tab,#mainFooter){visibility:hidden}" in index
    auth_js = _read(STATIC / "auth.js")
    assert "window.dashboardHomeCards = homeCards;" in auth_js
    for card in ("refreshForYou", "refreshYearGoals", "refreshMonthlyChallenge", "refreshSeasonCard", "refreshBadges"):
        assert f"window.{card}?.()" in auth_js
    home_js = _read(STATIC / "dashboard" / "home.js")
    assert "...cardRequests]).then(batch.resolve)" in home_js
    # auth.js changed, so pages must ask browsers for the new copy.
    assert "auth.js?v=20261029-account-1" in index
    assert "auth.js?v=20261029-account-1" in _read(TEMPLATES / "public_landing.html")


def test_shared_list_page_draws_its_heading_like_the_script_does(authenticated_client, db_session):
    list_id = _new_list(authenticated_client)
    page = authenticated_client.get(f"/lists/{list_id}").text
    section = re.search(r'<section class="sl-app"[^>]*>', page).group(0)
    assert 'aria-live' not in section, "each vote redraws the list; a live region would read it all out again"
    assert '<p class="sl-back"><a href="/lists">← All shared lists</a></p>' in page
    assert '<p class="eyebrow">SHARED LIST</p>' in page
    assert '<p class="sl-loading" role="status">' in page
    css = _read(STATIC / "shared-lists.css")
    assert '.sl-app[data-view="list"]:has(> .sl-loading) { min-height: 100vh; }' in css


def test_shared_list_with_a_club_says_watch_club(authenticated_client, db_session):
    _, _, list_id, first, _, _ = _club(authenticated_client, db_session)
    assert '<p class="eyebrow">SHARED LIST</p>' in authenticated_client.get(f"/lists/{list_id}").text
    started = authenticated_client.post(f"/api/lists/{list_id}/club", json={"item_id": first, "ends_on": _day(7)})
    assert started.status_code == 201, started.text
    assert '<p class="eyebrow">WATCH CLUB</p>' in authenticated_client.get(f"/lists/{list_id}").text


def test_text_that_was_too_faint_now_reads_at_4_5_to_1():
    a11y = _read(STATIC / "a11y.css")
    assert "body.app-shell .notification-time { color: var(--fg-secondary); opacity: 1; }" in a11y
    assert ".activity-diary__cell.is-future { background: transparent; border-style: dashed; opacity: 1; }" in a11y
    assert _contrast("#606b80", "#f3f5fd") >= 4.5  # light --fg-secondary on an unread notification
    assert _contrast("#2e7d32", "#f7f8fc") >= 4.5 and _contrast("#c62828", "#f7f8fc") >= 4.5
    account_js = _read(STATIC / "dashboard" / "account.js")
    assert "#4caf50" not in account_js and "classList.toggle('is-verified'" in account_js
    assert '.demo-filters button[aria-pressed="true"] { background: #7c3aed;' in _read(STATIC / "demo.css")
    assert _contrast("#ffffff", "#7c3aed") >= 4.5
    assert "border-radius: 50%; color: #f5f3ff;" in _read(STATIC / "public-landing.css")
    assert _contrast("#f5f3ff", "#374151") >= 4.5


def test_changelog_ids_are_unique_and_the_old_review_page_has_a_main_landmark():
    ids = Counter(re.findall(r'\sid="([^"]+)"', _read(TEMPLATES / "changelog.html")))
    assert [name for name, count in ids.items() if count > 1] == []
    assert '<main class="review-wrapper site-wrap">' in _read(TEMPLATES / "review_detail.html")
