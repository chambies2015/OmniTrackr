"""Recommend to a friend: send a title with a note, the friend adds it in one tap, or share a join link."""
import json

from app import auth, models
from app.crud.friends import create_friendship
from tests.test_title_pages import add_movie, member


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


def _as(client, user):
    client.headers = {}
    client.cookies.clear()
    token = auth.create_user_access_token(user)
    client.headers = {"Authorization": f"Bearer {token}"}
    client.cookies.set(auth.AUTH_COOKIE_NAME, token)


def _sign_out(client):
    client.headers = {}
    client.cookies.clear()


def _friend(db, me, name="dana"):
    friend = member(db, name)
    create_friendship(db, min(me.id, friend.id), max(me.id, friend.id))
    db.commit()
    return friend


def _movie(db, me, **extra):
    movie = add_movie(db, me, poster_url="https://img.example.com/interstellar.jpg", rating=9.5,
                      review="My private thoughts", **extra)
    db.commit()
    return movie


def test_send_to_a_friend_and_add_to_library_and_next_up(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    movie = _movie(db_session, me)

    sent = authenticated_client.post("/api/friend-recs", json={
        "category": "movies", "item_id": movie.id, "friend_ids": [dana.id], "note": "  The docking   scene!  "})
    assert sent.status_code == 200, sent.text
    assert sent.json()["sent"] == 1 and sent.json()["friends"] == ["dana"]
    note = db_session.query(models.Notification).filter_by(user_id=dana.id, type="friend_recommendation").one()
    assert note.link == "/#friend-recs" and "testuser thinks you'd love Interstellar." in note.message
    assert "The docking scene!" in note.message

    # Sending again refreshes the note without a second ping.
    again = authenticated_client.post("/api/friend-recs", json={
        "category": "movies", "item_id": movie.id, "friend_ids": [dana.id], "note": "Bring tissues"})
    assert again.json() == {"sent": 0, "already": 1, "friends": ["dana"], "title": "Interstellar"}
    assert db_session.query(models.Notification).filter_by(user_id=dana.id, type="friend_recommendation").count() == 1

    _as(authenticated_client, dana)
    inbox = authenticated_client.get("/api/friend-recs/inbox")
    assert inbox.status_code == 200 and inbox.headers["cache-control"] == "private, no-store"
    data = inbox.json()
    assert data["count"] == 1
    item = data["items"][0]
    assert item["sender"] == "testuser" and item["title"] == "Interstellar" and item["note"] == "Bring tissues"
    assert item["year"] == 2014 and item["creator"] == "Christopher Nolan" and item["in_library"] is False
    assert item["image"] == "https://img.example.com/interstellar.jpg"
    # The sender's rating and review never travel with the recommendation.
    # created_at is left out of the check: its fractional seconds can contain "9.5".
    shared = json.dumps([{k: v for k, v in it.items() if k != "created_at"} for it in data["items"]])
    assert "My private thoughts" not in shared and "9.5" not in shared
    assert not {"rating", "review"} & set(item)

    added = authenticated_client.post(f"/api/friend-recs/{item['id']}/add", json={"next_up": True})
    assert added.status_code == 200, added.text
    assert added.json()["created"] is True and added.json()["queued"] is True and added.json()["status"] == "queued"
    copy = db_session.query(models.Movie).filter_by(user_id=dana.id).one()
    assert copy.title == "Interstellar" and copy.director == "Christopher Nolan" and copy.year == 2014
    assert copy.rating is None and copy.review is None and copy.watched is False and copy.review_public is False
    assert db_session.query(models.NextUpItem).filter_by(user_id=dana.id, item_id=copy.id).count() == 1
    thanks = db_session.query(models.Notification).filter_by(user_id=me.id, type="friend_recommendation_added").one()
    assert thanks.message == "dana added Interstellar to their Next Up from your recommendation."

    assert authenticated_client.get("/api/friend-recs/inbox").json() == {"count": 0, "items": []}
    assert authenticated_client.post(f"/api/friend-recs/{item['id']}/add", json={}).status_code == 409


def test_add_keeps_an_existing_entry_and_dismiss_is_silent(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    movie = _movie(db_session, me)
    mine = add_movie(db_session, dana, title="interstellar ", watched=True)
    db_session.commit()
    authenticated_client.post("/api/friend-recs", json={"category": "movies", "item_id": movie.id, "friend_ids": [dana.id]})
    _as(authenticated_client, dana)
    item = authenticated_client.get("/api/friend-recs/inbox").json()["items"][0]
    assert item["in_library"] is True
    added = authenticated_client.post(f"/api/friend-recs/{item['id']}/add", json={"next_up": True}).json()
    assert added["created"] is False and added["item_id"] == mine.id and added["queued"] is False
    assert db_session.query(models.Movie).filter_by(user_id=dana.id).count() == 1

    _as(authenticated_client, me)
    other = add_movie(db_session, me, title="Arrival", year=2016)
    db_session.commit()
    authenticated_client.post("/api/friend-recs", json={"category": "movies", "item_id": other.id, "friend_ids": [dana.id]})
    _as(authenticated_client, dana)
    rec = authenticated_client.get("/api/friend-recs/inbox").json()["items"][0]
    before = db_session.query(models.Notification).filter_by(user_id=me.id).count()
    assert authenticated_client.post(f"/api/friend-recs/{rec['id']}/dismiss").json() == {"status": "dismissed"}
    assert db_session.query(models.Notification).filter_by(user_id=me.id).count() == before
    assert authenticated_client.get("/api/friend-recs/inbox").json()["count"] == 0


def test_only_friends_and_only_your_own_titles(authenticated_client, db_session):
    me = _me(db_session)
    stranger = member(db_session, "stranger")
    dana = _friend(db_session, me)
    movie = _movie(db_session, me)
    theirs = add_movie(db_session, dana, title="Heat", year=1995)
    db_session.commit()
    refused = authenticated_client.post("/api/friend-recs", json={
        "category": "movies", "item_id": movie.id, "friend_ids": [stranger.id]})
    assert refused.status_code == 403
    assert authenticated_client.post("/api/friend-recs", json={
        "category": "movies", "item_id": theirs.id, "friend_ids": [dana.id]}).status_code == 404
    assert authenticated_client.post("/api/friend-recs", json={
        "category": "movies", "item_id": movie.id, "friend_ids": [dana.id], "note": "x" * 281}).status_code == 422
    assert authenticated_client.post("/api/friend-recs", json={"friend_ids": [dana.id]}).status_code == 400
    # Someone else's recommendation can't be answered.
    authenticated_client.post("/api/friend-recs", json={"category": "movies", "item_id": movie.id, "friend_ids": [dana.id]})
    rec = db_session.query(models.FriendRecommendation).filter_by(recipient_id=dana.id).one()
    _as(authenticated_client, stranger)
    assert authenticated_client.post(f"/api/friend-recs/{rec.id}/add", json={}).status_code == 404
    assert authenticated_client.post(f"/api/friend-recs/{rec.id}/dismiss").status_code == 404


def test_recommend_from_a_title_page(authenticated_client, db_session):
    me = _me(db_session)
    dana = _friend(db_session, me)
    someone = member(db_session, "someone")
    add_movie(db_session, someone, poster_url="https://img.example.com/i.jpg")
    db_session.commit()
    sent = authenticated_client.post("/api/friend-recs", json={
        "kind": "movie", "slug": "interstellar-2014", "friend_ids": [dana.id]})
    assert sent.status_code == 200 and sent.json()["sent"] == 1
    rec = db_session.query(models.FriendRecommendation).filter_by(recipient_id=dana.id).one()
    assert rec.title_path == "/titles/movie/interstellar-2014" and rec.category == "movies"
    page = authenticated_client.get("/titles/movie/interstellar-2014")
    assert "data-friend-rec-open" in page.text


def test_share_link_for_someone_not_on_omnitrackr(authenticated_client, db_session):
    me = _me(db_session)
    movie = _movie(db_session, me)
    made = authenticated_client.post("/api/friend-recs/link", json={
        "category": "movies", "item_id": movie.id, "note": "Watch it on the biggest screen you can"})
    assert made.status_code == 200, made.text
    url = made.json()["url"]
    assert url.startswith("https://omnitrackr.xyz/r/")
    assert made.json()["text"] == "I think you'd love Interstellar. Watch it on the biggest screen you can"
    token = url.rsplit("/", 1)[1]
    # The same title and note reuse the link.
    assert authenticated_client.post("/api/friend-recs/link", json={
        "category": "movies", "item_id": movie.id, "note": "Watch it on the biggest screen you can"}).json()["url"] == url
    invite = db_session.query(models.FriendInvite).filter_by(user_id=me.id).one()

    _sign_out(authenticated_client)
    page = authenticated_client.get(f"/r/{token}")
    assert page.status_code == 200
    assert "testuser thinks you&#x27;d love" in page.text and "Watch it on the biggest screen you can" in page.text
    assert f'href="/?invite={invite.token}#signup"' in page.text
    assert "My private thoughts" not in page.text
    assert page.headers["x-robots-tag"] == "noindex, nofollow" and page.headers["cache-control"] == "private, no-store"
    assert authenticated_client.get("/r/not-a-real-token-at-all").status_code == 404

    newcomer = member(db_session, "newcomer")
    db_session.commit()
    _as(authenticated_client, newcomer)
    signed_in_page = authenticated_client.get(f"/r/{token}")
    assert "data-friend-rec-claim" in signed_in_page.text and f'href="/join/{invite.token}"' in signed_in_page.text
    claimed = authenticated_client.post(f"/api/friend-recs/claim/{token}")
    assert claimed.status_code == 200 and claimed.json()["claimed"] is True
    assert authenticated_client.post(f"/api/friend-recs/claim/{token}").json()["claimed"] is False
    inbox = authenticated_client.get("/api/friend-recs/inbox").json()
    assert inbox["count"] == 1 and inbox["items"][0]["sender"] == "testuser"
    added = authenticated_client.post(f"/api/friend-recs/{inbox['items'][0]['id']}/add", json={}).json()
    assert added["status"] == "added"
    # Not friends yet, so the sender isn't told who saved it.
    assert db_session.query(models.Notification).filter_by(user_id=me.id, type="friend_recommendation_added").count() == 0

    _as(authenticated_client, me)
    assert authenticated_client.post(f"/api/friend-recs/claim/{token}").json()["own"] is True


def test_expired_link_and_deactivated_sender(authenticated_client, db_session):
    from datetime import datetime, timedelta
    me = _me(db_session)
    dana = _friend(db_session, me)
    movie = _movie(db_session, me)
    token = authenticated_client.post("/api/friend-recs/link", json={"category": "movies", "item_id": movie.id}).json()["url"].rsplit("/", 1)[1]
    authenticated_client.post("/api/friend-recs", json={"category": "movies", "item_id": movie.id, "friend_ids": [dana.id]})
    link = db_session.query(models.FriendRecommendation).filter_by(token=token).one()
    link.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    _sign_out(authenticated_client)
    assert authenticated_client.get(f"/r/{token}").status_code == 404
    me.is_active = False
    db_session.commit()
    _as(authenticated_client, dana)
    assert authenticated_client.get("/api/friend-recs/inbox").json()["count"] == 0
