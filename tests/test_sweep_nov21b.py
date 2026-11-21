"""Nov 21 2026 sweep of #276 (May 2027 challenge, birthday steps) and #278 (The Essential 100)."""
import inspect
import re
from types import SimpleNamespace
from urllib.parse import unquote

import pytest

from app import challenges, essentials, models, title_search
from app.main import ESSENTIALS_LIMITS
from app.routers import essentials as essentials_router
from app.routers import titles as titles_router


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    essentials._details_cache.update({"index": None, "details": None})
    yield
    title_search.clear_cache()


def user_of(db_session):
    return db_session.query(models.User).filter_by(username="testuser").one()


# ---------------------------------------------------------------- share pages and cards

@pytest.mark.parametrize("done", ["٥", "037", "+5", "05", " 5", "5 ", "1e1", "0x5"])
def test_one_list_count_has_one_address(client, done):
    # Unicode digits, leading zeros and signs used to open the same page under another address.
    assert client.get(f"/essentials/anime/score/{done}").status_code == 404
    assert client.get(f"/essentials/anime/score/{done}/card.png").status_code == 404


def test_counts_at_the_edges_still_open(client):
    assert client.get("/essentials/anime/score/0").status_code == 200
    assert client.get("/essentials/anime/score/100").status_code == 200
    assert client.get("/essentials/score/0-0-0-0-0-0-0-0-100").status_code == 200


@pytest.mark.parametrize("counts", ["01-2-3-4-5-6-7-8-9", "1-2-3-4-5-6-7-8-٩", "+1-2-3-4-5-6-7-8-9", "1-2-3-4-5-6-7-8-09"])
def test_all_nine_count_has_one_address(client, counts):
    assert client.get(f"/essentials/score/{counts}").status_code == 404
    assert client.get(f"/essentials/score/{counts}/card.png").status_code == 404


def test_share_cards_are_rate_limited():
    paths = {getattr(route, "path", None) for route in essentials_router.router.routes}
    for path in ("/essentials/score/{counts}/card.png", "/essentials/{fmt}/score/{done}/card.png"):
        assert path in paths and ESSENTIALS_LIMITS[path] == "30/minute"
    for endpoint in (essentials_router.essentials_card, essentials_router.essentials_all_card):
        # slowapi needs the request to count against.
        assert "request" in inspect.signature(endpoint).parameters


# ---------------------------------------------------------------- keep my count

def test_guest_keep_my_count_comes_back_to_the_list(client):
    html = client.get("/essentials/movies").text
    link = re.search(r'<a[^>]* class="es-save-count" href="([^"]+)"', html)
    assert link, "guests get the Keep my count link"
    href = link.group(1).replace("&amp;", "&")
    assert href.startswith("/?next=") and href.endswith("#signup")
    assert unquote(href[len("/?next="):-len("#signup")]) == "/essentials/movies#your-count"


def test_members_do_not_get_the_sign_up_link(authenticated_client):
    assert 'class="es-save-count"' not in authenticated_client.get("/essentials/movies").text


# ---------------------------------------------------------------- saves and imports

def test_seen_it_saves_a_finished_title_without_a_feed_card(authenticated_client, db_session):
    user = user_of(db_session)
    item = essentials.get("movies")["items"][7]
    body = authenticated_client.post("/api/essentials/save", json={"id": item["id"], "answer": "seen"}).json()
    assert body["state"] == "created" and body["done"] is True
    assert db_session.query(models.Movie).filter_by(user_id=user.id, title=item["title"]).one().watched is True
    # Created already finished, so the feed listener has no "finished" change to report.
    assert db_session.query(models.FriendFeedEvent).filter_by(user_id=user.id).count() == 0


def test_want_to_still_saves_unfinished(authenticated_client, db_session):
    item = essentials.get("tv")["items"][4]
    body = authenticated_client.post("/api/essentials/save", json={"id": item["id"], "answer": "want"}).json()
    assert body["done"] is False
    assert db_session.query(models.TVShow).filter_by(title=item["title"]).one().watched is False


def test_import_adds_finished_titles_without_feed_cards_and_skips_what_is_there(authenticated_client, db_session):
    user = user_of(db_session)
    films = essentials.get("movies")["items"][:6]
    books = essentials.get("books")["items"][:4]
    db_session.add(models.Movie(user_id=user.id, title="  " + films[2]["title"].upper() + " ", director="",
                                year=films[2]["year"], watched=False, rating=4.0))
    db_session.commit()
    ids = [item["id"] for item in films + books]
    body = authenticated_client.post("/api/essentials/import", json={"ids": ids + ids[:2]}).json()
    assert body == {"added": 9, "existing": 1, "missing": 0}
    kept = db_session.query(models.Movie).filter(models.Movie.rating == 4.0).one()
    assert kept.watched is False and kept.title.strip() == films[2]["title"].upper()
    assert db_session.query(models.Movie).filter_by(user_id=user.id).count() == 6
    assert all(book.read for book in db_session.query(models.Book).filter_by(user_id=user.id))
    assert db_session.query(models.FriendFeedEvent).filter_by(user_id=user.id).count() == 0
    again = authenticated_client.post("/api/essentials/import", json={"ids": ids}).json()
    assert again == {"added": 0, "existing": 10, "missing": 0}


