"""Cross-media Collection API coverage, including anime."""


class TestCollections:
    def test_collection_can_mix_movie_and_anime(self, authenticated_client, test_movie_data, test_anime_data):
        movie = authenticated_client.post("/movies/", json=test_movie_data).json()
        anime = authenticated_client.post("/anime/", json=test_anime_data).json()
        collection = authenticated_client.post(
            "/collections/", json={"name": "Weekend worlds", "description": "A little escape."}
        )
        assert collection.status_code == 201
        collection_id = collection.json()["id"]

        assert authenticated_client.post(
            f"/collections/{collection_id}/items", json={"category": "movies", "item_id": movie["id"]}
        ).status_code == 201
        anime_item = authenticated_client.post(
            f"/collections/{collection_id}/items", json={"category": "anime", "item_id": anime["id"]}
        )
        assert anime_item.status_code == 201
        assert anime_item.json()["category_label"] == "Anime"
        assert authenticated_client.post(
            f"/collections/{collection_id}/items", json={"category": "anime", "item_id": anime["id"]}
        ).status_code == 409

        listed = authenticated_client.get("/collections/")
        assert listed.status_code == 200
        assert {item["category"] for item in listed.json()[0]["items"]} == {"movies", "anime"}

        moved = authenticated_client.put(
            f"/collections/{collection_id}/items/{anime_item.json()['id']}/position", json={"position": 0}
        )
        assert moved.status_code == 200
        assert moved.json()[0]["category"] == "anime"

    def test_collection_validates_item_ownership(self, authenticated_client):
        collection = authenticated_client.post("/collections/", json={"name": "Private shelf"}).json()
        assert authenticated_client.post(
            f"/collections/{collection['id']}/items", json={"category": "books", "item_id": 9999}
        ).status_code == 404

    def test_collections_require_authentication(self, client):
        assert client.get("/collections/").status_code == 401
