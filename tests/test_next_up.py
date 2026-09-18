"""Coverage for the private, additive Next Up queue."""


class TestNextUpQueue:
    def test_add_reorder_and_remove_queue_items(self, authenticated_client, test_movie_data, test_book_data):
        movie = authenticated_client.post("/movies/", json=test_movie_data).json()
        book = authenticated_client.post("/books/", json=test_book_data).json()

        first = authenticated_client.post("/next-up/", json={"category": "movies", "item_id": movie["id"]})
        assert first.status_code == 201
        assert first.json()["title"] == test_movie_data["title"]
        assert first.json()["position"] == 0

        second = authenticated_client.post("/next-up/", json={"category": "books", "item_id": book["id"]})
        assert second.status_code == 201
        assert authenticated_client.post(
            "/next-up/", json={"category": "movies", "item_id": movie["id"]}
        ).status_code == 409

        moved = authenticated_client.put(f"/next-up/{second.json()['id']}/position", json={"position": 0})
        assert moved.status_code == 200
        assert [item["title"] for item in moved.json()] == [test_book_data["title"], test_movie_data["title"]]

        assert authenticated_client.delete(f"/next-up/{first.json()['id']}").status_code == 204
        listed = authenticated_client.get("/next-up/")
        assert listed.status_code == 200
        assert [item["title"] for item in listed.json()] == [test_book_data["title"]]

    def test_queue_only_accepts_owned_existing_library_items(self, authenticated_client):
        missing_item = authenticated_client.post("/next-up/", json={"category": "movies", "item_id": 9999})
        assert missing_item.status_code == 404

        invalid_category = authenticated_client.post("/next-up/", json={"category": "custom-tabs", "item_id": 1})
        assert invalid_category.status_code == 422

    def test_pulse_prioritizes_next_up_items(self, authenticated_client, test_movie_data):
        movie_data = test_movie_data.copy()
        movie_data["watched"] = False
        movie = authenticated_client.post("/movies/", json=movie_data).json()
        assert authenticated_client.post(
            "/next-up/", json={"category": "movies", "item_id": movie["id"]}
        ).status_code == 201

        pulse = authenticated_client.get("/statistics/pulse/")
        assert pulse.status_code == 200
        assert pulse.json()["next_up_items"] == [{
            "id": movie["id"],
            "title": movie_data["title"],
            "category": "movies",
            "category_label": "Movie",
            "status_label": "Not watched",
            "prompts": [],
        }]

    def test_queue_requires_authentication(self, client):
        assert client.get("/next-up/").status_code == 401
