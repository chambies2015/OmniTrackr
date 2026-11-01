"""Overlapping sections share one header entry, paired pages carry a view switch,
and the dashboard's Explore menu and phone sheet come from the same list as the site header."""
from pathlib import Path

import pytest

from app import site_chrome

INDEX = Path("app/templates/index.html").read_text(encoding="utf-8")
HOME_JS = Path("app/static/dashboard/home.js").read_text(encoding="utf-8")


def header(html):
    return html[html.index('<header class="site-header'):html.index("</header>")]


def test_overlapping_pages_no_longer_have_their_own_header_entries():
    hrefs = [href for _, _, href in site_chrome.NAV_ITEMS]
    for href in ("/tonight", "/new-this-week", "/titles/movie"):
        assert href not in hrefs
    for href in ("/pick", "/release-radar", "/titles"):
        assert hrefs.count(href) == 1


@pytest.mark.parametrize("path, menu, href", [("/tonight", "play", "/pick"),
                                              ("/titles/movie", "explore", "/titles")])
def test_a_paired_page_marks_the_entry_it_belongs_to(client, path, menu, href):
    nav = header(client.get(path).text)
    assert f'<details class="site-dd is-current" data-menu="{menu}">' in nav
    assert f'href="{href}" aria-current="true"' in nav
    assert 'aria-current="page"' not in nav


@pytest.mark.parametrize("path, current, other", [("/pick", "/pick", "/tonight"),
                                                  ("/tonight", "/tonight", "/pick"),
                                                  ("/release-radar", "/release-radar", "/new-this-week"),
                                                  ("/titles", "/titles", "/titles/movie"),
                                                  ("/titles/anime", "/titles/movie", "/titles")])
def test_paired_pages_show_a_switch_to_the_other_view(client, path, current, other):
    html = client.get(path).text
    switch = html[html.index('<nav class="site-switch"'):]
    switch = switch[:switch.index("</nav>")]
    assert f'href="{current}" aria-current="page"' in switch
    assert f'href="{other}">' in switch


def test_footer_does_not_repeat_the_legal_line():
    legal = {href for _, href in site_chrome.FOOTER_LEGAL}
    columns = [href for _, links in site_chrome.FOOTER_GROUPS for _, href in links]
    assert len(columns) == len(set(columns))
    assert not legal & set(columns)
    for href in ("/tonight", "/new-this-week", "/titles/movie"):
        assert href in columns  # Still one click from every page.


def test_dashboard_explore_menu_and_sheet_follow_the_site_header():
    assert site_chrome.APP_EXPLORE_MARKER in INDEX and site_chrome.APP_SHEET_EXPLORE_MARKER in INDEX
    assert "↗</a>" not in INDEX[INDEX.index('<nav class="tabs"'):INDEX.index("</nav>", INDEX.index('<nav class="tabs"'))]
    html = site_chrome.apply_app_chrome(INDEX)
    menu = html[html.index('<details class="app-explore">'):html.index("</details>", html.index('<details class="app-explore">'))]
    sheet = html[html.index('<dialog id="appMoreSheet"'):html.index("</dialog>", html.index('<dialog id="appMoreSheet"'))]
    for _, label, href in site_chrome.NAV_ITEMS:
        assert f'href="{href}"' in menu and f'href="{href}"' in sheet, href
    assert 'class="tab' not in menu  # core.js treats .tab elements as the tab strip


def test_signed_in_root_fills_the_markers(client):
    client.cookies.set("omnitrackr_session", "x")
    html = client.get("/").text
    assert site_chrome.APP_EXPLORE_MARKER not in html and site_chrome.APP_SHEET_EXPLORE_MARKER not in html


def test_todays_pick_steps_past_titles_already_in_continue():
    assert "function pickRepeatsContinue" in HOME_JS and "function skipRepeatedPick" in HOME_JS
    assert "#libraryPulseContinue [data-pulse-item-id]" in HOME_JS
    assert "Math.min(2, todaysPickCandidateCount - 1)" in HOME_JS  # Bounded, so it never loops.
