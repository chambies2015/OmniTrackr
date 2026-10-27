"""Taste quiz (/taste-quiz): a one-minute deck that fills a new library and picks what to try next (Oct 2026)."""
import json
import re

import pytest

from app import funnel, models, pick, taste_quiz, title_pages, title_search


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


def _deck(html):
    match = re.search(r'<script[^>]*id="tasteQuizDeck"[^>]*>(.*?)</script>', html, re.S)
    assert match
    return json.loads(match.group(1))


def test_deck_covers_four_formats_and_every_link_resolves():
    ids = [taste_quiz.card_id(card) for card in taste_quiz.DECK]
    assert len(ids) == len(set(ids)) == 24
    counts = {kind: sum(card["kind"] == kind for card in taste_quiz.DECK) for kind in taste_quiz.KINDS}
    assert counts == {"movie": 6, "tv": 6, "anime": 6, "game": 6}
    # The first four cards show every format.
    assert {card["kind"] for card in taste_quiz.DECK[:4]} == set(taste_quiz.KINDS)
    for card in taste_quiz.DECK:
        assert card.get("guide") or card.get("next"), card["title"]
        if card.get("guide"):
            from app import if_you_liked
            guide = if_you_liked.guide(card["guide"])
            assert guide is not None and guide["anchor"]["title"] == card["title"]
        for pick_id in card.get("next", ()):
            assert pick.find_id(pick_id) is not None, pick_id
        if card["kind"] in ("movie", "album", "book"):
            assert card.get("creator")


def test_suggestions_follow_loved_titles_and_skip_what_you_have():
    picks = taste_quiz.suggestions([("movie/interstellar-2014", "loved"), ("game/minecraft-2011", "liked")])
    assert 1 <= len(picks) <= taste_quiz.SUGGESTION_LIMIT
    titles = {p["title"] for p in picks}
    assert "Arrival" in titles  # The Interstellar guide's closest match.
    assert all(p["because"] in ("Interstellar", "Minecraft") for p in picks)
    assert all(p["why"] for p in picks)
    # At most two picks per inspiring title keeps the list varied.
    assert sum(p["because"] == "Interstellar" for p in picks) <= 2
    owned = {("movie", title_pages.slugify("Arrival"))}
    again = taste_quiz.suggestions([("movie/interstellar-2014", "loved")], owned=owned)
    assert "Arrival" not in {p["title"] for p in again}
    # Only "Not for me" answers: nothing positive to go on.
    assert taste_quiz.suggestions([("movie/interstellar-2014", "meh")]) == []
    # Unknown ids and answers are ignored.
    assert taste_quiz.suggestions([("movie/not-a-card", "loved"), ("movie/interstellar-2014", "bogus")]) == []


def test_answered_deck_titles_are_never_suggested():
    answers = [("movie/spider-man-into-the-spider-verse-2018", "loved"),
               ("movie/everything-everywhere-all-at-once-2022", "liked")]
    titles = {p["title"] for p in taste_quiz.suggestions(answers, limit=20)}
    assert "Everything Everywhere All at Once" not in titles
    assert "Spider-Man: Into the Spider-Verse" not in titles


def test_page_works_for_visitors_and_stays_out_of_search(client):
    response = client.get("/taste-quiz")
    assert response.status_code == 200
    html = response.text
    assert '<meta name="robots" content="noindex, follow">' in html
    assert response.headers["x-robots-tag"] == "noindex, follow"
    assert 'id="tasteQuiz"' in html and 'data-signed-in="false"' in html
    assert "/static/taste-quiz.js?v=" in html and "/static/guest-list.js?v=" in html
    assert "your answers stay in this browser" in html
    cards = _deck(html)
    assert [card["id"] for card in cards] == [taste_quiz.card_id(card) for card in taste_quiz.DECK]
    assert cards[0]["guide"] == "/if-you-liked/interstellar"
    assert "<noscript>" in html


def test_member_page_saves_to_the_library(authenticated_client):
    html = authenticated_client.get("/taste-quiz").text
    assert 'data-signed-in="true"' in html
    assert "/static/guest-list.js" not in html
    assert "Everything goes straight into your library" in html


def test_visitor_suggestions_store_nothing(client, db_session):
    response = client.post("/api/taste-quiz/suggestions", json={
        "answers": [{"id": "tv/stranger-things-2016", "answer": "loved"}, {"id": "anime/death-note-2006", "answer": "want"}],
        "kinds": ["tv", "anime"]})
    assert response.status_code == 200
    rows = response.json()["suggestions"]
    assert rows and all({"id", "title", "why", "because", "image", "url"} <= set(row) for row in rows)
    assert all(pick.find_id(row["id"]) for row in rows)
    assert db_session.query(models.TVShow).count() == 0
    assert client.post("/api/taste-quiz/suggestions", json={"answers": [{"id": "tv/stranger-things-2016", "answer": "nope"}]}).status_code == 422


def test_save_needs_an_account(client):
    response = client.post("/api/taste-quiz/save", json={"answers": [{"id": "movie/interstellar-2014", "answer": "loved"}]})
    assert response.status_code == 401


