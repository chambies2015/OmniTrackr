"""Guest pages on phones (Nov 21 2026): the Start tracking sheet marker, tap areas,
16px form boxes, and crosslink cards that list each shared title once."""
from pathlib import Path

from app import funnel, guest_signup, guide_links, html_finish, site_chrome

ROOT = Path(__file__).resolve().parents[1]
SITE_CSS = (ROOT / "app/static/site.css").read_text(encoding="utf-8")
SITE_NAV = (ROOT / "app/static/site-nav.js").read_text(encoding="utf-8")


def _google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")


def _phone_block() -> str:
    start = SITE_CSS.index("/* Phones, guest pages (Nov 21 2026). */")
    return SITE_CSS[start:]


def test_public_pages_are_marked_for_the_sheet_when_google_is_set_up(client, monkeypatch):
    _google(monkeypatch)
    for path in ("/in-order/star-wars", "/binge-calculator/breaking-bad", "/movie-tracker", "/faq", "/discover"):
        page = client.get(path).text
        assert page.count('data-signup-sheet="google"') == 1, path
    # The homepage holds the sign-up form itself.
    assert "data-signup-sheet" not in client.get("/").text


def test_no_sheet_without_google(client, monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    assert "data-signup-sheet" not in client.get("/in-order/star-wars").text


def test_marker_rules(monkeypatch):
    _google(monkeypatch)
    page = '<html><body class="site"><header class="site-header"></header><a href="/#signup">Start</a></body></html>'
    marked = html_finish.finish(page)
    assert marked.count('data-signup-sheet="google"') == 1
    assert guest_signup.mark_signup_pages(marked) == marked
    # Member pages, pages with the sign-up form and pages without a sign-up link are left alone.
    assert "data-signup-sheet" not in guest_signup.mark_signup_pages(page.replace('"site-header"', '"site-header is-member"'))
    assert "data-signup-sheet" not in guest_signup.mark_signup_pages(page.replace("</body>", '<form id="registerForm"></form></body>'))
    assert "data-signup-sheet" not in guest_signup.mark_signup_pages(page.replace('href="/#signup"', 'href="/about"'))
    # Both sheet markers can sit on one page: a guest with saved titles gets Keep your list.
    both = html_finish.finish(page.replace("</body>", "<div data-guest-bar></div></body>"))
    assert 'data-guest-sheet="google"' in both and 'data-signup-sheet="google"' in both


def test_sheet_events_are_counted():
    names = {"signup_sheet_opened", "signup_sheet_google", "signup_sheet_email", "signup_sheet_login"}
    assert names <= funnel.CLIENT_EVENTS and names <= funnel.SERVER_EVENTS
    labels = dict(funnel.GUEST)
    assert all(labels[name].startswith("Phones:") for name in names)


def test_sheet_script_is_phone_only_and_links_to_google():
    sheet = SITE_NAV[SITE_NAV.index('"Start tracking" opens a small sheet'):]
    assert "matchMedia('(max-width: 760px)')" in sheet
    assert "'/auth/google/start'" in sheet and "'/#signup'" in sheet and "'/#login'" in sheet
    assert "signupSheet !== 'google'" in sheet
    assert site_chrome.SITE_NAV_JS_VERSION >= "20261121-phone"
    assert site_chrome.SITE_CSS_VERSION >= "20261121-phone"


def test_phone_form_boxes_are_16px_so_iphones_do_not_zoom():
    block = _phone_block()
    assert 'body.site input:not([type="checkbox"]):not([type="radio"]):not([type="range"]), body.site select, body.site textarea { font-size: max(16px, 1em); }' in block


def test_small_links_get_a_44px_tap_band_without_moving():
    block = _phone_block()
    for selector in (".trail-guide > .hero > a:first-child", ".reader-crumbs a", ".title-crumbs a", ".io-progress__link",
                     ".bc-track__link", ".site-header .site-brand"):
        assert f"body.site {selector}::after" in block, selector
    assert "content: \"\"; height: 44px;" in block and "transform: translateY(-50%)" in block
    assert "body.site .guide-related-grid article h3 a::after { content: \"\"; inset: 0; position: absolute; }" in block


def test_crosslink_cards_list_each_shared_title_once():
    seen_pages = 0
    for piece in guide_links.editorial_index.entries():
        for link in guide_links.related(piece["href"]):
            assert len(set(link["shared"])) == len(link["shared"]), (piece["href"], link["href"], link["shared"])
        seen_pages += 1
    assert seen_pages > 50
    star_wars = guide_links.related("/in-order/star-wars")
    assert star_wars and all(len(set(link["shared"])) == len(link["shared"]) for link in star_wars)


def test_star_wars_crosslinks_render_distinct_names(client):
    page = client.get("/in-order/star-wars").text
    start = page.index("data-guide-crosslinks")
    section = page[start:page.index("</section>", start)]
    for card in section.split("<article>")[1:]:
        if "Also covers" not in card:
            continue
        names = [part.split("</em>")[0] for part in card.split("Also covers", 1)[1].split("</strong>")[0].split("<em>")[1:]]
        assert len(names) == len(set(names)), names


def test_guide_save_bars_are_one_slim_row_on_phones():
    block = _phone_block()
    assert "body.site :is(.io-bar, .yl-bar, .bc-bar, .dc-bar) { border-radius: 16px;" in block and "flex-wrap: nowrap" in block
    assert "body.site :is(.io-bar, .yl-bar, .bc-bar, .dc-bar, .search-guestbar, .x-dock) .guest-count__ask { display: none; }" in block
    guest_list = (ROOT / "app/static/guest-list.js").read_text(encoding="utf-8")
    assert "ask.className = 'guest-count__ask';" in guest_list


def test_every_page_loads_the_new_guest_list_script(client):
    stale = [path for path in (ROOT / "app").rglob("*") if path.suffix in (".py", ".html")
             and "guest-list.js?v=20261118-sheet-1" in path.read_text(encoding="utf-8")]
    assert stale == []
    assert "/static/guest-list.js?v=20261121-phone-1" in client.get("/in-order/star-wars").text


def test_essentials_lists_offer_a_titles_only_view(client):
    page = client.get("/essentials/movies").text
    assert '<button type="button" class="es-view" aria-pressed="false" data-es-view hidden>Titles only</button>' in page
    assert "/static/essentials.js?v=20261121-phone-1" in page and "/static/essentials.css?v=20261121-phone-1" in page
    css = (ROOT / "app/static/essentials.css").read_text(encoding="utf-8")
    assert '.es-guide[data-es-view="titles"] .es-item__why, .es-guide[data-es-view="titles"] .es-item__start { display: none; }' in css
    assert ".es-tracker--stuck .es-view { display: none; }" in css
    # The notes stay in the page for readers and search engines; only the view changes.
    assert page.count('class="es-item__why"') == 100


def test_editorial_paragraphs_get_room_between_them(client):
    discover_css = (ROOT / "app/static/discover.css").read_text(encoding="utf-8")
    rule = ".editorial p + p { margin-top: 12px; }"
    assert rule in discover_css
    # Written before the reflection rule so that one keeps its own 14px.
    assert discover_css.index(rule) < discover_css.index(".guide-reflection p + p { margin-top: 14px; }")
    for path in ("/pick", "/tier-list", "/daily", "/discover", "/challenges"):
        assert "/static/discover.css?v=20261121-phone-1" in client.get(path).text, path
    assert "body.site.public-reader .sample-card p + p { margin-top: 8px; }" in SITE_CSS


def test_browse_byline_sits_below_the_deck(client):
    css = (ROOT / "app/static/browse.css").read_text(encoding="utf-8")
    assert ".browse-page .site-hero .browse-byline { margin-top: 20px; }" in css
    assert "/static/browse.css?v=20261121-phone-1" in client.get("/browse/manga").text


def test_in_order_rows_open_from_anywhere_on_phones():
    block = _phone_block()
    assert "body.site .io-rows li { position: relative; }" in block
    assert 'body.site .io-row__text a::after { border-radius: 14px; content: ""; inset: 0; position: absolute; }' in block
    assert site_chrome.SITE_CSS_VERSION >= "20261121-phone-2"
