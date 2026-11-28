"""Guide lines that change once their date has passed, and the Nov 27 2026 AdSense pass."""
import copy
import pickle
from datetime import date, datetime

import pytest

from app import awards, binge_calculator, challenges, corrections_log, dated_text, in_order
from app.binge_guides import GUIDES as BINGE
from app.deal_guides import GUIDE as BLACK_FRIDAY
from app.holiday_guides import GUIDES as HOLIDAY
from app.in_order_guides import GUIDES as IN_ORDER
from app.release_guides import GUIDES as RELEASES
from app.routers import binge_calculator as binge_router
from app.routers import deals_guide, new_releases, seasonal
from app.routers import in_order as in_order_router
from app.dated_text import Dated


def test_dated_text_picks_the_version_for_the_day():
    line = Dated("opens on December 4", ("2026-12-04", "opened on December 4"), ("2027-01-01", "came out last year"))
    assert str(line) == "opens on December 4"
    assert line.on(date(2026, 12, 3)) == "opens on December 4"
    assert line.on(date(2026, 12, 4)) == "opened on December 4"
    assert line.on(date(2027, 2, 1)) == "came out last year"
    assert line.versions() == ["opens on December 4", "opened on December 4", "came out last year"]
    assert type(line.on(date(2026, 12, 4))) is str


def test_resolve_walks_dicts_lists_and_tuples_and_leaves_plain_values():
    value = {"faq": (("Q", Dated("a", ("2026-12-01", "b"))),), "intro": [Dated("x", ("2026-12-01", "y")), "z"], "n": 3}
    resolved = dated_text.resolve(value, date(2026, 12, 8))
    assert resolved == {"faq": (("Q", "b"),), "intro": ["y", "z"], "n": 3}
    assert dated_text.resolve(value, date(2026, 11, 27))["intro"] == ["x", "z"]


def test_dated_text_survives_copy_and_pickle_and_rejects_bad_dates():
    line = Dated("before", ("2026-12-01", "after"))
    for clone in (copy.deepcopy(line), pickle.loads(pickle.dumps(line))):
        assert clone == "before" and clone.on(date(2026, 12, 2)) == "after"
    with pytest.raises(ValueError):
        Dated("x", ("2026-12-05", "b"), ("2026-12-01", "c"))
    with pytest.raises(ValueError):
        Dated("x", ("December 5", "b"))


