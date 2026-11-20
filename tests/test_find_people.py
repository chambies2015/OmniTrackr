"""Find people: who gets suggested, what a card may name, follow-backs, Not for me and the switches."""
from datetime import datetime, timedelta

from app import auth, models, people_to_follow

LONG_REVIEW = (
    "Arrival works because the language puzzle never crowds out the grief at its centre. The first contact scenes "
    "are patient and strange, the score hums under everything, and the final turn reframes the whole film without "
    "feeling like a trick. I cried on the second watch, which I did not expect from a film about linguistics."
)
SHARED = (("Interstellar", 2014), ("Dune", 2021), ("Arrival", 2016), ("Her", 2013), ("Prisoners", 2013))


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


def movies(db, user, titles, rating=9):
    for title, year in titles:
        db.add(models.Movie(user_id=user.id, title=title, year=year, rating=rating, watched=True,
                            poster_url=f"https://img.example/{title.replace(' ', '')}.jpg"))
    db.commit()


def viewer(db, name="me"):
    user = member(db, name)
    movies(db, user, SHARED)
    return user


def suggest(client, user):
    response = client.get("/api/people/suggestions", headers=headers(user))
    assert response.status_code == 200
    return response.json()


def people(data, group=None):
    return [person["username"] for g in data["groups"] if group in (None, g["key"]) for person in g["people"]]


def card_for(data, username):
    for group in data["groups"]:
        for person in group["people"]:
            if person["username"] == username:
                return person
    return None


# ---------------------------------------------------------------- similar taste

def test_similar_taste_names_only_titles_the_profile_shows(client, db_session):
    me = viewer(db_session)
    twin = member(db_session, "twin")
    # Favorites (8+) are on the profile; the 6s are in the library but not shown anywhere.
    movies(db_session, twin, SHARED[:2], rating=9)
    movies(db_session, twin, SHARED[2:], rating=6)
    public(db_session, twin, bio="Slow sci-fi and long books.")
    data = suggest(client, me)
    card = card_for(data, "twin")
    assert card and card["source"] == "taste"
    assert card["reason"] == "You both loved Dune and Interstellar" or card["reason"] == "You both loved Interstellar and Dune"
    named = {title["title"] for title in card["titles"]}
    assert named <= {"Interstellar", "Dune"}
    assert "Arrival" not in card["reason"] and "Her" not in card["reason"]
    assert card["bio"] == "Slow sci-fi and long books."
    assert card["profile_url"] == "/u/twin" and "compare_url" not in card
    # Nothing on the card counts their library without the compare link switched on.
    assert "more in common" not in card["reason"]


def test_switching_a_profile_section_off_takes_effect_at_once(client, db_session):
    me = viewer(db_session)
    twin = member(db_session, "twin")
    movies(db_session, twin, SHARED, rating=9)
    public(db_session, twin, show_reviews=False)
    assert "twin" in people(suggest(client, me))
    profile = db_session.query(models.PublicProfile).filter_by(user_id=twin.id).one()
    profile.show_favorites = False
    db_session.commit()
    assert "twin" not in people(suggest(client, me))
    profile.show_favorites = True
    twin.movies_private = True
    db_session.commit()
    assert "twin" not in people(suggest(client, me))


def test_hidden_overlap_alone_never_suggests_anyone(client, db_session):
    me = viewer(db_session)
    quiet = member(db_session, "quiet")
    movies(db_session, quiet, SHARED, rating=9)
    public(db_session, quiet, show_favorites=False, show_reviews=False)
    assert "quiet" not in people(suggest(client, me))


def test_compare_link_on_lets_a_card_name_any_shared_title_and_count(client, db_session):
    me = viewer(db_session)
    open_book = member(db_session, "openbook")
    movies(db_session, open_book, SHARED, rating=7)
    public(db_session, open_book, show_favorites=False, show_reviews=False, show_taste_match=True)
    card = card_for(suggest(client, me), "openbook")
    assert card and card["compare_url"] == "/u/openbook/match"
    assert card["reason"].startswith("You both have ") and card["reason"].endswith("3 more in common")


def test_private_categories_never_count_or_get_named(client, db_session):
    me = viewer(db_session)
    shy = member(db_session, "shy", movies_private=True)
    movies(db_session, shy, SHARED, rating=10)
    public(db_session, shy, show_taste_match=True)
    assert "shy" not in people(suggest(client, me))


def test_too_little_overlap_or_library_is_not_a_match(client, db_session):
    me = viewer(db_session)
    near = member(db_session, "near")
    movies(db_session, near, SHARED[:2], rating=9)
    public(db_session, near, show_taste_match=True)
    assert "near" not in people(suggest(client, me), "taste")
    newbie = member(db_session, "newbie")
    movies(db_session, newbie, SHARED[:2])
    db_session.commit()
    data = suggest(client, newbie)
    assert data["you"]["library"] == 2 and data["you"]["needs_titles"] == 3
    assert people(data, "taste") == []


# ---------------------------------------------------------------- who can be suggested

