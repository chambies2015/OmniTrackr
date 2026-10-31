"""OmniTrackr Daily (/daily): the puzzle bank, guess checking, pages and saving the answer (Oct 2026)."""
import re
from datetime import datetime, timedelta, timezone

import pytest

from app import daily, models, title_pages, title_search
from app.daily_puzzles import PUZZLES

COMMON = {"the", "and", "of", "a", "an", "to", "in", "into", "on", "at", "for", "from", "with", "x", "part"}


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


@pytest.fixture
def on_day(monkeypatch):
    """Pin "today" to puzzle number n (noon US Eastern)."""
    def pin(number):
        moment = datetime.combine(daily.date_for(number), datetime.min.time()) + timedelta(hours=17)
        fixed = moment.replace(tzinfo=timezone.utc)
        real = daily.now_local
        monkeypatch.setattr(daily, "now_local", lambda now=None: real(now or fixed))
    return pin


def _words(text):
    return set(re.findall(r"[a-z0-9]+", daily.normalize(text)))


def test_bank_is_complete_and_no_clue_gives_the_answer_away():
    assert len(PUZZLES) >= 120
    seen = set()
    for entry in PUZZLES:
        assert entry["kind"] in title_pages.KINDS
        assert len(entry["clues"]) == daily.MAX_GUESSES
        assert 1800 <= entry["year"] <= 2030 and entry["creator"]
        assert len(entry["note"].split()) >= 35
        key = daily.answer_id(entry)
        assert key not in seen, key
        seen.add(key)
        answer_words = {w for w in _words(entry["title"]) if len(w) >= 4 and w not in COMMON}
        for clue in entry["clues"]:
            leaked = answer_words & _words(clue)
            assert not leaked, (entry["title"], clue, leaked)


def test_guesses_ignore_case_punctuation_accents_and_a_leading_article():
    zelda = next(p for p in PUZZLES if p["title"].startswith("The Legend of Zelda"))
    for guess in ("the legend of zelda breath of the wild", "Legend of Zelda: Breath of the Wild", "BOTW",
                  "breath of the wild", "  Zelda — Breath of the Wild "):
        assert daily.is_correct(zelda, guess), guess
    assert not daily.is_correct(zelda, "Tears of the Kingdom")
    assert not daily.is_correct(zelda, "")
    spider = next(p for p in PUZZLES if p["title"].startswith("Spider-Man"))
    assert daily.is_correct(spider, "spiderman into the spiderverse")
    assert daily.is_correct(spider, "Spider Man: Into the Spider-Verse")
    frieren = next(p for p in PUZZLES if p["title"].startswith("Frieren"))
    assert daily.is_correct(frieren, "Frieren: Beyond Journey’s End") and daily.is_correct(frieren, "frieren")


def test_check_reveals_one_clue_at_a_time_and_the_answer_only_at_the_end():
    entry = daily.puzzle(1)
    first = daily.check(1, "Inception", 0)
    assert first == {"number": 1, "correct": False, "done": False, "attempt": 1, "clue": entry["clues"][1]}
    skip = daily.check(1, "", 2)
    assert skip["clue"] == entry["clues"][3] and not skip["correct"] and "answer" not in skip
    last = daily.check(1, "Gravity", 5)
    assert last["done"] and not last["correct"] and last["answer"]["title"] == entry["title"]
    won = daily.check(1, entry["title"].lower(), 0)
    assert won["done"] and won["correct"] and won["answer"]["clues"] == list(entry["clues"])


def test_numbering_follows_us_eastern_midnight():
    eve = datetime(2026, 10, 16, 3, 59, tzinfo=timezone.utc)  # 11:59 pm on Oct 15 in New York
    assert daily.today_number(eve) == 1
    assert daily.today_number(eve + timedelta(minutes=2)) == 2
    assert daily.seconds_to_next(eve) == 60
    assert daily.today_number(datetime(2026, 10, 1, tzinfo=timezone.utc)) == 0
    # Daylight saving ends on Nov 1, 2026: that night is 25 hours long.
    before = datetime(2026, 11, 1, 4, 0, tzinfo=timezone.utc)  # midnight EDT
    assert daily.seconds_to_next(before) == 25 * 3600
    assert daily.canonical_number(len(PUZZLES) + 1) == 1


