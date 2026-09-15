"""Recommendation Postcards stay scoped, private, and owner-controlled."""
from datetime import datetime, timedelta

from app import auth, crud, models, schemas


def create_postcard(authenticated_client, **overrides):
    payload = {
        "prompt": "What should I try when I want a clever mystery with some warmth?",
        "categories": ["movies", "anime", "books"],
        "expires_in_days": 7,
        "max_responses": 5,
    }
    payload.update(overrides)
    return authenticated_client.post("/recommendations/requests/", json=payload)


def create_second_user(db_session, username="postcardfriend"):
    data = schemas.UserCreate(email=f"{username}@example.com", username=username, password="testpassword123")
    user = crud.create_user(db_session, data, auth.get_password_hash(data.password), f"verify-{username}")
    user.is_verified = True
    db_session.commit()
    db_session.refresh(user)
    return user


class TestRecommendationPostcards:
    def test_dashboard_and_guest_page_are_private_search_surfaces(self, authenticated_client):
        dashboard = authenticated_client.get("/")
        assert dashboard.status_code == 200
        assert 'data-switch-tab="recommendations"' in dashboard.text
        assert 'id="recommendations-tab"' in dashboard.text
        assert "No automatic library changes" in dashboard.text

        postcard = create_postcard(authenticated_client).json()
        guest_page = authenticated_client.get(postcard["share_path"])
        assert guest_page.status_code == 200
        assert "Recommendation Postcard" in guest_page.text
        assert 'name="robots" content="noindex, nofollow"' in guest_page.text
        assert guest_page.headers["x-robots-tag"] == "noindex, nofollow"
        assert guest_page.headers["cache-control"] == "private, no-store"
        assert "/recommend/" not in authenticated_client.get("/sitemap.xml").text

    def test_create_validation_and_public_payload_disclose_only_postcard_fields(self, authenticated_client):
        response = create_postcard(authenticated_client)
        assert response.status_code == 201
        postcard = response.json()
        assert postcard["state"] == "open"
        assert postcard["remaining"] == 5
        assert postcard["share_path"].startswith("/recommend/")
        token = postcard["share_path"].rsplit("/", 1)[-1]

        public = authenticated_client.get(f"/recommendations/public/{token}")
        assert public.status_code == 200
        assert set(public.json()) == {
            "owner_username", "prompt", "categories", "max_responses",
            "response_count", "remaining", "state", "expires_at",
        }
        assert "email" not in public.text
        assert "library" not in public.text
        assert public.headers["x-robots-tag"] == "noindex, nofollow"
        assert public.headers["cache-control"] == "private, no-store"

        assert create_postcard(authenticated_client, prompt="too short").status_code == 422
        assert create_postcard(authenticated_client, categories=["podcasts"]).status_code == 422

    def test_open_postcard_limit_keeps_authenticated_storage_bounded(self, authenticated_client):
        for number in range(5):
            assert create_postcard(
                authenticated_client,
                prompt=f"Which thoughtful mystery should I try for quiet evening number {number}?",
            ).status_code == 201
        blocked = create_postcard(authenticated_client)
        assert blocked.status_code == 409
        first = authenticated_client.get("/recommendations/requests/").json()[-1]
        assert authenticated_client.post(f"/recommendations/requests/{first['id']}/close").status_code == 200
        assert create_postcard(authenticated_client).status_code == 201

    def test_guest_reply_duplicate_honeypot_and_owner_inbox(self, authenticated_client, db_session):
        postcard = create_postcard(authenticated_client).json()
        token = postcard["share_path"].rsplit("/", 1)[-1]
        reply = {
            "guest_name": "Sam",
            "category": "movies",
            "title": "Knives Out",
            "reason": "It is playful, tightly plotted, and never loses its warmth.",
        }
        submitted = authenticated_client.post(f"/recommendations/public/{token}", json=reply)
        assert submitted.status_code == 201
        assert db_session.query(models.RecommendationSubmission).count() == 1
        assert db_session.query(models.Notification).filter_by(type="recommendation_received").count() == 1

        inbox = authenticated_client.get("/recommendations/inbox/").json()
        assert inbox[0]["title"] == "Knives Out"
        assert inbox[0]["reason"] == reply["reason"]
        assert inbox[0]["status"] == "pending"

        duplicate = {**reply, "title": "  KNIVES OUT  "}
        assert authenticated_client.post(f"/recommendations/public/{token}", json=duplicate).status_code == 409
        disallowed = {**reply, "category": "music", "title": "A Warm Album"}
        assert authenticated_client.post(f"/recommendations/public/{token}", json=disallowed).status_code == 400

        trapped = {**reply, "title": "Bot title", "website": "https://spam.invalid"}
        assert authenticated_client.post(f"/recommendations/public/{token}", json=trapped).status_code == 201
        assert db_session.query(models.RecommendationSubmission).count() == 1
        assert db_session.query(models.Notification).filter_by(type="recommendation_received").count() == 1

    def test_closed_expired_and_full_postcards_stop_accepting_replies(self, authenticated_client, db_session):
        first = create_postcard(authenticated_client, max_responses=3).json()
        token = first["share_path"].rsplit("/", 1)[-1]
        closed = authenticated_client.post(f"/recommendations/requests/{first['id']}/close")
        assert closed.status_code == 200
        payload = {"guest_name": "Sam", "category": "movies", "title": "Arrival", "reason": "A humane mystery with a satisfying emotional center."}
        assert authenticated_client.post(f"/recommendations/public/{token}", json=payload).status_code == 409

        second = create_postcard(authenticated_client).json()
        expired = db_session.query(models.RecommendationRequest).filter_by(id=second["id"]).one()
        expired.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db_session.commit()
        expired_token = second["share_path"].rsplit("/", 1)[-1]
        assert authenticated_client.post(f"/recommendations/public/{expired_token}", json=payload).status_code == 410

        third = create_postcard(authenticated_client, max_responses=3).json()
        full = db_session.query(models.RecommendationRequest).filter_by(id=third["id"]).one()
        for number in range(3):
            db_session.add(models.RecommendationSubmission(
                request_id=full.id, guest_name=f"Guest {number}", category="movies",
                title=f"Title {number}", reason="A detailed reason that is certainly long enough.",
            ))
        db_session.commit()
        full_token = third["share_path"].rsplit("/", 1)[-1]
        assert authenticated_client.post(f"/recommendations/public/{full_token}", json=payload).status_code == 409

    def test_triage_never_changes_existing_item_and_new_item_is_minimal(self, authenticated_client, db_session):
        existing = authenticated_client.post("/movies/", json={
            "title": "Knives Out", "director": "Rian Johnson", "year": 2019,
            "rating": 9.2, "watched": True, "review": "A review that must remain untouched.",
        }).json()
        postcard = create_postcard(authenticated_client).json()
        token = postcard["share_path"].rsplit("/", 1)[-1]
        base = {"guest_name": "Sam", "category": "movies", "reason": "It is playful, tightly plotted, and never loses its warmth."}
        first = authenticated_client.post(f"/recommendations/public/{token}", json={**base, "title": "knives out"}).json()
        accepted = authenticated_client.post(f"/recommendations/submissions/{first['id']}/triage", json={"action": "library"})
        assert accepted.status_code == 200
        assert accepted.json()["library_changed"] is False
        unchanged = db_session.query(models.Movie).filter_by(id=existing["id"]).one()
        assert (unchanged.director, unchanged.year, unchanged.rating, unchanged.watched, unchanged.review) == (
            "Rian Johnson", 2019, 9.2, True, "A review that must remain untouched.",
        )
        assert authenticated_client.post(f"/recommendations/submissions/{first['id']}/triage", json={"action": "next-up"}).status_code == 409

        second = authenticated_client.post(f"/recommendations/public/{token}", json={**base, "title": "The Kid Detective"}).json()
        queued = authenticated_client.post(f"/recommendations/submissions/{second['id']}/triage", json={"action": "next-up"})
        assert queued.status_code == 200
        assert queued.json()["library_changed"] is True
        assert queued.json()["queued"] is True
        created = db_session.query(models.Movie).filter_by(title="The Kid Detective").one()
        assert created.director == "Unknown director"
        assert created.rating is None and created.watched is False and created.review is None and created.review_public is False
        assert db_session.query(models.NextUpItem).filter_by(item_id=created.id, category="movies").count() == 1

    def test_friend_invitation_requires_friendship_and_one_reply(self, authenticated_client, db_session):
        owner_token = authenticated_client.headers["Authorization"]
        owner = db_session.query(models.User).filter_by(username="testuser").one()
        friend = create_second_user(db_session)
        stranger = create_second_user(db_session, "stranger")
        friendship = crud.create_friendship(db_session, owner.id, friend.id)
        assert friendship is not None
        postcard = create_postcard(authenticated_client).json()

        assert authenticated_client.post(
            f"/recommendations/requests/{postcard['id']}/invite", json={"friend_id": stranger.id}
        ).status_code == 403
        invited = authenticated_client.post(
            f"/recommendations/requests/{postcard['id']}/invite", json={"friend_id": friend.id}
        )
        assert invited.status_code == 201
        assert authenticated_client.post(
            f"/recommendations/requests/{postcard['id']}/invite", json={"friend_id": friend.id}
        ).status_code == 409

        login = authenticated_client.post("/auth/login", data={"username": friend.username, "password": "testpassword123"})
        authenticated_client.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        invitations = authenticated_client.get("/recommendations/invitations/").json()
        assert invitations[0]["sender_username"] == owner.username
        response_payload = {"category": "books", "title": "The Westing Game", "reason": "It has a warm ensemble and a wonderfully playful central puzzle."}
        assert authenticated_client.post(f"/recommendations/requests/{postcard['id']}/respond", json=response_payload).status_code == 201
        assert authenticated_client.post(f"/recommendations/requests/{postcard['id']}/respond", json=response_payload).status_code == 409

        authenticated_client.headers = {"Authorization": owner_token}
        assert authenticated_client.get("/recommendations/inbox/").json()[0]["guest_name"] == friend.username

    def test_postcard_owner_isolation(self, authenticated_client, db_session):
        owner_token = authenticated_client.headers["Authorization"]
        postcard = create_postcard(authenticated_client).json()
        other = create_second_user(db_session)
        login = authenticated_client.post("/auth/login", data={"username": other.username, "password": "testpassword123"})
        authenticated_client.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert authenticated_client.get("/recommendations/requests/").json() == []
        assert authenticated_client.post(f"/recommendations/requests/{postcard['id']}/close").status_code == 404
        authenticated_client.headers = {"Authorization": owner_token}
