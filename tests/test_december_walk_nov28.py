"""Fixes from the Nov 28 2026 frozen-clock walk of December 1 to February 1: words that went stale once their
day had passed, on the awards pages, the top nine tile and page, the holiday guides and the emailed fill-in page."""
from datetime import date, datetime

import pytest

from app import awards, awards_data, corrections_log, dated_text, models, top_nine, year_fill
from app.holiday_guides import GUIDES as HOLIDAY
from app.routers import deals_guide, seasonal
from app.seasonal_guides import SEASONS

GAME_AWARDS = "the-game-awards-2026"
GLOBES = "golden-globes-2027"


@pytest.fixture
def unannounced(monkeypatch):
    """Every real show without nominees, as the Globes were when this was written."""
    for slug, show in list(awards_data.SHOWS.items()):
        monkeypatch.setitem(awards_data.SHOWS, slug, dict(show, categories=[]))


def _at(monkeypatch, when):
    monkeypatch.setattr(awards, "_now", lambda: when)


# ---------------------------------------------------------------- awards

def test_every_show_has_after_words_in_the_past_tense():
    for slug in awards_data.SHOWS:
        show = awards.get(slug)
        before = awards.show_words(slug, show, datetime(2026, 11, 28))
        after = awards.show_words(slug, show, datetime(2027, 6, 1))
        assert after["lead"] != before["lead"], slug
        assert " were on " in after["lead"] and " were on " in after["description"], slug
        assert "is open" not in after["lead"] and "will " not in after["lead"], slug


def test_game_awards_page_after_the_show(client, monkeypatch):
    _at(monkeypatch, datetime(2026, 12, 1, 12))
    before = client.get(f"/awards/{GAME_AWARDS}").text
    assert "Open now on thegameawards.com" in before and "<dt>Ballots here lock</dt>" in before
    assert "The opening act starts at 4:30" in before

    _at(monkeypatch, datetime(2026, 12, 11, 1))
    after = client.get(f"/awards/{GAME_AWARDS}").text
    assert "The Game Awards 2026 were on Thursday, December 10" in after
    assert "<dt>Public vote</dt><dd>Closed</dd>" in after and "<dt>Ballots here locked</dt>" in after
    assert "The opening act started at 4:30" in after and "The show streamed free on YouTube" in after
    assert "Open now on thegameawards.com" not in after
    # The page description in the head follows the lead.
    assert "Every nominee and winner in all 30 categories" in after


def test_a_show_that_went_ahead_without_nominees_here(client, monkeypatch, unannounced):
    _at(monkeypatch, datetime(2027, 1, 15, 12))
    html = client.get(f"/awards/{GLOBES}").text
    assert "THE SHOW IS OVER" in html and "BALLOT BEING CHECKED" not in html
    assert "There was no ballot for this show" in html and 'href="/awards">awards calendar</a>' in html
    assert "The 84th Golden Globes were on Sunday, January 10, 2027" in html
    assert "Nikki Glaser was booked to host" in html and "<dt>Ballots here locked</dt>" in html
    assert 'type="radio"' not in html
    hub = client.get("/awards").text
    assert "Show over" in hub


def test_a_show_with_nominees_still_waiting_keeps_its_ballot_words(client, monkeypatch, unannounced):
    _at(monkeypatch, datetime(2026, 12, 20, 12))
    html = client.get(f"/awards/{GLOBES}").text
    assert "THE SHOW IS OVER" not in html and "There was no ballot for this show" not in html
    assert "<dt>Ballots here lock</dt>" in html


# ---------------------------------------------------------------- top nine

def test_top_nine_tile_looks_back_in_january():
    december = top_nine.tools_tile_html(date(2026, 12, 10))
    assert "New for the end of 2026" in december and "loved most this year" in december
    january = top_nine.tools_tile_html(date(2027, 1, 10))
    assert "Looking back on 2026" in january and "loved most in 2026" in january
    assert "this year" not in january and "New for the end of" not in january
    assert top_nine.tools_tile_html(date(2027, 2, 1)) == ""


