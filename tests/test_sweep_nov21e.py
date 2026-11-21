"""Nov 21 midday sweep of #285 (July 2027), #288 (August 2027), #289 (September 2027) and #290 (Valentine's hub).

The pair and maker steps reduce every library title to a story key, and library titles have no length limit;
the report step reads library reviews, which have none either. These pin the bounds, and the report step
reading only the member's own rows, including a takeaway saved on the title's finish screen in an earlier month.
"""
import time
from datetime import datetime
from pathlib import Path

from app import challenges, models, title_pages

INDEX = (Path(__file__).resolve().parents[1] / "app" / "templates" / "index.html").read_text(encoding="utf-8")
SEPTEMBER = datetime(2027, 9, 10, 20, 0)
AUGUST = datetime(2027, 8, 20, 20, 0)


def _member(db_session, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True)
    db_session.add(user)
    db_session.flush()
    return user


def _row(db_session, user, model, title, finished=True, **fields):
    kind = next(kind for kind, spec in title_pages.KINDS.items() if spec[0] is model)
    row = model(user_id=user.id, title=title, **{title_pages.COMPLETE_FIELD[kind]: finished}, **fields)
    db_session.add(row)
    db_session.commit()
    return row


def _finish(db_session, user, category, row, when=SEPTEMBER, note=None):
    db_session.add(models.ActivityEntry(user_id=user.id, category=category, item_id=row.id, title=row.title,
                                        action="completed", occurred_at=when, note=note))
    db_session.commit()


def _report(db_session, user):
    return challenges.progress(db_session, user.id, "2027-09")[2]


def test_story_keys_of_long_separator_runs_take_no_time():
    # 40,000 characters of commas and spaces took about 30 seconds before runs were folded first.
    started = time.perf_counter()
    for title in ("a" + " ," * 20000 + "b", "a" + "." * 40000 + "b", "x" + " -" * 20000, "x" + " part 1" * 6000):
        challenges.story_key(title)
    assert time.perf_counter() - started < 0.5


def test_story_keys_read_only_the_start_of_a_very_long_title():
    long_title = "Dune " + "x" * 1_000_000
    assert challenges.story_key(long_title) == challenges.story_key(long_title[:challenges.STORY_KEY_CHARS])
    # The cache holds the cut title, never the million characters.
    challenges._story_key.cache_clear()
    challenges.story_key(long_title)
    assert challenges._story_key.cache_info().currsize == 1
    assert challenges.story_key(None) == challenges.story_key("") == ""


def test_story_keys_still_fold_the_same_way():
    key = challenges.story_key
    assert key("The Last of Us Part I") == key("The Last of Us: Season 1") == "last of us"
    assert key("Akira, Vol. 1") == key("Akira (Volume 1)") == key("AKIRA") == "akira"
    assert key("Dune: Part Two") == key("Dune") == "dune"
    assert key("Attack on Titan: The Final Season") == "attack on titan"
    assert key("Spider-Man: Into the Spider-Verse") == "spider man into the spider verse"
    assert key("...And Justice for All") == "and justice for all"
    assert key("Pokémon — Season 3") == key("Pokemon") == "pokemon"
    assert key("Tom & Jerry") == "tom and jerry"
    assert key("Catch-22") == "catch 22"
    assert key("千と千尋の神隠し") == "千と千尋の神隠し"


def test_report_reads_only_the_members_own_review(db_session):
    # A journal finish whose id now belongs to another member's title (SQLite can reuse the id of a removed row)
    # must not count that member's review.
    owner = _member(db_session, "reader")
    other = _member(db_session, "neighbour")
    theirs = _row(db_session, other, models.Book, "Lord of the Flies", author="William Golding",
                  review=" ".join(["private"] * 80))
    db_session.add(models.ActivityEntry(user_id=owner.id, category="books", item_id=theirs.id,
                                        title="Lord of the Flies", action="completed", occurred_at=SEPTEMBER))
    db_session.commit()
    step = _report(db_session, owner)
    assert step["done"] is False and step["best"]["words"] == 0


def test_a_takeaway_from_an_earlier_finish_counts_when_kept_writing(db_session):
    # Finished in August with a takeaway, finished again in September: "Keep writing" opens that same finish
    # screen, so what is added there has to count for September.
    user = _member(db_session, "rereader")
    book = _row(db_session, user, models.Book, "The Odyssey", author="Homer")
    db_session.add(models.CompletionMoment(user_id=user.id, category="books", item_id=book.id, title=book.title,
                                           takeaway=" ".join(["wine-dark"] * 10), completed_at=AUGUST))
    _finish(db_session, user, "books", book, note=" ".join(["sea"] * 20))
    step = _report(db_session, user)
    assert step["best"] == {"title": "The Odyssey", "category": "books", "id": book.id, "words": 30}
    moment = db_session.query(models.CompletionMoment).filter_by(user_id=user.id).one()
    moment.takeaway = " ".join(["wine-dark"] * 30)
    db_session.commit()
    assert _report(db_session, user)["done"] is True


