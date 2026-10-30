"""Compare tastes (/u/<name>/match): opt-in, privacy, the deck, scoring, saving answers, share card."""
import pytest

from app import auth, models, taste_compare
from app.middleware import PUBLIC_PROFILE_PATH
from tests.test_public_profiles import enable, headers_for, member


@pytest.fixture(autouse=True)
def fresh_decks():
    taste_compare.DECK_CACHE.clear()
    yield
    taste_compare.DECK_CACHE.clear()


def shelf(db, user):
    db.add_all([
        models.Movie(user_id=user.id, title="Interstellar", director="Christopher Nolan", year=2014, rating=10, watched=True,
                     review="Private thoughts on the docking scene.", poster_url="https://img.example/i.jpg"),
        models.Movie(user_id=user.id, title="Arrival", director="Denis Villeneuve", year=2016, rating=9, watched=True),
        models.Movie(user_id=user.id, title="Cats", director="Tom Hooper", year=2019, rating=2, watched=True),
        models.TVShow(user_id=user.id, title="Severance", year=2022, rating=9, watched=True),
        models.VideoGame(user_id=user.id, title="Hades", rating=8, played=True),
        models.Book(user_id=user.id, title="Dune", author="Frank Herbert", year=1965, rating=9, read=True),
        models.Book(user_id=user.id, title="Secret Diary", author="Me", year=2020, rating=10, read=True),
        models.Movie(user_id=user.id, title="Unrated", director="Someone", year=2010, rating=None, watched=False),
    ])
    db.commit()


def ids(cards):
    return {card["title"]: card["id"] for card in cards}


def test_link_is_off_until_the_member_switches_it_on(client, db_session):
    owner = member(db_session, "dana")
    shelf(db_session, owner)
    assert client.get("/u/dana/match").status_code == 404  # no profile at all
    profile = enable(db_session, owner)
    assert client.get("/u/dana/match").status_code == 404  # public profile, link still off
    assert client.get("/u/dana/match/card.png").status_code == 404
    assert client.post(f"/api/taste-match/u/{owner.id}/guess", json={"answers": []}).status_code == 404
    assert 'href="/u/dana/match"' not in client.get("/u/dana").text

    profile.show_taste_match = True
    db_session.commit()
    page = client.get("/u/dana/match")
    assert page.status_code == 200
    assert "noindex" in page.headers["x-robots-tag"] and 'content="noindex, follow"' in page.text
    assert "How does your taste compare with dana&#x27;s?" in page.text
    assert 'og:image" content="https://omnitrackr.xyz/u/dana/match/card.png"' in page.text
    assert 'href="/u/dana/match"' in client.get("/u/dana").text
    # Switching the whole profile off takes the link down too.
    profile.enabled = False
    db_session.commit()
    assert client.get("/u/dana/match").status_code == 404


def test_deck_hides_ratings_and_private_categories(client, db_session):
    owner = member(db_session, "dana", books_private=True)
    shelf(db_session, owner)
    enable(db_session, owner, show_taste_match=True)
    cards = taste_compare.deck(db_session, owner)
    titles = {card["title"] for card in cards}
    assert titles == {"Interstellar", "Arrival", "Cats", "Severance", "Hades"}
    assert all("rating" not in card for card in cards)
    page = client.get("/u/dana/match").text
    assert "Secret Diary" not in page and "Dune" not in page and "Private thoughts" not in page
    assert '"rating"' not in page and "Unrated" not in page
    # A low rating makes it in so a match can disagree, and formats are mixed up front.
    assert "Cats" in titles
    assert len({card["category"] for card in cards[:3]}) == 3


def test_deck_prefers_titles_other_members_know(db_session):
    owner = member(db_session, "dana")
    for number in range(20):
        db_session.add(models.Movie(user_id=owner.id, title=f"Obscure {number:02d}", year=2000, rating=9, watched=True))
    db_session.add(models.Movie(user_id=owner.id, title="Paddington 2", year=2017, rating=9, watched=True))
    other = member(db_session, "other")
    db_session.add(models.Movie(user_id=other.id, title="paddington 2", year=2017, rating=7, watched=True))
    db_session.commit()
    cards = taste_compare.deck(db_session, owner)
    assert len(cards) == taste_compare.DECK_SIZE
    assert cards[0]["title"] == "Paddington 2"


def test_guest_guess_scores_answers_without_storing_anything(client, db_session):
    owner = member(db_session, "dana")
    shelf(db_session, owner)
    enable(db_session, owner, show_taste_match=True)
    deck = ids(taste_compare.deck(db_session, owner))
    before = db_session.query(models.Movie).count()
    response = client.post(f"/api/taste-match/u/{owner.id}/guess", json={"answers": [
        {"id": deck["Interstellar"], "answer": "loved"},   # 10 -> loved: full agreement
        {"id": deck["Arrival"], "answer": "liked"},        # 9 -> loved vs liked: 0.6
        {"id": deck["Cats"], "answer": "loved"},           # 2 -> meh vs loved: 0
        {"id": deck["Severance"], "answer": "skip"},
        {"id": deck["Hades"], "answer": "want"},
        {"id": "books:999999", "answer": "loved"},         # not one of hers: ignored
    ]})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["rated_count"] == 3
    assert data["score"] == round((1 + 0.6 + 0) / 3 * 100) == 53
    assert data["tier"] == "Some common ground"
    assert [item["title"] for item in data["agreed"]] == ["Interstellar"]
    assert [item["title"] for item in data["disagreements"]] == ["Cats"]
    assert data["disagreements"][0]["their_rating"] == 2
    picks = [item["title"] for item in data["their_picks"]]
    assert picks[:2] == ["Severance", "Hades"] and "Dune" in picks
    assert "review" not in str(data).lower() and "Private thoughts" not in str(data)
    assert db_session.query(models.Movie).count() == before


