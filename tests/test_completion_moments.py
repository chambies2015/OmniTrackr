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
