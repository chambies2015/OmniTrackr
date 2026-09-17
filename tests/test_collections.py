"""Cross-media Collection API coverage, including anime."""

from app import crud, models
from app.routers import collections as collections_router
from app.routers.export_import import _export_collections, _import_collections
from sqlalchemy import event
from starlette.requests import Request
from starlette.responses import Response


PUBLIC_INTRO = (
    "These are the titles I return to when I need a little room to think. Each one rewards attention in a "
    "different way, but together they remind me that a memorable experience can be quiet, curious, and kind. "
    "I keep them close because they make a strong case for taking art at its own pace instead of treating every "
    "watch, read, or play session as something to optimize. They are companions for a reflective weekend."
)


def _publish_three_item_collection(authenticated_client, test_movie_data, test_anime_data, test_book_data):
    collection = authenticated_client.post(
        "/collections/", json={"name": "Small things that stayed with me", "description": PUBLIC_INTRO}
    ).json()
    records = [
        ("movies", authenticated_client.post("/movies/", json=test_movie_data).json()),
        ("anime", authenticated_client.post("/anime/", json=test_anime_data).json()),
        ("books", authenticated_client.post("/books/", json=test_book_data).json()),
    ]
    item_responses = []
    for category, record in records:
        item_responses.append(authenticated_client.post(
            f"/collections/{collection['id']}/items", json={"category": category, "item_id": record["id"]}
        ).json())
    published = authenticated_client.patch(
        f"/collections/{collection['id']}", json={"is_public": True}
    )
    assert published.status_code == 200
    return published.json(), records, item_responses


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

    def test_empty_gallery_stays_out_of_search_inventory(self, client):
        gallery = client.get("/collections/explore")
        assert gallery.status_code == 200
        assert gallery.headers["x-robots-tag"] == "noindex, follow"
        assert '<meta name="robots" content="noindex, follow">' in gallery.text
        assert "/collections/explore" not in client.get("/sitemap.xml").text

    def test_moderation_requires_configured_trusted_username(self, authenticated_client, monkeypatch):
        monkeypatch.delenv("COLLECTION_MODERATOR_USERNAMES", raising=False)
        assert authenticated_client.get("/collections/moderation/queue").status_code == 403
        assert authenticated_client.get("/collections/moderation/insights").status_code == 403

    def test_moderator_insights_are_aggregate_and_exclude_private_user_data(
        self, authenticated_client, db_session, test_movie_data, monkeypatch
    ):
        monkeypatch.setenv("COLLECTION_MODERATOR_USERNAMES", "testuser")
        assert authenticated_client.post("/movies/", json=test_movie_data).status_code == 201
        assert authenticated_client.post("/auth/register", json={
            "email": "new-reader@example.com",
            "username": "newreader",
            "password": "readerpassword123",
        }).status_code == 201
        owner = db_session.query(models.User).filter(models.User.username == "testuser").one()
        db_session.add(models.ActivityEntry(
            user_id=owner.id,
            category="movies",
            title="Private journal title",
            action="watched",
            note="Private reflection",
        ))
        db_session.commit()

        response = authenticated_client.get("/collections/moderation/insights")
        assert response.status_code == 200
        insights = response.json()
        assert insights["users"]["total"] == 2
        assert insights["content"]["total_items"] == 1
        assert insights["content"]["categories"][0]["label"] == "Movies"
        assert insights["engagement"]["activity_entries_30_days"] == 1
        assert [stage["key"] for stage in insights["activation"]] == [
            "registered", "verified", "started", "activated", "returned"
        ]
        assert [stage["count"] for stage in insights["activation"]] == [2, 1, 1, 0, 0]
        assert {row["username"] for row in insights["recent_users"]} == {"testuser", "newreader"}
        serialized = response.text
        assert "new-reader@example.com" not in serialized
        assert "Private journal title" not in serialized
        assert "Private reflection" not in serialized
        assert "hashed_password" not in serialized

    def test_moderator_activation_uses_existing_library_and_minimal_login_counts(
        self, authenticated_client, test_movie_data, monkeypatch
    ):
        monkeypatch.setenv("COLLECTION_MODERATOR_USERNAMES", "testuser")
        for index in range(5):
            payload = {**test_movie_data, "title": f"Activation title {index}"}
            assert authenticated_client.post("/movies/", json=payload).status_code == 201

        second_login = authenticated_client.post(
            "/auth/login", data={"username": "testuser", "password": "testpassword123"}
        )
        assert second_login.status_code == 200

        activation = authenticated_client.get("/collections/moderation/insights").json()["activation"]
        assert [stage["count"] for stage in activation] == [1, 1, 1, 1, 1]
        assert activation[-1]["label"] == "Returned after activation"
        assert activation[-1]["step_rate"] == 100.0

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

        published = authenticated_client.patch(
            f"/collections/{collection_id}", json={"description": PUBLIC_INTRO, "is_public": True}
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
        assert public_page.headers["x-robots-tag"] == "noindex, follow"
        assert '<meta name="robots" content="noindex, follow">' in public_page.text
        assert public_url not in authenticated_client.get("/sitemap.xml").text

        unpublished = authenticated_client.patch(f"/collections/{collection_id}", json={"is_public": False})
        assert unpublished.status_code == 200
        assert unpublished.json()["is_public"] is False
        assert authenticated_client.get(public_url).status_code == 404

    def test_approved_collection_enters_gallery_and_edit_returns_it_to_review(
        self, authenticated_client, test_movie_data, test_anime_data, test_book_data, monkeypatch
    ):
        monkeypatch.setenv("COLLECTION_MODERATOR_USERNAMES", "testuser")
        collection, _, items = _publish_three_item_collection(
            authenticated_client, test_movie_data, test_anime_data, test_book_data
        )

        assert collection["moderation_status"] == "pending"
        assert collection["name"] not in authenticated_client.get("/collections/explore").text
        approved = authenticated_client.patch(
            f"/collections/{collection['id']}/moderation", json={"status": "approved"}
        )
        assert approved.status_code == 200
        assert approved.json()["moderation_status"] == "approved"
        assert collection["name"] in authenticated_client.get("/collections/explore").text
        detail = authenticated_client.get(collection["public_url"])
        assert detail.headers["x-robots-tag"] == "index, follow"
        assert collection["public_url"] in authenticated_client.get("/sitemap.xml").text

        updated = authenticated_client.patch(
            f"/collections/{collection['id']}/items/{items[0]['id']}",
            json={"curator_note": "Notice how the story makes restraint feel active rather than empty."},
        )
        assert updated.status_code == 200
        assert updated.json()["curator_note"].startswith("Notice how")
        collection_after_edit = authenticated_client.get("/collections/").json()[0]
        assert collection_after_edit["moderation_status"] == "pending"
        assert collection["name"] not in authenticated_client.get("/collections/explore").text
        assert collection["public_url"] not in authenticated_client.get("/sitemap.xml").text

    def test_editing_referenced_media_invalidates_approval(
        self, authenticated_client, test_movie_data, test_anime_data, test_book_data, monkeypatch
    ):
        monkeypatch.setenv("COLLECTION_MODERATOR_USERNAMES", "testuser")
        collection, records, _ = _publish_three_item_collection(
            authenticated_client, test_movie_data, test_anime_data, test_book_data
        )
        assert authenticated_client.patch(
            f"/collections/{collection['id']}/moderation", json={"status": "approved"}
        ).status_code == 200

        movie = records[0][1]
        assert authenticated_client.put(
            f"/movies/{movie['id']}", json={"title": "Unreviewed replacement title"}
        ).status_code == 200

        detail = authenticated_client.get(collection["public_url"])
        assert detail.headers["x-robots-tag"] == "noindex, follow"
        assert collection["name"] not in authenticated_client.get("/collections/explore").text
        assert collection["public_url"] not in authenticated_client.get("/sitemap.xml").text
        assert authenticated_client.get("/collections/").json()[0]["moderation_status"] == "pending"

    def test_inactive_owner_collection_is_not_sitemapped(
        self, authenticated_client, db_session, test_movie_data, test_anime_data, test_book_data, monkeypatch
    ):
        monkeypatch.setenv("COLLECTION_MODERATOR_USERNAMES", "testuser")
        collection, _, _ = _publish_three_item_collection(
            authenticated_client, test_movie_data, test_anime_data, test_book_data
        )
        authenticated_client.patch(
            f"/collections/{collection['id']}/moderation", json={"status": "approved"}
        )
        user = db_session.query(models.User).filter(models.User.username == "testuser").one()
        user.is_active = False
        db_session.commit()

        assert collection["public_url"] not in authenticated_client.get("/sitemap.xml").text
        assert authenticated_client.get(collection["public_url"]).status_code == 404

    def test_public_feedback_is_pseudonymous_and_idempotent(
        self, authenticated_client, db_session, test_movie_data, test_anime_data, test_book_data
    ):
        collection, _, _ = _publish_three_item_collection(
            authenticated_client, test_movie_data, test_anime_data, test_book_data
        )
        first = authenticated_client.post(f"{collection['public_url']}/helpful")
        second = authenticated_client.post(f"{collection['public_url']}/helpful")
        assert first.status_code == 200
        assert second.json()["count"] == 1
        assert db_session.query(models.CollectionReaction).count() == 1

        report = {"reason": "spam", "details": "Repeated promotional links."}
        assert authenticated_client.post(f"{collection['public_url']}/report", json=report).status_code == 201
        assert authenticated_client.post(f"{collection['public_url']}/report", json=report).status_code == 201
        assert db_session.query(models.CollectionReport).count() == 1

    def test_public_detail_uses_signed_cookie_and_private_cache_policy(
        self, authenticated_client, db_session, test_movie_data, test_anime_data, test_book_data,
        monkeypatch,
    ):
        collection, _, _ = _publish_three_item_collection(
            authenticated_client, test_movie_data, test_anime_data, test_book_data
        )
        authenticated_client.cookies.delete(collections_router.VISITOR_COOKIE)
        first = authenticated_client.get(collection["public_url"])
        assert first.status_code == 200
        assert first.headers["cache-control"].startswith("private, no-cache")
        assert db_session.query(models.CollectionView).count() == 0

        second = authenticated_client.get(collection["public_url"])
        assert second.status_code == 200
        assert collections_router.VISITOR_COOKIE not in second.headers.get("set-cookie", "")
        assert db_session.query(models.CollectionView).count() == 1
        assert db_session.query(models.Collection).filter_by(id=collection["id"]).one().view_count == 1

        forged_cookie = f"attacker-controlled.{'0' * 64}"
        # Cookie identity includes domain/path. Remove the server-scoped cookie
        # before adding a hostless forged value, rather than sending both.
        authenticated_client.cookies.delete(collections_router.VISITOR_COOKIE)
        authenticated_client.cookies.set(collections_router.VISITOR_COOKIE, forged_cookie)
        monkeypatch.setenv("ENVIRONMENT", "production")
        replacement_response = authenticated_client.get(collection["public_url"])
        assert replacement_response.status_code == 200
        sent_cookies = replacement_response.request.headers["cookie"]
        assert sent_cookies.count(f"{collections_router.VISITOR_COOKIE}=") == 1
        assert f"{collections_router.VISITOR_COOKIE}={forged_cookie}" in sent_cookies
        set_cookie = replacement_response.headers["set-cookie"]
        replacement_cookie = replacement_response.cookies.get(collections_router.VISITOR_COOKIE)

        assert forged_cookie not in set_cookie
        assert replacement_cookie and replacement_cookie != forged_cookie
        payload, _ = replacement_cookie.rsplit(".", 1)
        assert replacement_cookie == collections_router._sign_visitor_token(payload)
        assert "httponly" in set_cookie.lower()
        assert "samesite=lax" in set_cookie.lower()
        assert "secure" in set_cookie.lower()
        assert "max-age=31536000" in set_cookie.lower()
        assert db_session.query(models.CollectionView).count() == 1

    def test_non_ascii_visitor_signature_is_replaced_without_error(self):
        hostile_cookie = b"attacker-controlled." + bytes([233]) * 64
        request = Request({
            "type": "http",
            "headers": [(b"cookie", collections_router.VISITOR_COOKIE.encode() + b"=" + hostile_cookie)],
        })

        _, replacement_cookie, trusted = collections_router._visitor_identity(request)
        response = Response()
        collections_router._set_visitor_cookie(response, replacement_cookie)

        assert trusted is False
        assert replacement_cookie
        assert "attacker-controlled" not in response.headers["set-cookie"]
        payload, _ = replacement_cookie.rsplit(".", 1)
        assert replacement_cookie == collections_router._sign_visitor_token(payload)

    def test_collection_rate_limit_wrappers_are_bound_to_executed_handlers(self):
        protected_paths = {
            "/collections/public/{collection_id}",
            "/collections/public/{collection_id}/helpful",
            "/collections/public/{collection_id}/report",
        }
        routes = [route for route in collections_router.router.routes if route.path in protected_paths]
        assert {route.path for route in routes} == protected_paths
        assert all(route.endpoint is route.dependant.call for route in routes)
        assert all(hasattr(route.endpoint, "__wrapped__") for route in routes)

    def test_copy_public_collection_creates_private_clean_library_records(
        self, authenticated_client, db_session, test_movie_data, test_anime_data, test_book_data
    ):
        collection, _, items = _publish_three_item_collection(
            authenticated_client, test_movie_data, test_anime_data, test_book_data
        )
        authenticated_client.patch(
            f"/collections/{collection['id']}/items/{items[0]['id']}",
            json={"curator_note": "A useful lens for the rest of the list."},
        )

        second_user = {"email": "reader@example.com", "username": "reader", "password": "readerpassword123"}
        registered = authenticated_client.post("/auth/register", json=second_user)
        reader = crud.get_user_by_id(db_session, registered.json()["id"])
        reader.is_verified = True
        reader.verification_token = None
        db_session.commit()
        login = authenticated_client.post(
            "/auth/login", data={"username": second_user["username"], "password": second_user["password"]}
        )
        authenticated_client.headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        copied = authenticated_client.post(f"{collection['public_url']}/copy")
        assert copied.status_code == 201
        assert copied.json()["is_public"] is False
        assert copied.json()["moderation_status"] == "pending"
        assert len(copied.json()["items"]) == 3
        copied_movie = db_session.query(models.Movie).filter(models.Movie.user_id == reader.id).one()
        assert copied_movie.rating is None
        assert copied_movie.review is None
        assert copied_movie.watched is False

    def test_collection_curator_notes_are_in_json_backup(
        self, authenticated_client, test_movie_data
    ):
        movie = authenticated_client.post("/movies/", json=test_movie_data).json()
        collection = authenticated_client.post(
            "/collections/", json={"name": "Backup this shelf", "description": "Private context"}
        ).json()
        item = authenticated_client.post(
            f"/collections/{collection['id']}/items", json={"category": "movies", "item_id": movie["id"]}
        ).json()
        authenticated_client.patch(
            f"/collections/{collection['id']}/items/{item['id']}",
            json={"curator_note": "The opening image changes how the ending lands."},
        )

        backup = authenticated_client.get("/export/").json()
        assert backup["export_metadata"]["version"] == "1.2"
        assert backup["collections"][0]["items"][0]["curator_note"].startswith("The opening")

    def test_collection_backup_preserves_same_title_edition_identity(
        self, authenticated_client, db_session, test_movie_data
    ):
        first_data = {**test_movie_data, "title": "The Return", "year": 1998, "director": "First Director"}
        second_data = {**test_movie_data, "title": "The Return", "year": 2024, "director": "Second Director"}
        first = authenticated_client.post("/movies/", json=first_data).json()
        second = authenticated_client.post("/movies/", json=second_data).json()
        collection = authenticated_client.post("/collections/", json={"name": "Edition-aware backup"}).json()
        authenticated_client.post(
            f"/collections/{collection['id']}/items", json={"category": "movies", "item_id": second["id"]}
        )
        user = db_session.query(models.User).filter(models.User.username == "testuser").one()
        exported = _export_collections(db_session, user.id)
        assert exported[0]["items"][0]["year"] == 2024
        assert exported[0]["items"][0]["director"] == "Second Director"

        db_session.delete(db_session.get(models.Collection, collection["id"]))
        db_session.commit()
        assert _import_collections(db_session, user.id, exported) == (1, 0)
        restored_item = db_session.query(models.CollectionItem).one()
        assert restored_item.item_id == second["id"]
        assert restored_item.item_id != first["id"]

    def test_collection_export_query_count_is_bounded(
        self, authenticated_client, db_session, test_movie_data, test_anime_data
    ):
        collection = authenticated_client.post("/collections/", json={"name": "Efficient backup"}).json()
        for index in range(4):
            movie_data = {**test_movie_data, "title": f"Movie {index}"}
            movie = authenticated_client.post("/movies/", json=movie_data).json()
            authenticated_client.post(
                f"/collections/{collection['id']}/items", json={"category": "movies", "item_id": movie["id"]}
            )
        anime = authenticated_client.post("/anime/", json=test_anime_data).json()
        authenticated_client.post(
            f"/collections/{collection['id']}/items", json={"category": "anime", "item_id": anime["id"]}
        )
        user = db_session.query(models.User).filter(models.User.username == "testuser").one()
        statements = []

        def count_statement(*args):
            statements.append(args[2])

        event.listen(db_session.bind, "before_cursor_execute", count_statement)
        try:
            exported = _export_collections(db_session, user.id)
        finally:
            event.remove(db_session.bind, "before_cursor_execute", count_statement)

        assert len(exported[0]["items"]) == 5
        assert len(statements) <= 8

    def test_collection_gallery_query_count_is_bounded_by_media_types(
        self, authenticated_client, db_session, test_movie_data, test_anime_data, test_book_data, monkeypatch
    ):
        monkeypatch.setenv("COLLECTION_MODERATOR_USERNAMES", "testuser")
        collection, _, _ = _publish_three_item_collection(
            authenticated_client, test_movie_data, test_anime_data, test_book_data
        )
        authenticated_client.patch(
            f"/collections/{collection['id']}/moderation", json={"status": "approved"}
        )
        statements = []

        def count_statement(*args):
            statements.append(args[2])

        event.listen(db_session.bind, "before_cursor_execute", count_statement)
        try:
            response = authenticated_client.get("/collections/explore")
        finally:
            event.remove(db_session.bind, "before_cursor_execute", count_statement)

        assert response.status_code == 200
        assert len(statements) <= 8
