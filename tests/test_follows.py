"""Following public profiles without being friends: permissions, privacy, removal, caps, notices and email."""
from datetime import datetime, timedelta

import pytest

from app import auth, digest, follows, models, web_push
from app.auth import AUTH_COOKIE_NAME
from app.routers import collections as collections_router

LONG_REVIEW = (
    "Interstellar works because the science never crowds out the family story at its center. The docking "
    "sequence is one of the most tense scenes I have seen, and the score keeps building pressure without "
    "feeling cheap. Some dialogue is clumsy, yet the time-dilation planet hit me hard on a rewatch and the final "
    "act ties the father and daughter threads together better than I remembered."
)
BOOK_REVIEW = (
    "Dune rewards patience. The first hundred pages bury you in houses, spice and politics, and then the desert "
    "takes over and everything you were asked to remember starts paying off. Paul is colder than I expected, which "
    "makes the ending land harder, and the appendices are worth reading for the ecology alone. I finished it in a week."
)
INTRO = (
    "These are the titles I return to when I need a little room to think. Each one rewards attention in a "
    "different way, but together they remind me that a memorable experience can be quiet, curious, and kind. "
    "I keep them close because they make a strong case for taking art at its own pace instead of treating every "
    "watch, read, or play session as something to optimize. They are companions for a reflective weekend."
)


def member(db, name, **extra):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, created_at=datetime(2025, 3, 4), **extra)
    db.add(user)
    db.flush()
    return user


def public(db, user, **fields):
    db.add(models.PublicProfile(user_id=user.id, enabled=True, **fields))
    db.commit()


def headers(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}


def writer(db, name="critic", **extra):
    user = member(db, name, **extra)
    db.add_all([
        models.Movie(user_id=user.id, title="Interstellar", director="Christopher Nolan", year=2014, rating=10,
                     watched=True, review=LONG_REVIEW, review_public=True),
        models.Movie(user_id=user.id, title="Secret Film", director="Someone", year=2020, rating=4, watched=True,
                     review="My private thoughts about this film are not for anyone else to read, not even friends.",
                     review_public=False),
        models.Book(user_id=user.id, title="Dune", author="Frank Herbert", year=1965, rating=9, read=True,
                    review=BOOK_REVIEW, review_public=True),
        models.Book(user_id=user.id, title="Unrated Add", author="Nobody", year=2021, read=False),
    ])
    db.commit()
    return user


@pytest.fixture
def pair(db_session):
    target = writer(db_session)
    public(db_session, target)
    fan = member(db_session, "fan")
    db_session.commit()
    return target, fan


def follow(client, fan, target):
    return client.post(f"/api/follows/{target.id}", headers=headers(fan))


def feed_titles(client, fan):
    response = client.get("/api/follows/feed", headers=headers(fan))
    assert response.status_code == 200
    return [item["title"] for item in response.json()["items"]]


# ---------------------------------------------------------------- who can be followed

def test_only_public_profiles_can_be_followed(client, db_session):
    target = writer(db_session, "hidden")
    fan = member(db_session, "fan")
    db_session.commit()
    assert follow(client, fan, target).status_code == 404
    db_session.add(models.PublicProfile(user_id=target.id, enabled=False))
    db_session.commit()
    assert follow(client, fan, target).status_code == 404
    assert client.post(f"/api/follows/{target.id}").status_code == 401


def test_follow_creates_one_row_and_one_notice(client, db_session, pair):
    target, fan = pair
    first = follow(client, fan, target)
    assert first.status_code == 200 and first.json()["created"] is True and first.json()["followers"] == 1
    again = follow(client, fan, target)
    assert again.json()["created"] is False
    assert db_session.query(models.MemberFollow).count() == 1
    notices = db_session.query(models.Notification).filter_by(user_id=target.id, type="new_follower").all()
    assert len(notices) == 1 and notices[0].link == "/#followers" and "fan" in notices[0].message
    # Unfollowing and following again within a week doesn't ring the bell twice.
    assert client.delete(f"/api/follows/{target.id}", headers=headers(fan)).json()["removed"] is True
    follow(client, fan, target)
    assert db_session.query(models.Notification).filter_by(user_id=target.id, type="new_follower").count() == 1


def test_you_cannot_follow_yourself(client, db_session, pair):
    target, _fan = pair
    assert follow(client, target, target).status_code == 422


def test_turning_followers_off_removes_them_and_blocks_new_ones(client, db_session, pair):
    target, fan = pair
    follow(client, fan, target)
    saved = client.put("/api/follows/settings", json={"allow_followers": False}, headers=headers(target)).json()
    assert saved["allow_followers"] is False and saved["followers"] == []
    assert db_session.query(models.MemberFollow).count() == 0
    blocked = follow(client, fan, target)
    assert blocked.status_code == 403 and "isn't taking new followers" in blocked.json()["detail"]


