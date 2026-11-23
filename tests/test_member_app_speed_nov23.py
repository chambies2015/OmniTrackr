"""Member app speed pass (Nov 23 2026): whole-page restyles, the card rail, early home requests, fewer queries."""
import re
from pathlib import Path

from sqlalchemy import event

from app import dashboard_assets, models, review_inbox, review_spoilers
from tests.test_title_pages import ESSAY, LONG_REVIEW, add_movie

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
HOME_JS = (STATIC / "dashboard" / "home.js").read_text(encoding="utf-8")
PREFETCH = (STATIC / "home-prefetch.js").read_text(encoding="utf-8")


def _dashboard_css() -> str:
    css, _, _ = dashboard_assets.stylesheet_bundle()
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_no_has_rule_restyles_the_whole_page():
    # In Chrome, a :has() on html or body, or a "> *" straight after a :has(), makes every
    # change anywhere on the page restyle all of it (about 4,000 elements on the home page).
    css = _dashboard_css()
    assert not re.findall(r"(?<![\w-])(?:html|body|:root)(?:[.#\[:][^\s{,>~+]*)?:has\(", css)
    assert not re.findall(r":has\([^{}]*?\)\s*>\s*\*", css)


def test_footer_libraries_and_home_cards_use_sibling_rules_instead():
    css = _dashboard_css()
    assert "body.app-shell .app-footer__lib[hidden] { display: none; }" in css
    assert "body.app-shell .home-focus:has(~ #returnDeck:not([hidden])) { display: none; }" in css
    assert ":is(:has(~ #homeFocus:not([hidden])), :has(~ #returnDeck:not([hidden])))" in css


def test_card_rail_waits_for_scroll_events_instead_of_watching_every_change():
    body = HOME_JS[HOME_JS.index("function keepHomeRailAtStart()"):]
    body = body[:body.index("\n  }\n")]
    assert "MutationObserver" not in body
    assert "rail.addEventListener('scroll'" in body


def test_home_requests_start_before_the_page_scripts():
    tag = '<script src="/static/home-prefetch.js?v=20261123-prefetch-1"></script>'
    assert INDEX.count(tag) == 1
    scripts = re.findall(r'<script src="([^"]+)"', INDEX)
    # First of the end-of-body run, so the requests start while the rest download.
    assert scripts.index("/static/home-prefetch.js?v=20261123-prefetch-1") + 1 == scripts.index("./credentials.js")
    assert INDEX.index(tag) > INDEX.index("</main>")


def test_early_requests_leave_out_cards_that_read_the_visit_count():
    addresses = re.findall(r"\['[\w-]+', [`']([^`']+)[`']\]", PREFETCH)
    assert len(addresses) >= 35
    for left_out in ("/api/badges", "/api/stay-posted", "/api/support-ask"):
        assert not any(address.startswith(left_out) for address in addresses), left_out
    # Writes drop every early answer; only the visit pings are let through.
    assert "const HARMLESS_WRITE = /^\\/(account\\/visit|api\\/visit|api\\/[\\w/-]+\\/(event|seen))$/;" in PREFETCH
    assert "innerHTML" not in PREFETCH


def _book(db, user, title, review):
    book = models.Book(user_id=user.id, title=title, author="Author", year=2001, review=review)
    db.add(book)
    db.flush()
    return book


def _statements(db, run):
    statements = []

    def note(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", note)
    try:
        result = run()
    finally:
        event.remove(db.bind, "before_cursor_execute", note)
    return result, statements


def test_review_inbox_checks_every_format_in_one_query_per_table(db_session):
    me = db_session.query(models.User).filter_by(username="testuser").first()
    if me is None:
        me = models.User(username="testuser", email="speed@example.com", hashed_password="x", is_verified=True)
        db_session.add(me)
        db_session.flush()
    shown = add_movie(db_session, me, review=ESSAY)
    praised = add_movie(db_session, me, title="Arrival", year=2016, review=LONG_REVIEW)
    db_session.add(models.ReviewReaction(category="movie", item_id=praised.id, visitor_hash="reader"))  # was public once
    book = _book(db_session, me, "The Left Hand of Darkness", ESSAY)
    flagged = _book(db_session, me, "Piranesi", LONG_REVIEW)
    review_spoilers.set_flag(db_session, "book", flagged, True)
    db_session.commit()

    data, statements = _statements(db_session, lambda: review_inbox.candidates(db_session, me))
    by_key = {(item["category"], item["id"]): item for item in data["items"]}
    assert set(by_key) == {("movie", shown.id), ("book", book.id), ("book", flagged.id)}
    assert by_key[("book", flagged.id)]["spoilers"] is True and by_key[("movie", shown.id)]["spoilers"] is False
    for table in ("review_reactions", "public_review_states", "review_spoilers"):
        assert sum(1 for sql in statements if f"FROM {table}" in sql) == 1, table
