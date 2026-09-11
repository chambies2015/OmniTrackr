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

    def test_collection_publish_is_explicit_quality_gated_and_reversible(
        self, authenticated_client, test_movie_data, test_anime_data, test_book_data
    ):
        collection = authenticated_client.post(
            "/collections/", json={"name": "Small things that stayed with me", "description": "Private draft."}
        ).json()
        collection_id = collection["id"]
        assert collection["is_public"] is False
        assert collection["public_url"] is None
        assert authenticated_client.patch(
            f"/collections/{collection_id}", json={"is_public": True}
        ).status_code == 422

        movie = authenticated_client.post("/movies/", json=test_movie_data).json()
        anime = authenticated_client.post("/anime/", json=test_anime_data).json()
        book = authenticated_client.post("/books/", json=test_book_data).json()
        for category, item in [("movies", movie), ("anime", anime), ("books", book)]:
            assert authenticated_client.post(
                f"/collections/{collection_id}/items", json={"category": category, "item_id": item["id"]}
            ).status_code == 201

        introduction = (
            "These are the titles I return to when I need a little room to think. Each one rewards attention in a "
            "different way, but together they remind me that a memorable experience can be quiet, curious, and kind. "
            "I keep them close because they make a strong case for taking art at its own pace instead of treating every "
            "watch, read, or play session as something to optimize. They are companions for a reflective weekend."
        )
        published = authenticated_client.patch(
            f"/collections/{collection_id}", json={"description": introduction, "is_public": True}
        )
        assert published.status_code == 200
        assert published.json()["is_public"] is True
        public_url = published.json()["public_url"]
        public_page = authenticated_client.get(public_url)
        assert public_page.status_code == 200
        assert collection["name"] in public_page.text
        assert movie["title"] in public_page.text
        assert "Private draft." not in public_page.text
        assert test_movie_data["review"] not in public_page.text
        assert public_url in authenticated_client.get("/sitemap.xml").text

        unpublished = authenticated_client.patch(f"/collections/{collection_id}", json={"is_public": False})
        assert unpublished.status_code == 200
        assert unpublished.json()["is_public"] is False
        assert authenticated_client.get(public_url).status_code == 404