def test_top_nine_page_names_the_year_in_january(client, monkeypatch):
    monkeypatch.setattr(top_nine, "_now", lambda: datetime(2027, 1, 10, 12))
    html = client.get("/top-nine").text
    assert "Pick the nine things you loved most in 2026" in html
    assert "what you loved in 2026" in html and "for the first time in 2026" in html
    assert "loved most this year" not in html and "what you loved this year" not in html


# ---------------------------------------------------------------- holiday guides

def _christmas(day):
    return seasonal.companion_content("christmas", HOLIDAY["christmas"], {}, False, day)


def test_christmas_guide_in_the_new_year():
    eve = _christmas(date(2026, 12, 24))
    assert "ABC has it on its schedule for 8 p.m. Eastern on Christmas Eve this year" in eve
    boxing = _christmas(date(2026, 12, 26))
    assert "ABC had it on its schedule for 8 p.m. Eastern on Christmas Eve 2026" in boxing
    january = _christmas(date(2027, 1, 2))
    assert "Christmas Day 2026 fell on a Friday" in january
    assert "Was there a Doctor Who Christmas special in 2026?" in january
    assert "Ebenezer was 2026" in january and "No date has been given" not in january
    assert "What Christmas specials were on TV in 2026?" in january
    assert "the Thursday after" in january


def test_black_friday_guide_through_the_winter_sale():
    pages = {}
    november = deals_guide.guide_content(pages=pages, signed_in=False, today=date(2026, 11, 28))
    assert "Grand Theft Auto VI, out since November 19" in november
    assert "due on November 19" not in november
    winter = deals_guide.guide_content(pages=pages, signed_in=False, today=date(2026, 12, 20))
    assert "the Winter Sale, which runs from December 17 to January 4" in winter
    sale_end = deals_guide.guide_content(pages=pages, signed_in=False, today=date(2027, 1, 2))
    assert "the last days of the Steam Winter Sale, which ends on January 4" in sale_end
    assert "which started on December 17 and ends on January 4" in sale_end
    assert "Was there a Steam sale on Black Friday in 2026?" in sale_end
    assert "Black Friday 2027 is on November 26" in sale_end and "next year Black" not in sale_end
    after = deals_guide.guide_content(pages=pages, signed_in=False, today=date(2027, 1, 6))
    assert "which ran from December 17 to January 4" in after and "ends on January 4" not in after


def _valentines(day):
    return seasonal.hub_content("valentines", dated_text.resolve(SEASONS["valentines"], day), {}, False, day)


def test_valentines_hub_once_february_starts():
    january = _valentines(date(2027, 1, 20))
    assert "Love in every form, opens on February 1" in january
    february = _valentines(date(2027, 2, 1))
    assert "Love in every form, opens on February 1" not in february
    assert "Love in every form, has nine more love stories" in february


# ---------------------------------------------------------------- the emailed fill-in page

def test_emailed_big_ones_page_names_the_year(client, db_session, monkeypatch):
    # The link lasts 30 days, so one sent in December can be opened in January.
    monkeypatch.setattr(year_fill, "_now", lambda: datetime(2026, 12, 3, 12))
    user = models.User(username="reader", email="reader@example.com", hashed_password="x", is_verified=True,
                       is_active=True, created_at=datetime(2026, 3, 1))
    db_session.add(user)
    db_session.commit()
    token = year_fill.make_token(user.id, 2026, [], catchup=True)
    html = client.get(f"/fill-in/{token}").text
    assert "Tap anything you watched, played, read or listened to in 2026" in html
    assert "most people got to in 2026" in html and "this year" not in html.split('class="yf-lead"')[1][:400]


def test_the_log_lists_the_pages_that_changed(client):
    change = next(change for change in corrections_log.guide_changes() if change.date == "2026-11-28")
    assert change.kind == "edited"
    for path, line in change.pages:
        assert client.get(path).status_code == 200, path
        assert line.strip() and "—" not in line
