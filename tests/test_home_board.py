"""Home board refresh: dashboard cards in a main column and a rail, visual only."""
import re
from pathlib import Path

from app import dashboard_assets

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "app" / "static" / "dashboard-home.css").read_text(encoding="utf-8")
APP_JS = dashboard_assets.full_source()


def _between(start, end):
    i = INDEX.index(start)
    return INDEX[i:INDEX.index(end, i)]


def test_stylesheet_loads_before_the_dashboard_theme():
    links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', INDEX.split("</head>")[0])
    assert links[-3].startswith("/static/dashboard-home.css?v=")
    assert links[-2].startswith("/static/dashboard-2026.css?v=")


def test_daily_cards_and_badges_share_the_main_column():
    main = _between('<div class="home-board__main">', '<aside class="home-board__rail"')
    order = [main.index(f'id="{card}"') for card in ("libraryPulse", "todaysPick", "nextUpQueue", "comingUp", "badgeCase")]
    assert order == sorted(order)
    assert '<div class="daily-dashboard">' in main


def test_goals_and_extras_share_the_rail():
    rail = _between('<aside class="home-board__rail"', "</aside>")
    for card in ("seasonCard", "monthlyChallenge", "yearGoals", "installAppCard"):
        assert f'id="{card}"' in rail
    assert 'class="home-board__rail-cards"' in rail


def test_every_card_keeps_its_id_and_starts_hidden():
    for card in ("libraryPulse", "todaysPick", "nextUpQueue", "comingUp", "badgeCase",
                 "seasonCard", "monthlyChallenge", "yearGoals", "installAppCard"):
        assert INDEX.count(f'<section id="{card}"') == 1
        tag = INDEX[INDEX.index(f'<section id="{card}"'):]
        assert tag[:tag.index(">")].endswith("hidden")


def test_board_collapses_empty_columns_and_leaves_other_tabs_alone():
    assert ".home-board__rail:not(:has(.home-board__rail-cards > section:not([hidden])))" in CSS
    assert ".home-board:not(:has(section:not([hidden]))) { display: none; }" in CSS
    for tab in ("statistics", "collections", "activity", "recommendations", "friends-feed"):
        assert f'[data-active-tab="{tab}"]' in CSS


def test_phone_rail_swipes_and_starts_at_the_first_card():
    phone = CSS[CSS.index("@media (max-width: 640px)"):]
    assert "grid-auto-flow: column" in phone and "scroll-snap-type: x mandatory" in phone
    assert "function keepHomeRailAtStart()" in APP_JS
    assert "keepHomeRailAtStart();" in APP_JS


def test_open_row_menu_draws_over_the_next_row():
    theme = (ROOT / "app" / "static" / "dashboard-2026.css").read_text(encoding="utf-8")
    assert "body.app-shell td:has(details.row-menu[open]) { z-index: 30; }" in theme