def test_only_open_profiles_are_suggested(client, db_session):
    me = viewer(db_session)
    for name in ("private", "closed", "unsuggested", "omnitrackr_editors", "gone"):
        other = member(db_session, name)
        movies(db_session, other, SHARED, rating=9)
    db_session.commit()
    users = {u.username: u for u in db_session.query(models.User)}
    db_session.add(models.PublicProfile(user_id=users["private"].id, enabled=False))
    public(db_session, users["closed"])
    db_session.add(models.FollowSetting(user_id=users["closed"].id, allow_followers=False))
    public(db_session, users["unsuggested"])
    db_session.add(models.FollowSetting(user_id=users["unsuggested"].id, suggest_me=False))
    public(db_session, users["omnitrackr_editors"])
    public(db_session, users["gone"])
    users["gone"].is_active = False
    db_session.commit()
    assert people(suggest(client, me)) == []


def test_followed_friends_and_removed_people_drop_out(client, db_session):
    me = viewer(db_session)
    names = ("followed", "friend", "removedme", "iremoved")
    for name in names:
        other = member(db_session, name)
        movies(db_session, other, SHARED, rating=9)
        public(db_session, other)
    users = {u.username: u for u in db_session.query(models.User)}
    assert set(people(suggest(client, me))) == set(names)
    db_session.add_all([
        models.MemberFollow(follower_id=me.id, followed_id=users["followed"].id),
        models.Friendship(user1_id=me.id, user2_id=users["friend"].id),
        models.FollowBar(owner_id=users["removedme"].id, barred_id=me.id),
        models.FollowBar(owner_id=me.id, barred_id=users["iremoved"].id),
    ])
    db_session.commit()
    assert people(suggest(client, me)) == []


def test_not_for_me_hides_a_card_until_undone(client, db_session):
    me = viewer(db_session)
    other = member(db_session, "maybe")
    movies(db_session, other, SHARED, rating=9)
    public(db_session, other)
    assert client.post(f"/api/people/dismiss/{other.id}", headers=headers(me)).json()["created"] is True
    assert client.post(f"/api/people/dismiss/{other.id}", headers=headers(me)).json()["created"] is False
    assert "maybe" not in people(suggest(client, me))
    # The other member is never told.
    assert db_session.query(models.Notification).filter_by(user_id=other.id).count() == 0
    assert client.delete(f"/api/people/dismiss/{other.id}", headers=headers(me)).json()["removed"] is True
    assert "maybe" in people(suggest(client, me))
    assert client.post(f"/api/people/dismiss/{me.id}", headers=headers(me)).status_code == 422
    assert client.post("/api/people/dismiss/999999", headers=headers(me)).json()["created"] is False


def test_endpoints_need_a_signed_in_member(client, db_session):
    assert client.get("/api/people/suggestions").status_code == 401
    assert client.get("/api/people/rail").status_code == 401
    assert client.post("/api/people/dismiss/1").status_code == 401
    me = viewer(db_session)
    assert client.post("/api/people/event", json={"name": "profile_prompt"}, headers=headers(me)).status_code == 200
    assert client.post("/api/people/event", json={"name": "friend_back"}, headers=headers(me)).status_code == 200
    assert client.post("/api/people/event", json={"name": "page_shown"}, headers=headers(me)).status_code == 422
    response = client.get("/api/people/suggestions", headers=headers(me))
    assert response.headers["cache-control"] == "private, no-store"


# ---------------------------------------------------------------- follow back

def test_followers_you_dont_follow_get_a_follow_back(client, db_session):
    me = viewer(db_session)
    public(db_session, me)
    fan = member(db_session, "fan")
    movies(db_session, fan, (("Up", 2009),))
    public(db_session, fan)
    lurker = member(db_session, "lurker")
    db_session.commit()
    for follower in (fan, lurker):
        assert client.post(f"/api/follows/{me.id}", headers=headers(follower)).status_code == 200
    data = suggest(client, me)
    back = {person["username"]: person for person in data["follow_back"]}
    assert set(back) == {"fan", "lurker"}
    assert back["fan"]["can_follow"] is True and back["fan"]["profile_url"] == "/u/fan"
    assert back["fan"]["reason"] == "Followed you today"
    # No public profile: no profile link, offer a friend request instead.
    assert back["lurker"]["can_follow"] is False and back["lurker"]["profile_url"] is None
    assert back["lurker"]["can_friend"] is True
    db_session.add(models.FriendRequest(sender_id=me.id, receiver_id=lurker.id, status="pending"))
    db_session.commit()
    back = {person["username"]: person for person in suggest(client, me)["follow_back"]}
    assert back["lurker"]["can_friend"] is False and back["lurker"]["friend_pending"] is True
    assert client.post(f"/api/follows/{fan.id}?source=back", headers=headers(me)).status_code == 200
    assert [person["username"] for person in suggest(client, me)["follow_back"]] == ["lurker"]


def test_rail_puts_follow_backs_first(client, db_session):
    me = viewer(db_session)
    public(db_session, me)
    fan = member(db_session, "fan")
    public(db_session, fan)
    for name in ("alpha", "beta", "gamma"):
        other = member(db_session, name)
        movies(db_session, other, SHARED, rating=9)
        public(db_session, other)
    client.post(f"/api/follows/{me.id}", headers=headers(fan))
    rail = client.get("/api/people/rail", headers=headers(me)).json()
    assert [person["username"] for person in rail["people"]][0] == "fan"
    assert len(rail["people"]) == people_to_follow.RAIL_LIMIT and rail["more"] is True