def _every_dated(value):
    if isinstance(value, Dated):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _every_dated(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _every_dated(item)


def test_every_dated_line_in_the_guides_is_finished_writing():
    sources = (HOLIDAY, BLACK_FRIDAY, RELEASES, BINGE, IN_ORDER, challenges.CHALLENGES)
    found = [line for source in sources for line in _every_dated(source)]
    assert len(found) >= 15
    for line in found:
        for version in line.versions():
            assert version.strip() and "TODO" not in version and "  " not in version
            assert "—" not in version


def _companion(slug, day):
    return seasonal.companion_content(slug, HOLIDAY[slug], {}, False, day)


def test_thanksgiving_guide_reads_as_past_once_the_weekend_is_over():
    before = _companion("thanksgiving", date(2026, 11, 25))
    after = _companion("thanksgiving", date(2026, 12, 8))
    assert "falls on Thursday, November 26 this year" in before
    assert "falls on Thursday, November 26 this year" not in after
    assert "Thanksgiving 2026 was on Thursday, November 26" in after
    assert "In 2027 it falls on Thursday, November 25" in after


def test_christmas_guide_stops_calling_past_days_upcoming():
    early = _companion("christmas", date(2026, 11, 27))
    mid = _companion("christmas", date(2026, 12, 20))
    late = _companion("christmas", date(2026, 12, 28))
    assert "Violent Night 2 opens on December 4" in early
    assert "Violent Night 2 opens on December 4" not in mid
    assert "Violent Night 2 on December 4" in mid
    assert "the busiest single day was Wednesday, December 2" in mid
    assert "showed its Disney Holiday Spectacular" in mid and "iHeartRadio Jingle Ball on December 17" in mid
    assert "no runtime listed yet" not in mid
    assert "Christmas Day fell on a Friday" in late
    assert "the cinema is the safe bet" not in late


def test_black_friday_guide_after_cyber_monday():
    pages = {}
    during = deals_guide.guide_content(pages=pages, signed_in=False, today=date(2026, 11, 27))
    after = deals_guide.guide_content(pages=pages, signed_in=False, today=date(2026, 12, 8))
    assert "Black Friday is on November 27 this year" in during
    assert "Black Friday was on November 27 this year" in after
    assert "how the days fell in 2026" in after
    assert "In 2027 they fall on November 26 and November 29" in after
    assert ">Many online sales start or deepen today" not in after
    later = deals_guide.guide_content(pages=pages, signed_in=False, today=date(2027, 1, 10))
    assert "the Winter Sale ran from December 17 to January 4" in later


def test_november_release_guide_says_when_it_was_written_once_the_month_is_over():
    entry = RELEASES["november-2026"]
    during = new_releases.guide_content("november-2026", entry, {}, False, date(2026, 11, 3))
    after = new_releases.guide_content("november-2026", entry, {}, False, date(2026, 12, 8))
    assert "Most of them aren&#x27;t out yet" in during and "when and where it comes out" in during
    assert "We wrote it on November 1, before most of them were out" in after
    assert "Most of them aren&#x27;t out yet" not in after
    assert "when and where it came out" in after
    assert "Before you start:" in after and "Before it arrives:" not in after


def test_winter_guide_dates_after_december_18():
    entry = RELEASES["winter-2026-27"]
    before = new_releases.guide_content("winter-2026-27", entry, {}, False, date(2026, 12, 8))
    after = new_releases.guide_content("winter-2026-27", entry, {}, False, date(2026, 12, 20))
    assert "Doomsday open against each other" in before
    assert "Doomsday opened against each other" in after
    moth = next(pick for section in entry["sections"] for pick in section["picks"] if pick["title"] == "The Moth Reborn")
    assert moth["date"] == "2027-02-23"


def test_dune_lines_follow_part_three():
    guide = BINGE["dune"]
    before = binge_router.guide_content("dune", guide, {}, False, date(2026, 12, 8))
    after = binge_router.guide_content("dune", guide, {}, False, date(2026, 12, 20))
    assert "opens on December 18, 2026" in before and "came out on December 18, 2026" in after
    dune = IN_ORDER["dune"]
    ids = {entry["id"] for entry in dune["entries"]}
    assert "part-three" in ids
    assert all("part-three" in order["ids"] for order in dune["orders"])
    later = in_order_router.guide_content("dune", dated_text.resolve(in_order.guide("dune"), date(2026, 12, 20)), {}, False)
    assert "Is there a third Villeneuve film?" in later and "came out on December 18, 2026" in later


def test_percy_jackson_guide_no_longer_waits_for_season_three(client):
    html = client.get("/in-order/percy-jackson").text
    assert "scheduled to premiere" not in html
    assert "premiered on Disney+ and Hulu on November 20, 2026" in html or "ending on December 11" in html


def test_binge_guides_with_a_new_section_name_it_in_their_history(client):
    for slug, section_id in corrections_log._NOV27_ADDED.items():
        guide = BINGE[slug]
        assert section_id in {section for section, _, _ in guide["sections"]}, slug
        assert len(guide["sections"]) == 4, slug
        assert guide["reviewed"] == "2026-11-27", slug
        heading = next(title for section, title, _ in guide["sections"] if section == section_id)
        html = client.get(binge_calculator.path(slug)).text
        assert f'id="{section_id}"' in html
        assert heading.replace("'", "&#x27;") in html or heading in html


def test_december_challenge_has_notes(client):
    notes = challenges.CHALLENGES["2026-12"]["notes"]
    assert [note["heading"] for note in notes] == ["Four finishes in a busy month", "What December adds to your Year in Review"]
    words = sum(len(paragraph.split()) for note in notes for paragraph in note["paragraphs"])
    assert words >= 250


def test_awards_questions_change_tense_after_the_game_awards():
    before = dict(awards.season_faq(datetime(2026, 12, 1, 12)))
    after = dict(awards.season_faq(datetime(2026, 12, 20, 12)))
    question = "When does awards season start?"
    assert before[question].startswith("The Game Awards open it on December 10")
    assert after[question].startswith("The Game Awards opened it on December 10")
    show = awards.get("the-game-awards-2026")
    picks = dict(dated_text.resolve(show["faq"], date(2026, 12, 20)))
    assert picks["Can I change my picks?"].startswith("Not any more")


def test_new_log_entries_point_at_pages_that_load(client):
    changes = [change for change in corrections_log.guide_changes() if change.date == "2026-11-27"]
    assert len(changes) >= 5
    for change in changes:
        for path, line in change.pages:
            assert client.get(path).status_code == 200, path
            assert line.strip()
