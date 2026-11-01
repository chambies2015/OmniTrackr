"""Grouped header menus, title search, the fuller footer and the dashboard's phone bar."""
from pathlib import Path

import pytest

from app import site_chrome

INDEX = Path("app/templates/index.html").read_text(encoding="utf-8")
SITE_JS = Path("app/static/site-nav.js").read_text(encoding="utf-8")
APP_NAV_JS = Path("app/static/app-nav.js").read_text(encoding="utf-8")


def header(html):
    return html[html.index('<header class="site-header'):html.index("</header>")]


def test_every_header_entry_is_reachable_from_a_menu_and_the_compact_sheet(client):
    nav = header(client.get("/faq").text)
    assert nav.count('<details class="site-dd') == len(site_chrome.NAV_MENUS) == 4
    sheet = nav[nav.index('<details class="site-menu">'):]
    for _, _, href in site_chrome.NAV_ITEMS:
        assert nav.count(f'href="{href}"') >= 2, href  # once in a dropdown, once in the phone sheet
        assert f'href="{href}"' in sheet
    assert len({key for key, _, _ in site_chrome.NAV_ITEMS}) == len(site_chrome.NAV_ITEMS)


@pytest.mark.parametrize("path, menu, href", [("/daily", "play", "/daily"), ("/tier-list", "play", "/tier-list"),
                                              ("/in-order/star-wars", "guides", "/in-order"),
                                              ("/release-radar", "explore", "/release-radar"),
                                              ("/reviews", "community", "/reviews")])
def test_the_menu_holding_the_current_page_is_marked(client, path, menu, href):
    nav = header(client.get(path).text)
    assert f'<details class="site-dd is-current" data-menu="{menu}">' in nav
    assert nav.count("site-dd is-current") == 1
    assert f'href="{href}" aria-current="page"' in nav


def test_search_and_library_buttons_degrade_without_scripts(client):
    nav = header(client.get("/discover").text)
    assert '<a class="site-search" href="/titles" data-site-search' in nav
    assert 'class="site-nav__library site-btn site-btn--primary site-btn--sm" href="/" hidden>My library</a>' in nav
    assert "/api/titles/search?q=" in SITE_JS and "textContent" in SITE_JS and "innerHTML" not in SITE_JS
    assert "localStorage.getItem('omnitrackr_user')" in SITE_JS


def test_member_only_pages_show_the_library_button_from_the_start():
    nav = site_chrome.site_nav("lists", member=True)
    assert '<header class="site-header is-member">' in nav
    assert 'href="/">My library</a>' in nav and 'href="/" hidden>My library' not in nav
    assert "Start tracking" not in nav and "Log in" not in nav


def test_header_extras_load_everywhere_but_the_sandboxed_demo(client):
    assert "/static/site-nav.js?v=" in client.get("/discover").text
    assert "/static/site-nav.js?v=" in client.get("/faq").text
    assert "/static/site-nav.js?v=" not in client.get("/demo").text


def test_footer_lists_every_group_and_a_legal_line(client):
    html = client.get("/about").text
    footer = html[html.index('<footer class="site-footer">'):]
    for title, links in site_chrome.FOOTER_GROUPS:
        assert f"<h2>{title}</h2>" in footer
        for _, href in links:
            assert f'href="{href}"' in footer
    base = footer[footer.index("site-footer__base"):]
    for _, href in site_chrome.FOOTER_LEGAL:
        assert f'href="{href}"' in base
    for href in ("/lists", "/supporters", "/roadmap", "/taste-quiz", "/best-of"):
        assert f'href="{href}"' in footer


def test_dashboard_phone_bar_reuses_the_existing_handlers():
    dock = INDEX[INDEX.index('<nav id="appDock"'):INDEX.index("</nav>", INDEX.index('<nav id="appDock"'))]
    assert 'data-action="open-quick-capture"' in dock
    assert 'data-switch-tab="friends-feed"' in dock and 'data-switch-tab="movies"' in dock
    assert 'class="tab' not in dock  # core.js treats .tab elements as the tab strip
    sheet = INDEX[INDEX.index('<dialog id="appMoreSheet"'):INDEX.index("</dialog>", INDEX.index('<dialog id="appMoreSheet"'))]
    for target in ("userDisplay", "showFriendsSidebar", "toggleMode", "logoutBtn", "installAppBtn", "siteStatsLink"):
        assert f'data-click-target="{target}"' in sheet
        assert f'id="{target}"' in INDEX
    assert '<script src="/static/app-nav.js?v=' in INDEX and '/static/app-nav.css?v=' in INDEX


def test_phone_sheet_mirrors_the_tab_strip_instead_of_copying_it():
    assert ".tab[data-switch-tab]" in APP_NAV_JS
    assert "tab.style.display !== 'none'" in APP_NAV_JS
    assert "innerHTML" not in APP_NAV_JS


def test_signed_out_homepage_does_not_get_the_dashboard_bar(client):
    html = client.get("/").text
    assert 'id="appDock"' not in html and "app-nav.js" not in html