def test_a_takeaway_saved_this_month_still_counts_once(db_session):
    user = _member(db_session, "once")
    film = _row(db_session, user, models.Movie, "12 Angry Men")
    words = " ".join(["juror"] * 30)
    _finish(db_session, user, "movies", film)
    db_session.add(models.CompletionMoment(user_id=user.id, category="movies", item_id=film.id, title=film.title,
                                           takeaway=words, completed_at=SEPTEMBER))
    db_session.commit()
    assert _report(db_session, user)["best"]["words"] == 30


def test_another_members_takeaway_on_the_same_id_never_counts(db_session):
    owner = _member(db_session, "mine")
    other = _member(db_session, "yours")
    film = _row(db_session, owner, models.Movie, "12 Angry Men")
    _finish(db_session, owner, "movies", film)
    db_session.add(models.CompletionMoment(user_id=other.id, category="movies", item_id=film.id, title="Other",
                                           takeaway=" ".join(["theirs"] * 60), completed_at=SEPTEMBER))
    db_session.commit()
    assert _report(db_session, owner)["best"]["words"] == 0


def test_a_huge_review_is_read_only_up_to_the_cap(db_session):
    user = _member(db_session, "essayist")
    album = _row(db_session, user, models.Music, "To Pimp a Butterfly", artist="Kendrick Lamar",
                 review="word " * 400_000)
    _finish(db_session, user, "music", album)
    started = time.perf_counter()
    step = _report(db_session, user)
    assert step["done"] is True
    assert time.perf_counter() - started < 1.0
    texts = challenges._reviews(db_session, user.id, [{"category": "music", "item_id": album.id}])
    assert len(texts[("album", album.id)][0]) == challenges.REPORT_TEXT_CHARS


def test_report_progress_still_takes_one_review_string():
    finish = {"category": "books", "item_id": 3, "title": "Sula", "at": SEPTEMBER, "notes": []}
    found = challenges.report_progress([finish], {("book", 3): " ".join(["nel"] * 50)})
    assert found["count"] == 1


def test_challenges_script_carries_the_sweep_tag():
    # The October (#292), November and December challenges changed challenges.js again after this sweep, so it carries a later tag.
    assert "/static/challenges.js?v=20261121-between-the-years-1" in INDEX


def _testuser(db_session):
    return db_session.query(models.User).filter(models.User.username == "testuser").one()


def _journal(db_session, user):
    return db_session.query(models.ActivityEntry).filter_by(user_id=user.id, action="completed").order_by(
        models.ActivityEntry.id).all()


def test_opening_the_finish_screen_for_a_journal_finish_logs_no_second_finish(authenticated_client, db_session):
    # "Write it" on the September card opens the finish screen for a finish the member logged in the journal.
    user = _testuser(db_session)
    book = _row(db_session, user, models.Book, "The Odyssey", author="Homer")
    db_session.add(models.ActivityEntry(user_id=user.id, category="books", item_id=book.id, title=book.title,
                                        action="completed", source="manual", occurred_at=datetime.utcnow()))
    db_session.commit()
    opened = authenticated_client.post("/completion-moments/", json={"category": "books", "item_id": book.id})
    assert opened.status_code == 200, opened.text
    db_session.expire_all()
    assert [entry.source for entry in _journal(db_session, user)] == ["manual"]


def test_a_journal_finish_from_years_ago_still_gets_todays_finish(authenticated_client, db_session):
    user = _testuser(db_session)
    book = _row(db_session, user, models.Book, "Dune", author="Frank Herbert")
    db_session.add(models.ActivityEntry(user_id=user.id, category="books", item_id=book.id, title=book.title,
                                        action="completed", source="manual", occurred_at=datetime(2020, 5, 1)))
    db_session.commit()
    assert authenticated_client.post("/completion-moments/", json={"category": "books", "item_id": book.id}).status_code == 200
    db_session.expire_all()
    assert [entry.source for entry in _journal(db_session, user)] == ["manual", "automatic"]
    # Opening it again never adds another.
    assert authenticated_client.post("/completion-moments/", json={"category": "books", "item_id": book.id}).status_code == 200
    db_session.expire_all()
    assert len(_journal(db_session, user)) == 2
