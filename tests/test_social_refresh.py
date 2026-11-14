"""Nov 13 2026 visual refresh of the friends feed, watch clubs and title discussions."""
import re
from pathlib import Path

from tests.test_shared_lists import _as
from tests.test_title_discussions import API, BOARD, OPENER, _reply, _setup, _start  # noqa: F401  (fixture below)
from tests.test_title_discussions import no_posting_gap  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_discussion_posts_and_rows_show_an_initial_avatar(client, db_session):
    alice, bob = _setup(db_session)
    _as(client, alice)
    thread = _start(client)
    _as(client, bob)
    assert _reply(client, thread["id"], "Hans Zimmer's organ, every time.").status_code == 201
    page = client.get(thread["url"]).text
    assert re.search(r'<span class="disc-avatar disc-avatar--h[0-7]" aria-hidden="true">A</span>', page)
    assert re.search(r'<span class="disc-avatar disc-avatar--h[0-7] disc-avatar--small" aria-hidden="true">B</span>', page)
    assert '<span class="disc-tag disc-tag--op">Started it</span>' in page
    board = client.get(BOARD).text
    assert '<li class="disc-row"><span class="disc-avatar' in board and "<strong>1</strong> reply" in board
    assert "discussions.css?v=20261113-discussions-2" in board


def test_avatar_colour_follows_the_name():
    from app.routers.title_discussions import _avatar_html
    from app.title_discussions import Author
    one = _avatar_html(Author("dana", None, None))
    assert one == _avatar_html(Author("dana", None, None))
    assert "disc-avatar--h" in one and ">D<" in one
    assert ">?<" in _avatar_html(None)


def test_friends_feed_tab_has_the_friends_following_switch_and_rail():
    html = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    tab = html.split('<div id="friends-feed-tab" class="tab-content">', 1)[1].split("<!-- Private Activity Journal", 1)[0]
    for needle in ('role="tablist"', 'data-social-tab="friends"', 'data-social-tab="following"',
                   'id="friendsFeedPanel" class="ffeed" role="tabpanel"', 'id="followingFeed" class="ffollow" role="tabpanel"',
                   'class="social-rail"', 'id="friendsFeedSharing" role="switch"', 'id="bestRecommenders"', 'id="followSuggestions"'):
        assert needle in tab, needle
    # Every id the feed scripts look up is still on the page, once.
    for element_id in ("friendsFeedTitle", "friendsFeedAddFriend", "friendsFeedFilters", "friendsFeedStatus", "friendsFeedList",
                       "friendsFeedMore", "followingList", "followingStatus", "followingRefresh", "followSuggestionsList",
                       "bestRecommendersList", "bestRecommendersSummary", "followingCount"):
        assert html.count(f'id="{element_id}"') == 1, element_id


def test_new_styles_use_the_shared_tokens():
    feed = (STATIC / "friends-feed.css").read_text(encoding="utf-8")
    assert "#191f2c" not in feed and "var(--card-bg)" in feed and "var(--radius-lg)" in feed
    clubs = (STATIC / "shared-lists.css").read_text(encoding="utf-8")
    assert ".sl-club__bar" in clubs and ".sl-post__bubble" in clubs