def test_guess_needs_three_answers_and_never_reads_private_shelves(client, db_session):
    owner = member(db_session, "dana")
    shelf(db_session, owner)
    enable(db_session, owner, show_taste_match=True)
    deck = ids(taste_compare.deck(db_session, owner))
    data = client.post(f"/api/taste-match/u/{owner.id}/guess",
                       json={"answers": [{"id": deck["Interstellar"], "answer": "loved"}]}).json()
    assert data["score"] is None and data["needed_for_score"] == 2
    secret = db_session.query(models.Book).filter_by(title="Secret Diary").one()
    owner.books_private = True
    db_session.commit()
    taste_compare.DECK_CACHE.clear()
    data = client.post(f"/api/taste-match/u/{owner.id}/guess",
                       json={"answers": [{"id": f"books:{secret.id}", "answer": "loved"}]}).json()
    assert data["rated_count"] == 0
    assert all(item["category"] != "books" for item in data["their_picks"])


def test_member_answers_go_into_their_library_and_return_the_full_match(client, db_session):
    owner = member(db_session, "dana")
    shelf(db_session, owner)
    enable(db_session, owner, show_taste_match=True)
    viewer = member(db_session, "sam")
    db_session.add(models.Movie(user_id=viewer.id, title="Interstellar", year=2014, rating=3, watched=True,
                                director="Christopher Nolan", review="mine"))
    db_session.commit()
    # The deck leaves out what the member already tracks.
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(viewer))
    page = client.get("/u/dana/match")
    assert page.headers["cache-control"] == "private, no-store"
    member_deck = ids(taste_compare.deck_for_member(db_session, owner, viewer))
    assert "Interstellar" not in member_deck and "Arrival" in member_deck
    client.cookies.clear()

    deck = ids(taste_compare.deck(db_session, owner))
    response = client.post(f"/api/taste-match/u/{owner.id}/answers", headers=headers_for(viewer), json={"answers": [
        {"id": deck["Interstellar"], "answer": "loved"},   # already tracked: left alone
        {"id": deck["Arrival"], "answer": "loved"},
        {"id": deck["Severance"], "answer": "liked"},
        {"id": deck["Hades"], "answer": "want"},
        {"id": deck["Cats"], "answer": "skip"},
    ]})
    assert response.status_code == 200
    data = response.json()
    assert [row["title"] for row in data["added"]] == ["Arrival", "Severance", "Hades"]
    assert data["existing"] == ["Interstellar"]
    mine = db_session.query(models.Movie).filter_by(user_id=viewer.id, title="Interstellar").one()
    assert mine.rating == 3 and mine.review == "mine"
    arrival = db_session.query(models.Movie).filter_by(user_id=viewer.id, title="Arrival").one()
    assert arrival.rating == 9 and arrival.watched is True and arrival.review is None
    hades = db_session.query(models.VideoGame).filter_by(user_id=viewer.id, title="Hades").one()
    assert hades.rating is None and hades.played is False
    match = data["match"]
    assert match["owner"] == {"id": owner.id, "username": "dana"} and "friend" not in match
    assert match["rated_count"] == 3 and match["score"] is not None

    library = client.get(f"/api/taste-match/u/{owner.id}", headers=headers_for(viewer)).json()
    assert library["score"] == match["score"]
    # Your own link isn't something to compare with.
    assert client.get(f"/api/taste-match/u/{owner.id}", headers=headers_for(owner)).status_code == 400
    assert client.post(f"/api/taste-match/u/{owner.id}/answers", headers=headers_for(owner),
                       json={"answers": []}).status_code == 400
    assert client.post(f"/api/taste-match/u/{owner.id}/answers", json={"answers": []}).status_code == 401


def test_owner_sees_their_link_and_a_warning_when_the_deck_is_thin(client, db_session):
    owner = member(db_session, "dana")
    enable(db_session, owner, show_taste_match=True)
    db_session.add(models.Movie(user_id=owner.id, title="Arrival", year=2016, rating=9, watched=True))
    db_session.commit()
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(owner))
    page = client.get("/u/dana/match").text
    client.cookies.clear()
    assert "Your compare link" in page and 'value="https://omnitrackr.xyz/u/dana/match"' in page
    assert "needs at least 5 rated titles" in page
    guest = client.get("/u/dana/match").text
    assert "Not ready yet" in guest and 'id="tasteCompare"' not in guest


def test_settings_api_and_card(client, db_session):
    owner = member(db_session, "dana")
    shelf(db_session, owner)
    settings = client.get("/api/profile/settings", headers=headers_for(owner)).json()
    assert settings["show_taste_match"] is False and settings["match_url"] == "/u/dana/match"
    saved = client.put("/api/profile/settings", headers=headers_for(owner),
                       json={"enabled": True, "show_taste_match": True}).json()
    assert saved["show_taste_match"] is True
    card = client.get("/u/dana/match/card.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png"
    assert card.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert client.get(f"/u/id/{owner.id}/match").status_code in (200, 301)


def test_middleware_lets_match_paths_through():
    assert PUBLIC_PROFILE_PATH.match("/u/admin_fan/match")
    assert PUBLIC_PROFILE_PATH.match("/u/admin_fan/match/card.png")
    assert PUBLIC_PROFILE_PATH.match("/u/id/12/match")
    assert not PUBLIC_PROFILE_PATH.match("/u/admin_fan/match/wp-admin")