def test_settings_list_offers_follow_back_and_the_suggest_switch(client, db_session):
    me = viewer(db_session)
    public(db_session, me)
    fan = member(db_session, "fan")
    public(db_session, fan)
    client.post(f"/api/follows/{me.id}", headers=headers(fan))
    settings = client.get("/api/follows/settings", headers=headers(me)).json()
    assert settings["suggest_me"] is True
    assert settings["followers"][0]["can_follow_back"] is True and settings["followers"][0]["followed_back"] is False
    saved = client.put("/api/follows/settings", json={"suggest_me": False}, headers=headers(me)).json()
    assert saved["suggest_me"] is False and saved["allow_followers"] is True
    row = db_session.query(models.FollowSetting).filter_by(user_id=me.id).one()
    db_session.refresh(row)
    assert row.suggest_me is False
    # Opting out hides you from suggestions, not from your own followers.
    movies(db_session, fan, SHARED, rating=9)
    assert "me" not in people(suggest(client, fan))
    assert client.post(f"/api/follows/{fan.id}?source=list", headers=headers(me)).status_code == 200
    settings = client.get("/api/follows/settings", headers=headers(me)).json()
    assert settings["followers"][0]["followed_back"] is True and settings["followers"][0]["can_follow_back"] is False


# ---------------------------------------------------------------- shelf and active

def test_public_reviews_of_your_titles_suggest_the_writer(client, db_session):
    me = viewer(db_session)
    critic = member(db_session, "critic")
    db_session.add(models.Movie(user_id=critic.id, title="Arrival", year=2016, rating=9, watched=True,
                                review=LONG_REVIEW, review_public=True))
    db_session.commit()
    public(db_session, critic)
    card = card_for(suggest(client, me), "critic")
    assert card and card["source"] in ("shelf", "active")
    data = people_to_follow.suggestions(db_session, me)
    shelf = [g for g in data["groups"] if g["key"] == "shelf"]
    assert shelf and shelf[0]["people"][0]["reason"] == "Reviewed Arrival, which is in your library"
    assert shelf[0]["people"][0]["titles"][0]["url"].startswith("/reviews/")


def test_active_profiles_are_read_from_what_the_profile_shows(client, db_session):
    me = viewer(db_session)
    busy = member(db_session, "busy")
    db_session.add(models.Movie(user_id=busy.id, title="Past Lives", year=2023, rating=9, watched=True,
                                review=LONG_REVIEW, review_public=True, added_at=datetime.utcnow() - timedelta(days=2)))
    quiet = member(db_session, "quietfinisher")
    film = models.Movie(user_id=quiet.id, title="Aftersun", year=2022, rating=9, watched=True)
    db_session.add(film)
    db_session.commit()
    db_session.add(models.ActivityEntry(user_id=quiet.id, category="movies", item_id=film.id, title="Aftersun", action="completed",
                                        occurred_at=datetime.utcnow() - timedelta(days=1)))
    public(db_session, busy)
    public(db_session, quiet)  # diary off: the finish is private
    data = suggest(client, me)
    card = card_for(data, "busy")
    assert card and card["reason"] == "A new review this month"
    assert "quietfinisher" not in people(data)


# ---------------------------------------------------------------- counters and stats

def test_follow_sources_and_counters_are_whitelisted():
    assert people_to_follow.count_follow("nope") is False
    assert people_to_follow.count("not_a_counter") is False
    assert set(people_to_follow.CLIENT_COUNTERS) <= set(people_to_follow.COUNTERS)
    for source in people_to_follow.SOURCES:
        assert f"followed_{source}" in people_to_follow.COUNTERS


def test_stats_count_follows_and_mutuals(db_session):
    a, b, c = member(db_session, "a"), member(db_session, "b"), member(db_session, "c")
    db_session.add_all([models.MemberFollow(follower_id=a.id, followed_id=b.id),
                        models.MemberFollow(follower_id=b.id, followed_id=a.id),
                        models.MemberFollow(follower_id=c.id, followed_id=a.id),
                        models.FollowSetting(user_id=c.id, suggest_me=False)])
    db_session.commit()
    stats = people_to_follow.stats(db_session, 30, datetime.utcnow())
    assert stats["follows_now"] == 3 and stats["mutual_pairs"] == 1
    assert stats["members_following"] == 3 and stats["members_followed"] == 2 and stats["suggest_off"] == 1
    assert set(stats["counts"]) == set(people_to_follow.COUNTERS)


def test_page_markup_has_the_view_and_switch():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    for needle in ('data-social-tab="people"', 'id="peoplePanel"', 'id="peopleGroups"', 'id="peopleBackList"',
                   'id="followSuggest"', 'id="followingFindPeople"', '/static/find-people.js?v=', 'find-people.css?v='):
        assert html.count(needle) == 1, needle
