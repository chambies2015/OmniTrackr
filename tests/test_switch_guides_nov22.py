"""Nov 22 2026 content pass: every switching guide has two sections of its own, the
corrections log records them, and an awards page whose nominees are out but not yet
loaded says so instead of giving a date that has passed."""
import re
from datetime import datetime

import pytest

from app import awards, awards_data, corrections_log, switch_guides

SLUGS = sorted(switch_guides.GUIDES)


def _main(html):
    return html[html.index('id="reader-main"'):html.index("</main>")]


@pytest.mark.parametrize("slug", SLUGS)
def test_each_switching_guide_has_its_own_sections(client, slug):
    guide = switch_guides.GUIDES[slug]
    notes = guide["notes"]
    assert len(notes) == 2
    html = client.get(f"/switch/{slug}").text
    main = _main(html)
    for note in notes:
        assert f'<h2 id="{note["id"]}">' in main
        # Listed in the page's jump links, after "What stays" and before "Import and check".
        assert f'href="#{note["id"]}"' in html
        assert main.index("stays-heading") < main.index(note["id"]) < main.index('id="import-heading"')
    assert '<time datetime="2026-11-22">November 22, 2026</time>' in main
    # The guide's own history, from the corrections log.
    assert 'id="changes-heading"' in main and "fix-kind--added" in main
    words = len(re.sub(r"<[^>]+>", " ", main).split())
    assert words >= 850, words


def test_section_ids_and_headings_are_not_shared_between_guides():
    ids = [note["id"] for slug in SLUGS for note in switch_guides.GUIDES[slug]["notes"]]
    headings = [note["heading"] for slug in SLUGS for note in switch_guides.GUIDES[slug]["notes"]]
    assert len(ids) == len(set(ids)) and len(headings) == len(set(headings))


def test_rating_table_matches_the_importer():
    table = switch_guides.GUIDES["letterboxd"]["notes"][0]["table"]
    from app.import_formats import _score
    for stars, points in table["rows"]:
        value = 0.5 if stars.startswith("½") else float(stars.split()[0].replace("½", ".5"))
        assert _score(value, 2) == points, stars


def test_corrections_log_lists_the_switching_guides(client):
    paths = {page for change in corrections_log.guide_changes() for page, _ in change.pages}
    for slug in SLUGS:
        assert switch_guides.path(slug) in paths
    fixes = corrections_log.changes_for("/switch/myanimelist")
    assert any(change.kind == "correction" for change, _ in fixes)
    html = client.get("/corrections").text
    assert "Switch from MyAnimeList" in html and 'href="/switch">12 switching guides</a>' in html
    page = client.get("/switch/goodreads").text
    assert "fix-kind--correction" in page and "(Mistborn, #1)" in page


def test_mal_guide_no_longer_says_the_file_only_has_series_totals(client):
    html = client.get("/switch/myanimelist").text
    assert "The count in the file is the series total" not in html
    assert "the import only reads the series total" in html


def _empty_show(monkeypatch, slug):
    monkeypatch.setitem(awards_data.SHOWS, slug, dict(awards_data.SHOWS[slug], categories=[]))


def test_awards_page_before_the_announcement_gives_the_date(client, monkeypatch):
    _empty_show(monkeypatch, "the-game-awards-2026")
    monkeypatch.setattr(awards, "_now", lambda: datetime(2026, 11, 12))
    html = client.get("/awards/the-game-awards-2026").text
    assert "The ballot opens when the nominees are announced" in html
    assert "NOMINEES DUE NOVEMBER 17, 2026" in html
    assert "Ballot opens November 17, 2026" in client.get("/awards").text


def test_awards_page_after_the_announcement_says_the_list_is_being_checked(client, monkeypatch):
    _empty_show(monkeypatch, "the-game-awards-2026")
    # On the day itself the old wording stays; from the next day the page catches up.
    monkeypatch.setattr(awards, "_now", lambda: datetime(2026, 11, 17, 20))
    assert "NOMINEES DUE NOVEMBER 17, 2026" in client.get("/awards/the-game-awards-2026").text
    monkeypatch.setattr(awards, "_now", lambda: datetime(2026, 11, 22))
    html = client.get("/awards/the-game-awards-2026").text
    assert "The nominees are out, and the ballot is being checked" in html
    assert "NOMINEES OUT · BALLOT BEING CHECKED" in html and "NOMINEES DUE" not in html
    assert "Tell me when the ballot opens" in html or "Make a free account to get a reminder" in html
    assert 'type="radio"' not in html
    hub = client.get("/awards").text
    assert "Ballot opening soon" in hub and "Ballot opens November 17, 2026" not in hub


def test_a_show_with_nominees_is_never_pending():
    show = dict(awards_data.SHOWS["grammys-2027"])
    assert awards.has_nominees(show)
    assert not awards.nominees_pending(show, datetime(2027, 1, 1))
