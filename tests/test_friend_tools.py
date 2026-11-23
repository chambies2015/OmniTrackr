"""Pick swap and Watch together, pointed out where they fit (Nov 23 2026, app/friend_tools.py)."""
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app import friend_tools, home_today, models, pick_swap, seasonal, together
from tests.test_title_pages import member

ROOT = Path(__file__).resolve().parents[1]
LANDING = (ROOT / "app" / "templates" / "public_landing.html").read_text(encoding="utf-8")
INDEX = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
IN_SEASON = date(2026, 11, 23)
OFF_SEASON = date(2027, 2, 10)


@pytest.fixture
def in_season(monkeypatch):
    monkeypatch.setattr(friend_tools, "swap_season", lambda today=None: True)


@pytest.fixture
def off_season(monkeypatch):
    monkeypatch.setattr(friend_tools, "swap_season", lambda today=None: False)


def _befriend(db, a, b):
    low, high = sorted([a.id, b.id])
    db.add(models.Friendship(user1_id=low, user2_id=high))
    db.flush()


def test_swap_season_runs_from_mid_november_to_december_22():
    assert not friend_tools.swap_season(date(2026, 11, 14))
    assert friend_tools.swap_season(date(2026, 11, 15))
    assert friend_tools.swap_season(IN_SEASON)
    assert friend_tools.swap_season(date(2026, 12, 22))
    assert not friend_tools.swap_season(date(2026, 12, 23))
    assert not friend_tools.swap_season(OFF_SEASON)


@pytest.mark.parametrize("path", ["/holidays", "/holidays/christmas", "/holidays/thanksgiving",
                                  "/holidays/reading-and-listening", "/holidays/gifts"])
def test_holiday_guides_point_guests_at_the_guide_pages(client, path):
    page = client.get(path).text
    section = page[page.index('<section class="ft-callout'):]
    section = section[:section.index("</section>")]
    assert "WITH YOUR PEOPLE" in section
    assert 'href="/swap"' in section and 'href="/swap#start"' not in section
    if path != "/holidays/gifts":
        assert 'href="/together"' in section
    # It sits before the questions, after the guide itself.
    assert page.index('id="with-friends"') < page.index('id="faq"')


def test_members_go_straight_to_the_start_forms(authenticated_client):
    page = authenticated_client.get("/holidays/christmas").text
    assert 'href="/swap#start"' in page and 'href="/together#start"' in page
    assert "Start a pick swap" in page and "Plan one" in page


def test_other_seasons_and_unknown_pages_get_nothing(client):
    assert friend_tools.callout_html("halloween", False) == ""
    assert "ft-callout" not in client.get("/halloween").text
    assert "ft-callout" not in client.get("/valentines-day").text


def test_callout_copy_is_escaped_and_needs_no_inline_styles():
    for page in friend_tools.CALLOUTS:
        html = friend_tools.callout_html(page, False)
        assert "style=" not in html  # the strict CSP blocks style attributes on these pages
        assert "'" not in re.sub(r"<[^>]+>", "", html)  # apostrophes come out as &#x27;


def _card_text(page, tool, today):
    html = friend_tools.callout_html(page, False, today)
    card = html[html.index(f'ft-card--{tool}'):]
    return card[:card.index("</article>")]


def test_christmas_morning_lines_give_way_after_the_swap_season():
    # Up to Dec 22 a swap can still unwrap on Christmas morning; from Dec 23 the copy stops promising it.
    for page in ("christmas", "thanksgiving"):
        assert "Christmas morning" in _card_text(page, "swap", date(2026, 12, 22))
        assert "Christmas morning" not in _card_text(page, "swap", date(2026, 12, 23))
        assert "Christmas morning" not in _card_text(page, "swap", date(2026, 12, 31))
        # Read in the new year, the guide is about next Christmas again.
        assert "Christmas morning" in _card_text(page, "swap", date(2027, 1, 2))
    assert "day after Christmas" in _card_text("christmas", "together", date(2026, 12, 26))
    assert "day after Christmas" not in _card_text("christmas", "together", date(2026, 12, 27))
    assert "day after Christmas" in _card_text("christmas", "together", date(2027, 11, 20))
    # Pages without a late version keep their copy all year.
    assert _card_text("holidays", "swap", date(2026, 12, 28)) == _card_text("holidays", "swap", IN_SEASON)
    for (page, tool), (day, text) in friend_tools.LATE_DECEMBER.items():
        assert any(item[0] == tool for item in friend_tools.CALLOUTS[page]["tools"])
        assert 1 <= day < 31 and text
        html = friend_tools.callout_html(page, False, date(2026, 12, 31))
        assert "'" not in re.sub(r"<[^>]+>", "", html)  # apostrophes escaped in the late copy too


def test_thanksgiving_heading_reads_right_after_the_weekend():
    assert friend_tools.CALLOUTS["thanksgiving"]["heading"] == "Drawing names at Thanksgiving?"