def test_today_page_shows_first_clue_but_never_the_answer(client, on_day):
    on_day(3)
    response = client.get("/daily")
    assert response.status_code == 200
    html = response.text
    entry = daily.puzzle(3)
    assert '<meta name="robots" content="index, follow' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/daily">' in html
    assert 'id="dailyTool" data-number="3"' in html and "OMNITRACKR DAILY · #3" in html
    assert entry["clues"][0] in html
    assert entry["title"] not in html and entry["clues"][1] not in html and entry["note"][:60] not in html
    assert "How to play" in html and "Tips from the editors" in html
    assert 'href="/daily/2"' in html and 'href="/daily/1"' in html and "/static/daily.js?v=" in html
    assert "/static/guest-list.js?v=" in html


def test_archive_and_past_pages(client, on_day):
    on_day(3)
    archive = client.get("/daily/archive")
    assert archive.status_code == 200 and 'href="/daily/2"' in archive.text and 'href="/daily/3"' not in archive.text
    past = client.get("/daily/1")
    entry = daily.puzzle(1)
    assert past.status_code == 200
    assert "<details data-daily-spoiler>" in past.text and f"The answer: {entry['title']}" in past.text
    assert entry["note"][:60] in past.text and '<meta name="robots" content="index, follow' in past.text
    today = client.get("/daily/3", follow_redirects=False)
    assert today.status_code == 307 and today.headers["location"] == "/daily"
    assert client.get("/daily/4").status_code == 404
    assert client.get("/daily/0").status_code == 404


def test_repeat_of_the_bank_points_at_the_first_page(client, on_day):
    on_day(len(PUZZLES) + 3)
    repeat = client.get(f"/daily/{len(PUZZLES) + 1}")
    assert repeat.status_code == 200
    assert '<link rel="canonical" href="https://omnitrackr.xyz/daily/1">' in repeat.text
    assert '<meta name="robots" content="noindex' in repeat.text


def test_guess_api(client, on_day):
    on_day(2)
    entry = daily.puzzle(2)
    wrong = client.post("/api/daily/2/guess", json={"guess": "Naruto", "attempt": 0})
    assert wrong.status_code == 200 and wrong.json()["clue"] == entry["clues"][1] and "answer" not in wrong.json()
    right = client.post("/api/daily/2/guess", json={"guess": "JJK", "attempt": 1})
    body = right.json()
    assert body["correct"] and body["done"] and body["answer"]["id"] == daily.answer_id(entry)
    assert "title_url" in body["answer"]
    assert client.post("/api/daily/3/guess", json={"guess": "x", "attempt": 0}).status_code == 404
    assert client.post("/api/daily/2/guess", json={"guess": "x", "attempt": 6}).status_code == 422
    assert client.post("/api/daily/2/guess", json={"guess": "x" * 200, "attempt": 0}).status_code == 422


def _member(db_session):
    return db_session.query(models.User).filter_by(username="testuser").one()


def test_members_add_a_published_answer_but_not_a_future_one(authenticated_client, db_session, on_day):
    client = authenticated_client
    on_day(2)
    test_user = _member(db_session)
    first = daily.puzzle(1)
    added = client.post("/api/daily/add", json={"id": daily.answer_id(first)})
    assert added.status_code == 200 and added.json()["state"] == "created"
    movie = db_session.query(models.Movie).filter_by(user_id=test_user.id, title=first["title"]).one()
    assert movie.year == first["year"] and movie.director == first["creator"] and not movie.watched
    again = client.post("/api/daily/add", json={"id": daily.answer_id(first)})
    assert again.json()["state"] == "existing"
    future = daily.puzzle(10)
    assert client.post("/api/daily/add", json={"id": daily.answer_id(future)}).status_code == 404
    client.headers = {}
    client.cookies.clear()
    assert client.post("/api/daily/add", json={"id": daily.answer_id(first)}).status_code == 401


def test_guest_list_import_accepts_daily_answers(authenticated_client, db_session, on_day):
    client = authenticated_client
    on_day(5)
    test_user = _member(db_session)
    book = daily.puzzle(5)
    slug = title_pages.title_slug(book["title"], book["year"])
    response = client.post("/api/guest-list/import", json={"items": [{"kind": "book", "slug": slug}]})
    assert response.status_code == 200 and response.json()["added"] == [{"title": book["title"], "category": "books"}]
    assert db_session.query(models.Book).filter_by(user_id=test_user.id, title=book["title"]).one().author == book["creator"]


def test_sitemap_footer_and_llms_list_the_game(client, on_day):
    on_day(3)
    sitemap = client.get("/sitemap.xml").text
    assert "https://omnitrackr.xyz/daily</loc>" in sitemap and "/daily/archive</loc>" in sitemap
    assert "/daily/2</loc>" in sitemap and "/daily/3</loc>" not in sitemap
    assert 'href="/daily"' in client.get("/about").text
    assert "/daily" in client.get("/llms.txt").text
