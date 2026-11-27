"""Home refresh (Nov 27 2026): the Today panel, three labelled groups on the board, one quiet card surface.

Visual and order only: every card keeps its id, starts hidden and keeps its own rules.
"""
import re
from pathlib import Path

from app import dashboard_assets

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "app" / "static" / "member-look.css").read_text(encoding="utf-8")
LAYOUT = (ROOT / "app" / "static" / "home-layout.js").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "app" / "templates" / "changelog.html").read_text(encoding="utf-8")
APP_JS = dashboard_assets.full_source()

GROUPS = {
    "going": ("weekOne", "libraryPulse", "breakHome", "homeNews", "nextUpQueue", "yourWeek", "backlogDraw", "rankDuel"),
    "friends": ("togetherHome", "swapHome", "yearbookHome"),
    "more": ("onYourServices", "stayPosted", "comingUp", "picksTeaser", "reviewInbox", "onThisDay", "badgeCase"),
}
LABELS = {"going": "Keep going", "friends": "With friends", "more": "More for you"}


def _main():
    start = INDEX.index('<div class="home-board__main">')
    return INDEX[start:INDEX.index('<aside class="home-board__rail"', start)]


def test_main_column_runs_in_three_labelled_groups_in_order():
    main = _main()
    labels = re.findall(r'<p class="home-board__group" data-home-group="(\w+)" hidden>([^<]+)</p>', main)
    assert labels == list(LABELS.items())
    starts = [main.index(f'data-home-group="{key}"') for key in LABELS] + [len(main)]
    for (key, cards), start, end in zip(GROUPS.items(), starts, starts[1:]):
        group = main[start:end]
        order = [group.index(f'id="{card}"') for card in cards]
        assert order == sorted(order), key
    # Every card on the board belongs to one of the groups, and none was dropped.
    ids = set(re.findall(r'<section id="(\w+)"', main)) - {"todaysPick"}
    assert ids == {c for cards in GROUPS.values() for c in cards}
    assert main.count('<div class="daily-dashboard">') == 1


def test_layout_gives_each_group_its_own_share_and_hides_empty_labels():
    assert "const GROUP_CAPS = { going: [2, 3], friends: [1, 2], more: [1, 1] };" in LAYOUT
    assert "function groupsOf(column)" in LAYOUT
    assert "if (group.label.hidden !== empty) group.label.hidden = empty;" in LAYOUT
    assert "document.querySelectorAll('.home-board__group').forEach(label => { label.hidden = true; });" in LAYOUT
    assert "innerHTML" not in LAYOUT


def test_do_this_next_waits_for_continue_when_it_loads_first():
    assert "let pulseDrawnWithoutFocus = null;" in APP_JS
    assert "window.redrawLibraryPulse = redrawLibraryPulse;" in APP_JS
    assert "if (typeof window.redrawLibraryPulse === 'function') window.redrawLibraryPulse();" in LAYOUT
    assert LAYOUT.index("window.OmniHomeFocus = {") < LAYOUT.index("window.redrawLibraryPulse();")


def test_today_panel_and_one_card_surface():
    block = CSS[CSS.index("Home refresh (Nov 27 2026)"):]
    assert "body.app-shell .home-hero:has(+ #homeFocus:not([hidden])) {" in block
    assert "body.app-shell .home-hero:not([hidden]) + .home-focus:not([hidden]) {" in block
    assert "body.app-shell .home-board :is(.home-board__main, .home-board__rail-cards) > section[id]," in block
    assert "body.app-shell .home-board__group[hidden] { display: none; }" in block
    # The next-episode button kept its dark ink on a clear background in Night Mode.
    assert "body.app-shell.dark-mode .home-focus__actions button.episode-next:not(.home-focus__primary) {" in block
    # Building blocks a new card can use without styles of its own.
    for name in (".home-card__eyebrow", ".home-card__summary", ".home-card__actions", ".home-card__go", ".home-card__quiet", ".home-card--slim"):
        assert name in block


def test_stylesheet_and_script_versions_and_changelog():
    assert INDEX.count("/static/member-look.css?v=20261127-home-refresh-1") == 1
    assert INDEX.count("/static/home-layout.js?v=20261127-home-refresh-1") == 1
    assert 'id="home-refresh-nov27-2026-heading"' in CHANGELOG
    assert CHANGELOG.index("home-refresh-nov27-2026-heading") < CHANGELOG.index("security-nov26-signin-fill-2026-heading")
