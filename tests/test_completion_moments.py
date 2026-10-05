"""Completion reflection and Monthly Replay coverage."""


class TestCompletionMoments:
    def test_create_update_and_replay_completion_moment(self, authenticated_client, test_movie_data):
        movie = authenticated_client.post("/movies/", json=test_movie_data).json()

        created = authenticated_client.post(
            "/completion-moments/", json={"category": "movies", "item_id": movie["id"]}
        )
        assert created.status_code == 200
        moment = created.json()
        assert moment["title"] == test_movie_data["title"]
        assert moment["category_label"] == "Movie"
        assert moment["rating"] == test_movie_data["rating"]

        same_moment = authenticated_client.post(
            "/completion-moments/", json={"category": "movies", "item_id": movie["id"]}
        )
        assert same_moment.status_code == 200
        assert same_moment.json()["id"] == moment["id"]

        updated = authenticated_client.patch(
            f"/completion-moments/{moment['id']}",
            json={"takeaway": "The ending stayed with me.", "favorite": True},
        )
        assert updated.status_code == 200
        assert updated.json()["favorite"] is True

        replay = authenticated_client.get("/completion-moments/replay/")
        assert replay.status_code == 200
        data = replay.json()
        assert data["completed_count"] == 1
        assert data["reflection_count"] == 1
        assert data["favorite_count"] == 1
        assert data["highlights"][0]["title"] == test_movie_data["title"]

    def test_only_finished_owned_items_can_receive_moments(self, authenticated_client, test_movie_data):
        movie_data = test_movie_data.copy()
        movie_data["watched"] = False
        movie = authenticated_client.post("/movies/", json=movie_data).json()
        response = authenticated_client.post(
            "/completion-moments/", json={"category": "movies", "item_id": movie["id"]}
        )
        assert response.status_code == 409

        assert authenticated_client.post(
            "/completion-moments/", json={"category": "movies", "item_id": 99999}
        ).status_code == 404

    def test_completion_moments_require_authentication(self, client):
        assert client.get("/completion-moments/replay/").status_code == 401


STANDALONE_REVIEW = (
    "The Matrix still feels sharp because every action scene is built around an idea about control and choice. "
    "The lobby shootout is pure style, but the quieter scenes on the ship give the story its weight. Some of the "
    "philosophy is spelled out a little too neatly, yet the final act earns its confidence and the effects hold up."
)


class TestFinishReviewPrompt:
    """The finish modal can turn a just-finished title into a review (Oct 2026)."""

    def start(self, client, data, **overrides):
        movie = client.post("/movies/", json={**data, **overrides}).json()
        moment = client.post("/completion-moments/", json={"category": "movies", "item_id": movie["id"]}).json()
        return movie, moment

    def test_moment_reports_whether_a_review_exists(self, authenticated_client, test_movie_data):
        _, with_review = self.start(authenticated_client, test_movie_data)
        assert with_review["has_review"] is True
        _, without = self.start(authenticated_client, test_movie_data, title="Blank", review=None)
        assert without["has_review"] is False

    def test_public_review_is_saved_and_gets_its_own_page(self, authenticated_client, client, test_movie_data):
        movie, moment = self.start(authenticated_client, test_movie_data, review=None)
        response = authenticated_client.post(f"/completion-moments/{moment['id']}/review",
                                             json={"review": f"  {STANDALONE_REVIEW}  ", "public": True})
        assert response.status_code == 200
        body = response.json()
        assert body["public"] and body["listed"] and body["standalone"]
        assert body["substantial"] is False and body["word_count"] > 35
        assert body["review_url"] == f"/reviews/{movie['id']}?category=movie"
        saved = authenticated_client.get(f"/movies/{movie['id']}").json()
        assert saved["review"] == STANDALONE_REVIEW and saved["review_public"] is True
        assert "The Matrix" in client.get(body["review_url"]).text

    def test_private_review_stays_private(self, authenticated_client, test_movie_data):
        movie, moment = self.start(authenticated_client, test_movie_data, review=None)
        body = authenticated_client.post(f"/completion-moments/{moment['id']}/review",
                                         json={"review": STANDALONE_REVIEW, "public": False}).json()
        assert body == {**body, "public": False, "listed": False, "standalone": False, "review_url": None}
        assert authenticated_client.get(f"/movies/{movie['id']}").json()["review_public"] is False

    def test_never_overwrites_an_existing_review(self, authenticated_client, test_movie_data):
        movie, moment = self.start(authenticated_client, test_movie_data)
        response = authenticated_client.post(f"/completion-moments/{moment['id']}/review",
                                             json={"review": "Replacement", "public": True})
        assert response.status_code == 409
        assert authenticated_client.get(f"/movies/{movie['id']}").json()["review"] == test_movie_data["review"]

    def test_rejects_blank_and_foreign_moments(self, authenticated_client, test_movie_data):
        _, moment = self.start(authenticated_client, test_movie_data, review=None)
        assert authenticated_client.post(f"/completion-moments/{moment['id']}/review",
                                         json={"review": "   ", "public": True}).status_code == 422
        assert authenticated_client.post("/completion-moments/99999/review",
                                         json={"review": "Hi", "public": False}).status_code == 404

    def test_requires_authentication(self, client):
        assert client.post("/completion-moments/1/review", json={"review": "Hi"}).status_code == 401
