"""What December 1 and the turn of the year switch on, checked with the clock moved (Nov 24 2026 walk).

Each test pins one thing a frozen-clock walk from Nov 30 to Feb 1 found reading wrong: the homepage losing
the advent calendar on its first morning, "2026 so far" in January, founding-supporter promises after the
cutoff, reminders offered once every door had opened, and two bits of copy that read oddly at zero.
"""
from datetime import date, datetime
from html import unescape

import pytest

from app import advent_calendar as advent, editorial_index, new_year_challenge as nyc, supporters, together
from app.routers import challenges as challenges_router
from app.routers import new_year_challenge as nyc_router


@pytest.fixture
def clock(monkeypatch):
    """Move the advent calendar, the New Year challenge and the founding cutoff to one moment (UTC)."""
    monkeypatch.delenv("ADVENT_CALENDAR_OPENS", raising=False)
    monkeypatch.delenv("NEW_YEAR_CHALLENGE_OPENS", raising=False)

    def move(when: datetime):
        monkeypatch.setattr(advent, "_now", lambda: when)
        monkeypatch.setattr(nyc, "_today", lambda: when.date())
        monkeypatch.setattr(supporters, "_now", lambda: when)
        return when
    return move


# ---------------------------------------------------------------- the homepage's newest guides

def _seasonal_card(monkeypatch):
    monkeypatch.setattr(editorial_index, "entries", lambda: [
        {"section": "seasonal", "href": nyc.path(2027), "name": "The 2027 challenge", "summary": "", "updated": "2026-12-01"},
        {"section": "seasonal", "href": advent.BASE_PATH, "name": "The December advent calendar", "summary": "",
         "updated": "2026-12-01"},
        {"section": "binge", "href": "/binge-calculator/the-wire", "name": "The Wire", "summary": "", "updated": "2026-11-23"},
    ])
    return next(piece["href"] for piece in editorial_index.latest() if piece["section"] == "seasonal")


def test_the_advent_calendar_keeps_its_homepage_card_while_doors_open(clock, monkeypatch):
    clock(datetime(2026, 12, 1, 9))
    assert _seasonal_card(monkeypatch) == advent.BASE_PATH
    clock(datetime(2026, 12, 25, 11))  # Christmas Eve is still running in UTC-12
    assert _seasonal_card(monkeypatch) == advent.BASE_PATH
    clock(datetime(2026, 12, 25, 12, 30))  # every door has opened everywhere: the New Year challenge takes over
    assert _seasonal_card(monkeypatch) == nyc.path(2027)


def test_the_real_homepage_shows_the_calendar_on_december_first(client, clock):
    clock(datetime(2026, 12, 1, 12))
    page = client.get("/").text
    assert 'href="/holidays/advent-calendar"' in page.split('id="reads-title"')[1]


# ---------------------------------------------------------------- the New Year challenge in January

def test_the_challenge_lead_stops_saying_next_year_once_it_starts(clock):
    clock(datetime(2026, 12, 10, 12))
    assert "next year" in nyc.lead(2027)
    clock(datetime(2027, 1, 2, 12))
    assert "next year" not in nyc.lead(2027) and "in 2027" in nyc.lead(2027)


def test_the_challenges_page_counts_the_last_day_in_the_singular(client, clock):
    clock(datetime(2026, 12, 31, 12))
    page = client.get("/challenges").text
    assert "STARTS JANUARY 1 · 1 DAY TO GO" in page and "1 DAYS" not in page
    clock(datetime(2026, 12, 29, 12))
    assert "3 DAYS TO GO" in client.get("/challenges").text
    clock(datetime(2027, 1, 5, 12))
    page = unescape(client.get("/challenges").text)
    assert "UNDERWAY" in page and "want to finish next year" not in page


def _member(partial: bool) -> dict:
    return {"goals": {}, "started": not partial,
            "suggestions": {"year": 2026, "partial": partial, "projected": True,
                            "categories": {"books": {"done": 16, "projected": 18, "keep": 18, "more": 23, "stretch": 27}}}}


def test_the_pledge_form_says_so_far_only_while_last_year_is_running():
    assert nyc_router._row_hint("books", _member(partial=True)) == "16 in 2026 so far, about 18 at that pace"
    january = nyc_router._row_hint("books", _member(partial=False))
    assert "so far" not in january and january == "16 in 2026 since you joined, about 18 over a full year"


# ---------------------------------------------------------------- founding supporters after the cutoff

def test_the_supporters_page_stops_offering_founding_after_the_cutoff(client, clock):
    clock(datetime(2026, 12, 20, 12))
    page = unescape(client.get("/supporters").text)
    assert "Founding supporter for good if it's before 2027" in page
    assert "the first few will be founding supporters" in page
    clock(datetime(2027, 1, 2, 12))
    page = unescape(client.get("/supporters").text)
    assert "Founding supporter for good if it's before 2027" not in page
    assert "the first few will be founding supporters" not in page
    assert "No names here yet." in page


def test_the_settings_line_about_founding_can_be_hidden(authenticated_client, clock):
    clock(datetime(2027, 1, 2, 12))
    assert authenticated_client.get("/api/supporter").json()["founding_open"] is False
    clock(datetime(2026, 12, 2, 12))
    assert authenticated_client.get("/api/supporter").json()["founding_open"] is True
    dashboard = authenticated_client.get("/").text
    assert 'id="supporterFoundingLine"' in dashboard and "supporter.js?v=20261124-founding-1" in dashboard


# ---------------------------------------------------------------- the advent calendar after Christmas Eve

def test_no_morning_reminder_once_every_door_has_opened(authenticated_client, clock):
    clock(datetime(2026, 12, 20, 12))
    assert "Remind me each morning" in authenticated_client.get(advent.BASE_PATH).text
    clock(datetime(2026, 12, 26, 12))
    page = unescape(authenticated_client.get(advent.BASE_PATH).text)
    assert "Remind me each morning" not in page and "Every door is open now." in page


def test_guests_are_not_promised_reminders_after_christmas_eve(client, clock):
    clock(datetime(2026, 12, 10, 12))
    assert "get a reminder each morning" in client.get(advent.BASE_PATH).text
    clock(datetime(2027, 1, 10, 12))
    page = client.get(advent.BASE_PATH).text
    assert "get a reminder each morning" not in page and "earn the Door Opener badge" in page


def test_door_pages_count_the_open_doors_in_plain_words(client, clock):
    clock(datetime(2026, 11, 30, 12))  # door 1 has opened in UTC+14 only
    assert "1 of 24 doors is open so far" in client.get(advent.door_path(2026, 1)).text
    clock(datetime(2026, 12, 3, 12))
    assert "4 of 24 doors are open so far" in client.get(advent.door_path(2026, 1)).text
    clock(datetime(2026, 12, 28, 12))
    assert "All 24 doors are open" in client.get(advent.door_path(2026, 1)).text


# ---------------------------------------------------------------- Watch together before the first episode

class _Plan:
    unit = "episode"


def test_watch_together_never_says_youre_on_before_you_start():
    assert together.where_you_are(_Plan(), 0) == "You haven't started yet."
    assert together.where_you_are(_Plan(), 4) == "You're on episode 4."
