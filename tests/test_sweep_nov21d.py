"""Nov 21 2026 morning sweep of #279-#284 and #286: the June day step's deadline, tap sizes in
Settings and the sign-up sheets, and focus after "Mark watched" on Do this next."""
import re
from datetime import datetime, timedelta
from pathlib import Path

from app import challenges, site_chrome

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
EVENING = datetime(2027, 6, 12, 20, 0)


def test_a_title_logged_twice_pairs_from_its_latest_finish():
    # Gone Home finished at 8 PM and finished again (or logged in the journal) at 6 AM: a new finish
    # pairs with the 6 AM one until 6 AM tomorrow, so the card must not say 8 PM tonight.
    finishes = [{"title": "Gone Home", "times": [EVENING, EVENING + timedelta(hours=10)]}]
    found = challenges.day_progress(finishes, "2027-06", now=EVENING + timedelta(hours=12))
    assert found["best"] == 1
    assert found["open"] == {"titles": ["Gone Home"], "count": 1, "until": "2027-06-14T06:00:00Z"}


def test_with_two_titles_waiting_the_earlier_title_decides_when_three_close():
    # For three in a day the new finish has to sit within a day of every title already in the window,
    # so the title whose latest finish came first sets the deadline.
    finishes = [{"title": "Early", "times": [EVENING]},
                {"title": "Late", "times": [EVENING + timedelta(hours=5), EVENING + timedelta(hours=8)]}]
    found = challenges.day_progress(finishes, "2027-06", target=3, now=EVENING + timedelta(hours=9))
    assert found["best"] == 2
    assert found["open"]["titles"] == ["Early", "Late"]
    assert found["open"]["until"] == "2027-06-13T20:00:00Z"


def test_the_deadline_still_stops_at_the_end_of_the_month():
    finishes = [{"title": "Last Night", "times": [datetime(2027, 6, 30, 1), datetime(2027, 6, 30, 12)]}]
    found = challenges.day_progress(finishes, "2027-06", now=datetime(2027, 6, 30, 20))
    assert found["open"]["until"] == "2027-07-01T00:00:00Z"


def test_settings_copy_buttons_are_full_size_on_phones():
    css = (STATIC / "member-phone.css").read_text(encoding="utf-8")
    block = css[css.index("/* ---------- Settings: Copy link and Copy code ---------- */"):]
    assert "@media (max-width: 760px)" in block
    rule = re.search(r"body\.app-shell \.profile-settings__copy \{([^}]*)\}", block)
    assert rule and "min-height: 44px" in rule.group(1)
    # Both buttons use that class: the profile link's Copy link and the supporter code's Copy code.
    assert 'class="profile-settings__copy" id="supporterCopyCode"' in INDEX
    assert 'class="profile-settings__copy" id="profileCopyLink"' in INDEX
    assert "/static/member-phone.css?v=20261121-sweep-d-1" in INDEX


def test_sign_up_sheet_log_in_link_has_a_tap_band_on_phones():
    css = (STATIC / "site.css").read_text(encoding="utf-8")
    phones = css[css.index("/* Phones, guest pages (Nov 21 2026). */"):]
    rule = re.search(r"\.guest-sheet__note a \{([^}]*)\}", phones)
    assert rule, "the phone block styles the sheet's Log in link"
    assert "margin-block: -12px" in rule.group(1) and "padding: 12px 4px" in rule.group(1)
    stats = (ROOT / "app" / "templates" / "site_stats.html").read_text(encoding="utf-8")
    assert f"/static/site.css?v={site_chrome.SITE_CSS_VERSION}" in stats


def test_mark_watched_parks_focus_on_the_card_heading():
    js = (STATIC / "home-layout.js").read_text(encoding="utf-8")
    button = js[js.index("function doneButton("):js.index("function started(")]
    park = button.index("$('homeFocusTitle')")
    assert "document.activeElement === button" in button
    assert park < button.index("openCompletionMoment(item.category, itemId)")
    # home-layout.js changed again in the Nov 21 afternoon sweep (OmniHomeLayout.reveal) and for "On your services".
    assert "/static/home-layout.js?v=20261122-streaming-1" in INDEX