def test_removed_followers_cannot_follow_again_until_allowed(client, db_session, pair):
    target, fan = pair
    follow(client, fan, target)
    settings = client.get("/api/follows/settings", headers=headers(target)).json()
    assert [person["username"] for person in settings["followers"]] == ["fan"]
    after = client.delete(f"/api/follows/followers/{fan.id}", headers=headers(target)).json()
    assert after["followers"] == [] and [person["username"] for person in after["removed"]] == ["fan"]
    # Same answer as followers being off: the removed member isn't told they were removed.
    assert follow(client, fan, target).status_code == 403
    client.delete(f"/api/follows/removed/{fan.id}", headers=headers(target))
    assert follow(client, fan, target).status_code == 200


def test_follow_caps(client, db_session, pair, monkeypatch):
    target, fan = pair
    other = writer(db_session, "second")
    public(db_session, other)
    monkeypatch.setattr(follows, "MAX_FOLLOWING", 1)
    assert follow(client, fan, target).status_code == 200
    assert follow(client, fan, other).status_code == 422
    monkeypatch.setattr(follows, "MAX_FOLLOWING", 500)
    monkeypatch.setattr(follows, "DAILY_FOLLOWS", 1)
    assert follow(client, fan, other).status_code == 429


# ---------------------------------------------------------------- what a follower sees

def test_feed_shows_only_what_the_profile_shows_everyone(client, db_session, pair):
    target, fan = pair
    follow(client, fan, target)
    titles = feed_titles(client, fan)
    assert set(titles) == {"Interstellar", "Dune"}
    body = client.get("/api/follows/feed", headers=headers(fan)).text
    assert "Secret Film" not in body and "Unrated Add" not in body and "critic@example.com" not in body


def test_private_category_and_hidden_reviews_drop_out(client, db_session, pair):
    target, fan = pair
    follow(client, fan, target)
    target.movies_private = True
    db_session.commit()
    assert feed_titles(client, fan) == ["Dune"]
    db_session.query(models.PublicProfile).filter_by(user_id=target.id).update({"show_reviews": False})
    db_session.commit()
    assert feed_titles(client, fan) == []


def test_friends_only_activity_never_reaches_followers(client, db_session, pair):
    target, fan = pair
    follow(client, fan, target)
    # A finish the friends feed would show, and a journal note: neither is on the public profile.
    book = db_session.query(models.Book).filter_by(user_id=target.id, title="Unrated Add").one()
    book.read = True
    db_session.add(models.FriendFeedEvent(user_id=target.id, category="books", item_id=book.id, kind="finished"))
    db_session.add(models.ActivityEntry(user_id=target.id, category="books", item_id=book.id, title=book.title,
                                        action="completed", note="Private journal note", occurred_at=datetime.utcnow()))
    db_session.commit()
    body = client.get("/api/follows/feed", headers=headers(fan)).text
    assert "Unrated Add" not in body and "Private journal note" not in body


def test_diary_entries_need_the_diary_switch_and_keep_notes_private(client, db_session, pair):
    target, fan = pair
    follow(client, fan, target)
    book = db_session.query(models.Book).filter_by(user_id=target.id, title="Unrated Add").one()
    db_session.add(models.ActivityEntry(user_id=target.id, category="books", item_id=book.id, title=book.title,
                                        action="completed", note="Private journal note", occurred_at=datetime.utcnow()))
    db_session.commit()
    assert "Unrated Add" not in feed_titles(client, fan)
    db_session.query(models.PublicProfile).filter_by(user_id=target.id).update({"show_diary": True})
    db_session.commit()
    items = client.get("/api/follows/feed", headers=headers(fan)).json()["items"]
    diary = [item for item in items if item["kind"] == "diary"]
    assert [item["title"] for item in diary] == ["Unrated Add"]
    assert "Private journal note" not in str(items)


def test_published_collections_reach_followers(client, db_session, pair):
    target, fan = pair
    collection = models.Collection(user_id=target.id, name="Quiet evenings", description=INTRO, is_public=True,
                                   published_at=datetime.utcnow())
    db_session.add(collection)
    db_session.flush()
    for position, title in enumerate(["Alpha", "Beta", "Gamma"]):
        movie = models.Movie(user_id=target.id, title=title, director="Someone", year=2000 + position, watched=True)
        db_session.add(movie)
        db_session.flush()
        db_session.add(models.CollectionItem(collection_id=collection.id, category="movies", item_id=movie.id,
                                             position=position))
    db_session.flush()
    db_session.refresh(collection)
    collections_router._apply_automated_readiness(collection, db_session)
    db_session.commit()
    follow(client, fan, target)
    kinds = {item["title"]: item["kind"] for item in client.get("/api/follows/feed", headers=headers(fan)).json()["items"]}
    assert kinds.get("Quiet evenings") == "collection"
    page = client.get(f"/collections/public/{collection.id}").text
    assert f'href="/u/critic#follow">Follow critic</a>' in page