def test_guide_pages_use_the_server_date_for_the_late_copy(client, monkeypatch):
    from app.routers import seasonal as seasonal_router

    class LateDecember(date):
        @classmethod
        def today(cls):
            return cls(2026, 12, 28)

    monkeypatch.setattr(seasonal_router, "date", LateDecember)
    page = client.get("/holidays/christmas").text
    section = page[page.index('<section class="ft-callout'):]
    section = section[:section.index("</section>")]
    assert "Christmas morning" not in section and "day after Christmas" not in section
    assert "Nobody finds out who had whom until unwrap day" in section


def test_season_card_lists_pick_swap_after_the_gift_guide_in_season(authenticated_client, monkeypatch, in_season):
    monkeypatch.setattr(seasonal, "current", lambda today=None: "holidays")
    paths = [link["path"] for link in authenticated_client.get("/api/seasonal/current").json()["links"]]
    assert paths[paths.index("/holidays/gifts") + 1] == "/swap"
    assert paths.count("/swap") == 1


def test_season_card_leaves_pick_swap_out_after_december_22(authenticated_client, monkeypatch, off_season):
    monkeypatch.setattr(seasonal, "current", lambda today=None: "holidays")
    paths = [link["path"] for link in authenticated_client.get("/api/seasonal/current").json()["links"]]
    assert "/swap" not in paths
    assert friend_tools.season_card_links("valentines", IN_SEASON) == []


def test_homepage_hero_line_only_in_season(client, monkeypatch):
    monkeypatch.setattr(friend_tools, "swap_season", lambda today=None: True)
    page = client.get("/").text
    assert 'class="lp-hero__news"' in page and 'href="/swap" data-home-tool="swap"' in page
    assert page.index("lp-hero__news") < page.index('id="hero-title"')
    monkeypatch.setattr(friend_tools, "swap_season", lambda today=None: False)
    page = client.get("/").text
    assert "lp-hero__news" not in page and "<!--HERO_NEWS-->" not in page


def test_homepage_feature_cards_link_both_guides():
    features = LANDING[LANDING.index('id="features"'):]
    features = features[:features.index("</section>")]
    assert features.count('<article class="lp-feature') == 8
    assert 'href="/swap" data-home-tool="swap"' in features
    assert 'href="/together" data-home-tool="together"' in features
    assert "style=" not in features
    css = (ROOT / "app/static/public-landing.css").read_text(encoding="utf-8")
    assert ".lp-tour { grid-template-columns: repeat(4, minmax(0, 1fr)); }" in css
    assert "/static/public-landing.css?v=20261123-friends-1" in LANDING


def _swap(db, host, today):
    swap = pick_swap.create(db, host, name="Family picks", note=None, kinds=[], draw_on=None,
                            reveal_on=today + timedelta(days=20), tz=0, wish=None, today=today)
    db.commit()
    return swap


def test_home_idea_offers_pick_swap_in_season_until_you_are_in_one(db_session, in_season):
    me = member(db_session, "maya")
    idea = home_today.build(db_session, me, now=datetime(2026, 11, 23, 12))["idea"]
    assert idea["tool"] == "swap" and idea["key"] == "swap-2026" and idea["path"] == "/swap#start"
    swap = _swap(db_session, me, date.today())
    assert home_today.build(db_session, me, now=datetime(2026, 11, 23, 12))["idea"] is None
    # Unwrapped or called off, the swap no longer counts.
    swap.cancelled_at = datetime.utcnow()
    db_session.commit()
    assert home_today.build(db_session, me, now=datetime(2026, 11, 23, 12))["idea"]["tool"] == "swap"


def test_home_idea_offers_watch_together_the_rest_of_the_year(db_session, off_season):
    me = member(db_session, "maya")
    idea = home_today.build(db_session, me, now=datetime(2027, 2, 10, 12))["idea"]
    assert idea == {"key": "together", "tool": "together", "title": "Watch together",
                    "text": idea["text"], "path": "/together#start", "label": "Plan one"}
    row = models.TVShow(user_id=me.id, title="Severance", year=2022)
    db_session.add(row)
    db_session.flush()
    together.create(db_session, me, row, "tv-shows", total=10, pace=2, starts_on=date.today(), today=date.today(),
                    season=1)
    db_session.commit()
    assert home_today.build(db_session, me, now=datetime(2027, 2, 10, 12))["idea"] is None


def test_home_idea_never_breaks_the_card(db_session, monkeypatch):
    me = member(db_session, "maya")

    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(friend_tools, "home_idea", broken)
    data = home_today.build(db_session, me, now=datetime(2026, 11, 23, 12))
    assert data["idea"] is None and "friends" in data


def test_api_sends_the_idea(authenticated_client, in_season):
    data = authenticated_client.get("/api/home/today").json()
    assert data["idea"]["tool"] == "swap"


def test_home_script_and_styles_are_asked_for_again():
    assert "/static/home-today.js?v=20261123-friends-1" in INDEX
    assert "/static/dashboard-home.css?v=20261123-friends-1" in INDEX
    css = (ROOT / "app/static/dashboard-home.css").read_text(encoding="utf-8")
    assert "body.app-shell .home-news__idea {" in css


def test_changelog_says_what_moved():
    changelog = (ROOT / "app/templates/changelog.html").read_text(encoding="utf-8")
    assert 'id="friend-tools-nov23-2026-heading"' in changelog
    assert changelog.index("friend-tools-nov23-2026") < changelog.index("security-nov23-founding-2026")