def test_library_titles_matches_trimmed_and_cased_names(authenticated_client, db_session):
    user = user_of(db_session)
    item = essentials.get("games")["items"][0]
    db_session.add(models.VideoGame(user_id=user.id, title=f" {item['title'].lower()}  ", played=False))
    db_session.commit()
    found = essentials.library_titles(db_session, user.id, essentials.get("games")["items"])
    assert found == {("game", item["title"].casefold())}
    assert essentials.library_titles(db_session, user.id, []) == set()


# ---------------------------------------------------------------- title page answers

@pytest.mark.parametrize("text, expected", [
    ("Monkey D. Luffy sets out to sea. Then more happens.", "Monkey D. Luffy sets out to sea."),
    ("Dr. Strangelove plays it straight and the joke lands. It still works.", "Dr. Strangelove plays it straight and the joke lands."),
    ("Super Mario Bros. set the template for every platformer. Later ones built on it.",
     "Super Mario Bros. set the template for every platformer."),
    ("Mr. Robot gets inside one man's head for four seasons. It is tense.", "Mr. Robot gets inside one man's head for four seasons."),
    ("Comedy Bang! Bang! made improv a weekly habit for a decade. Guests return.",
     "Comedy Bang! Bang! made improv a weekly habit for a decade."),
    ("T. E. Lawrence crosses the desert in seventy millimetre. It is long.", "T. E. Lawrence crosses the desert in seventy millimetre."),
    ("Is it scary? Yes, very scary indeed. It is.", "Is it scary? Yes, very scary indeed."),
    ("One sentence with no full stop", "One sentence with no full stop"),
    ("", ""),
])
def test_first_sentence(text, expected):
    assert essentials.first_sentence(text) == expected


def test_every_quick_answer_is_a_whole_sentence():
    for item in essentials.all_items():
        sentence = essentials.first_sentence(item["why"])
        assert sentence and item["why"].startswith(sentence), item["id"]
        assert sentence[-1] in ".!?\"”’)", item["id"]
        assert len(sentence.split()) >= 4, item["id"]


def test_title_page_answer_says_date_order_not_rank():
    film = essentials.get("movies")["items"][0]
    group = SimpleNamespace(kind="movie", title=film["title"], year=film["year"])
    question, text, html = titles_router._essential_answer(group)
    assert question == f"Is {film['title']} one of the essential movies?" or question.startswith(f"Is {film['title']} one of")
    assert f"number {film['number']} of 100 in date order." in text
    assert text.endswith(essentials.first_sentence(film["why"]))
    assert "See it on the list</a>" in html


def test_one_piece_answer_keeps_the_whole_first_sentence():
    item = next(entry for entry in essentials.get("anime")["items"] if entry["title"] == "One Piece")
    group = SimpleNamespace(kind="anime", title=item["title"], year=item["year"])
    _, text, _ = titles_router._essential_answer(group)
    assert not text.endswith(" D.")


# ---------------------------------------------------------------- facts

def test_running_counts_are_dated_2026_not_mid_2025():
    # "Nothing that began after mid-2025" is the cut-off for new shows and stays; counts are as of 2026.
    for fmt in ("tv", "anime", "manga"):
        data = essentials.get(fmt)
        blob = " ".join([*data["lead"], data["method"], *(answer for _, answer in data["faq"])]
                        + [item["length"] + " " + item["why"] for item in data["items"]])
        assert not re.search(r"\b(?:by|as of|in) mid-2025", blob), fmt
        assert all("mid-2025" not in item["length"] for item in data["items"]), fmt


def test_finished_series_say_so():
    chainsaw = next(item for item in essentials.get("manga")["items"] if item["title"] == "Chainsaw Man")
    assert "completed 2026" in chainsaw["length"] and (chainsaw.get("extra") or {}).get("volumes", 24) == 24
    bear = next(item for item in essentials.get("tv")["items"] if item["title"] == "The Bear")
    assert bear["length"].startswith("5 seasons")


# ---------------------------------------------------------------- May 2027 birthdays

def test_turning_list_puts_undated_saves_last_on_postgres():
    source = inspect.getsource(challenges.turning_titles)
    assert "added_at.desc().nullslast()" in source