def test_old_items_and_switched_off_profiles_leave_the_feed(client, db_session, pair):
    target, fan = pair
    follow(client, fan, target)
    assert follows.feed(db_session, fan.id, now=datetime.utcnow() + timedelta(days=90)) == []
    db_session.query(models.PublicProfile).filter_by(user_id=target.id).update({"enabled": False})
    db_session.commit()
    assert feed_titles(client, fan) == []
    assert client.get("/api/follows/settings", headers=headers(fan)).json()["following"] == []


def test_deactivated_accounts_drop_out_and_come_back(client, db_session, pair):
    target, fan = pair
    follow(client, fan, target)
    assert follows.counts(db_session, target.id) == {"followers": 1, "following": 0}
    fan.is_active = False
    db_session.commit()
    assert follows.counts(db_session, target.id)["followers"] == 0
    fan.is_active = True
    target.is_active = False
    db_session.commit()
    assert follows.counts(db_session, fan.id)["following"] == 0
    assert follows.feed(db_session, fan.id) == []
    target.is_active = True
    db_session.commit()
    assert follows.counts(db_session, fan.id)["following"] == 1


# ---------------------------------------------------------------- pages

def test_profile_page_follow_button(client, db_session, pair):
    target, fan = pair
    guest = client.get("/u/critic").text
    assert 'id="follow"' in guest and 'href="/#signup" data-profile-join' in guest
    client.cookies.set(AUTH_COOKIE_NAME, auth.create_user_access_token(fan))
    page = client.get("/u/critic").text
    assert f'data-follow="{target.id}"' in page and 'aria-pressed="false"' in page
    follow(client, fan, target)
    page = client.get("/u/critic").text
    assert 'aria-pressed="true"' in page and ">Following</button>" in page
    assert "<dt>Followers</dt><dd><span data-follower-count>1</span>" in page
    client.cookies.set(AUTH_COOKIE_NAME, auth.create_user_access_token(target))
    assert "data-follow=" not in client.get("/u/critic").text
    client.cookies.clear()


def test_profile_hides_the_button_and_counts_when_the_member_says_so(client, db_session, pair):
    target, fan = pair
    db_session.query(models.PublicProfile).filter_by(user_id=target.id).update({"show_stats": False})
    db_session.add(models.FollowSetting(user_id=target.id, allow_followers=False))
    db_session.commit()
    page = client.get("/u/critic").text
    assert 'id="follow"' not in page and "<dt>Followers</dt>" not in page


def test_review_page_links_to_follow(client, db_session, pair):
    target, _fan = pair
    movie = db_session.query(models.Movie).filter_by(user_id=target.id, title="Interstellar").one()
    page = client.get(f"/reviews/{movie.id}?category=movie")
    assert page.status_code == 200
    assert 'class="review-follow-link" href="/u/critic#follow">Follow critic</a>' in page.text
    db_session.add(models.FollowSetting(user_id=target.id, allow_followers=False))
    db_session.commit()
    assert "review-follow-link" not in client.get(f"/reviews/{movie.id}?category=movie").text


def test_suggestions_come_from_saved_collections(client, db_session, pair):
    target, fan = pair
    source = models.Collection(user_id=target.id, name="Source", description=INTRO, is_public=True)
    copy = models.Collection(user_id=fan.id, name="My copy", description="", is_public=False)
    db_session.add_all([source, copy])
    db_session.flush()
    db_session.add(models.CollectionSaveReceipt(user_id=fan.id, source_collection_id=source.id, selection_key="all",
                                                collection_id=copy.id))
    db_session.commit()
    people = client.get("/api/follows/suggestions", headers=headers(fan)).json()["people"]
    assert [(p["username"], p["reason"]) for p in people] == [("critic", "You saved one of their collections")]
    follow(client, fan, target)
    assert client.get("/api/follows/suggestions", headers=headers(fan)).json()["people"] == []


# ---------------------------------------------------------------- notices and email

def test_new_follower_push_is_off_by_default():
    assert web_push.topic_of("new_follower") == "followers"
    assert not web_push.wants(None, "new_follower")


def test_weekly_email_section(client, db_session, pair):
    target, fan = pair
    follow(client, fan, target)
    items = digest.following_line(db_session, fan, datetime.utcnow())
    assert {item["title"] for item in items} == {"Interstellar", "Dune"}
    html, text = digest._following_section(items, "https://omnitrackr.xyz")
    assert "From people you follow" in html and "critic reviewed Interstellar (10/10)" in "\n".join(text)
    assert "Secret Film" not in html
    # The section never sends an email by itself.
    quiet = {"matches": [], "popular": []}
    assert digest.build_digest("fan", quiet, "https://x/unsub", following=items) is None
    client.put("/api/follows/settings", json={"email_following": False}, headers=headers(fan))
    assert digest.following_line(db_session, fan, datetime.utcnow()) == []
