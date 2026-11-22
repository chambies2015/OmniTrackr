"""Streamlined member home (Nov 20 2026): "Do this next", card order, the "Show more" row, one card look.

Visual and order only: every card keeps its id, starts hidden and keeps its own hide button.
"""
import re
from pathlib import Path

from app import dashboard_assets

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "app" / "static" / "dashboard-home.css").read_text(encoding="utf-8")
LAYOUT = (ROOT / "app" / "static" / "home-layout.js").read_text(encoding="utf-8")
APP_JS = dashboard_assets.full_source()


def _between(start, end):
    i = INDEX.index(start)
    return INDEX[i:INDEX.index(end, i)]


def _order(html, ids):
    return [html.index(f'id="{card}"') for card in ids]


def test_do_this_next_sits_right_under_the_welcome_strip_and_starts_hidden():
    assert INDEX.index('<section id="homeHero"') < INDEX.index('<section id="homeFocus"') < INDEX.index('<section id="returnDeck"')
    tag = INDEX[INDEX.index('<section id="homeFocus"'):]
    assert tag[:tag.index(">")].endswith("hidden")
    for part in ("homeFocusCover", "homeFocusEyebrow", "homeFocusTitle", "homeFocusMeta", "homeFocusProgress", "homeFocusActions"):
        assert INDEX.count(f'id="{part}"') == 1
    # Hidden with the other home cards until the page settles, so it doesn't jump in.
    assert "html.dashboard-settling :is(#homeHero,#homeFocus," in INDEX


def test_welcome_back_deck_comes_first_above_the_board():
    order = _order(INDEX, ("homeFocus", "returnDeck", "yearInReviewBanner", "friendRecs", "starterPicks", "libraryLaunchpad"))
    assert order == sorted(order)


def test_main_column_runs_in_priority_order():
    main = _between('<div class="home-board__main">', '<aside class="home-board__rail"')
    order = _order(main, ("weekOne", "libraryPulse", "todaysPick", "onYourServices", "homeNews", "nextUpQueue", "yourWeek", "backlogDraw",
                          "stayPosted", "comingUp", "picksTeaser", "reviewInbox", "onThisDay", "badgeCase"))
    assert order == sorted(order)


def test_rail_puts_the_dated_cards_first_and_the_asks_last():
    rail = _between('<div class="home-board__rail-cards">', "</aside>")
    order = _order(rail, ("adventCard", "monthlyChallenge", "yearGoals", "awardsBallot", "yearSoFar", "seasonCard",
                          "newYearPledge", "supportAsk", "installAppCard"))
    assert order == sorted(order)


def test_show_more_row_belongs_to_the_board_and_starts_hidden():
    board = _between('<div class="home-board">', "<!-- Movies Tab Content -->")
    assert board.index("</aside>") < board.index('<div id="homeMore" class="home-board__more" hidden>')
    assert '<button type="button" id="homeMoreToggle" class="home-board__more-toggle" aria-expanded="false">' in board
    assert 'id="homeMoreStatus" class="sr-only" role="status"' in board


def test_layout_script_loads_with_the_other_home_scripts():
    scripts = re.findall(r'<script src="([^"?]+)', INDEX)
    assert scripts.index("/static/home-today.js") < scripts.index("/static/home-layout.js") < scripts.index("/static/for-you.js")


def test_dashboard_hands_continue_and_next_up_to_the_focus_and_resets_it():
    assert "window.OmniHomeFocus?.claim?.(continueItems)" in APP_JS
    assert "continueItems.slice(focused, focused + 4)" in APP_JS
    assert "window.OmniHomeFocus?.queue?.(items)" in APP_JS
    assert "window.OmniHomeFocus?.reset();" in APP_JS and "window.OmniHomeLayout?.reset();" in APP_JS
    # Today's pick steps past the focused title too.
    assert "#homeFocus .home-focus__open[data-pulse-item-id]" in APP_JS


def test_tucked_cards_hide_until_show_more_and_keep_their_own_rules():
    assert ".home-board:not(.home-board--more) .is-home-tucked { display: none !important; }" in CSS
    # Cards that only show now and then under their own rules are never tucked.
    assert "const ALWAYS = new Set(['weekOne', 'stayPosted', 'supportAsk']);" in LAYOUT
    for link in ("'#your-week': 'yourWeek'", "'#backlog-draw': 'backlogDraw'", "'#badges': 'badgeCase'", "'#goals': 'yearGoals'"):
        assert link in LAYOUT
    assert "innerHTML" not in LAYOUT


def test_one_welcome_back_layer_and_phone_trims():
    assert "body.app-shell:has(#returnDeck:not([hidden])) .home-focus { display: none; }" in CSS
    assert "body.app-shell #returnDeck:not([hidden]) ~ #libraryLaunchpad { display: none; }" in CSS
    phone = CSS[CSS.rindex("@media (max-width: 640px)"):]
    assert ".home-focus__actions:has(.episode-next.home-focus__primary) .progress-update { display: none; }" in phone
    assert "body.app-shell #starterPicks .for-you-grid" in CSS


def test_every_board_card_shares_one_surface():
    assert "body.app-shell .home-board .home-board__main > section[id]," in CSS
    assert "body.app-shell .home-board .home-board__rail-cards > section[id] {" in CSS