def test_save_adds_titles_with_ratings_and_leaves_existing_ones_alone(authenticated_client, db_session):
    client = authenticated_client
    user = db_session.query(models.User).first()
    # Already in the library with the member's own rating and review.
    db_session.add(models.Movie(user_id=user.id, title="interstellar", director="Christopher Nolan", year=2014,
                                rating=6.5, watched=False, review="Mine"))
    db_session.commit()
    response = client.post("/api/taste-quiz/save", json={"answers": [
        {"id": "movie/interstellar-2014", "answer": "loved"},
        {"id": "tv/breaking-bad-2008", "answer": "loved"},
        {"id": "anime/attack-on-titan-2013", "answer": "liked"},
        {"id": "game/hades-2020", "answer": "meh"},
        {"id": "game/elden-ring-2022", "answer": "want"},
        {"id": "game/elden-ring-2022", "answer": "loved"},
        {"id": "movie/not-in-the-deck", "answer": "loved"},
    ], "kinds": ["movie", "tv", "anime", "game"]})
    assert response.status_code == 200
    data = response.json()
    assert [row["title"] for row in data["existing"]] == ["interstellar"]
    assert {row["title"] for row in data["added"]} == {"Breaking Bad", "Attack on Titan", "Hades", "Elden Ring"}
    db_session.expire_all()
    mine = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert (mine.title, mine.rating, mine.watched, mine.review) == ("interstellar", 6.5, False, "Mine")
    show = db_session.query(models.TVShow).filter_by(user_id=user.id).one()
    assert (show.title, show.year, show.rating, show.watched) == ("Breaking Bad", 2008, 9.0, True)
    anime = db_session.query(models.Anime).filter_by(user_id=user.id).one()
    assert (anime.rating, anime.watched) == (7.0, True)
    hades = db_session.query(models.VideoGame).filter_by(user_id=user.id, title="Hades").one()
    assert (hades.rating, hades.played, hades.release_date.year) == (4.0, True, 2020)
    # The first answer for a card wins; Want to means not started and unrated.
    elden = db_session.query(models.VideoGame).filter_by(user_id=user.id, title="Elden Ring").one()
    assert (elden.rating, elden.played) == (None, False)
    suggested = {row["title"] for row in data["suggestions"]}
    assert suggested and "Better Call Saul" in suggested
    # Saving again changes nothing.
    again = client.post("/api/taste-quiz/save", json={"answers": [{"id": "tv/breaking-bad-2008", "answer": "meh"}]}).json()
    assert again["added"] == [] and [row["title"] for row in again["existing"]] == ["Breaking Bad"]
    db_session.expire_all()
    assert db_session.query(models.TVShow).filter_by(user_id=user.id).one().rating == 9.0


def test_suggestions_skip_titles_already_in_the_library(authenticated_client, db_session):
    user = db_session.query(models.User).first()
    db_session.add(models.TVShow(user_id=user.id, title="Better Call Saul", year=2015))
    db_session.commit()
    data = authenticated_client.post("/api/taste-quiz/save", json={"answers": [
        {"id": "tv/breaking-bad-2008", "answer": "loved"}]}).json()
    assert "Better Call Saul" not in {row["title"] for row in data["suggestions"]}


def test_art_lookup_only_answers_for_deck_cards(client):
    assert client.get("/api/taste-quiz/art/movie/not-a-card").status_code == 404
    response = client.get("/api/taste-quiz/art/movie/interstellar-2014")
    assert response.status_code == 200
    assert response.json() == {"image": None}
    assert response.headers["cache-control"] == "no-store"


def test_cached_member_artwork_is_used(client, db_session):
    for index in range(2):
        user = models.User(email=f"art{index}@example.com", username=f"artfan{index}", hashed_password="x", is_active=True)
        db_session.add(user)
        db_session.flush()
        db_session.add(models.Anime(user_id=user.id, title="Attack on Titan", year=2013,
                                    poster_url="https://img.example.com/aot.jpg"))
    db_session.commit()
    response = client.get("/api/taste-quiz/art/anime/attack-on-titan-2013")
    assert response.json() == {"image": "https://img.example.com/aot.jpg"}
    assert response.headers["cache-control"] == "public, max-age=86400"
    # The page itself never carries artwork.
    assert all("image" not in card for card in _deck(client.get("/taste-quiz").text))


def test_quiz_events_are_counted_on_site_stats():
    events = {item["event"] for item in funnel.summary({})["guest"]}
    assert {"quiz_started", "quiz_finished", "quiz_imported", "quiz_saved"} <= events
    assert {"quiz_started", "quiz_saved"} <= funnel.CLIENT_EVENTS
    assert "quiz_finished" not in funnel.CLIENT_EVENTS


def test_pick_add_accepts_the_quiz_as_a_source(authenticated_client):
    response = authenticated_client.post("/api/pick/add", json={"id": "movie/arrival-2016", "source": "taste-quiz"})
    assert response.status_code == 200 and response.json()["state"] == "created"


def test_dashboard_and_sign_up_point_to_the_quiz(authenticated_client):
    html = authenticated_client.get("/").text
    assert 'href="/taste-quiz"' in html
    assert "/static/taste-quiz.js?v=" in html
    from pathlib import Path
    auth_js = (Path(__file__).parents[1] / "app" / "static" / "auth.js").read_text(encoding="utf-8")
    assert "link.href = '/taste-quiz';" in auth_js
