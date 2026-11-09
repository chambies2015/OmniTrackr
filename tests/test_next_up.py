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
            "image": None,
        }]

    def test_queue_requires_authentication(self, client):
        assert client.get("/next-up/").status_code == 401
        assert client.post("/next-up/1/finish").status_code == 401
        assert client.post("/next-up/clear-finished").status_code == 401

    def test_queue_reports_finished_titles_and_cover_art(self, authenticated_client, test_movie_data, test_book_data):
        movie = authenticated_client.post("/movies/", json={**test_movie_data, "watched": False,
                                                            "poster_url": "https://img.example/matrix.jpg"}).json()
        book = authenticated_client.post("/books/", json=test_book_data).json()
        for category, item in (("movies", movie), ("books", book)):
            assert authenticated_client.post("/next-up/", json={"category": category, "item_id": item["id"]}).status_code == 201

        listed = {item["title"]: item for item in authenticated_client.get("/next-up/").json()}
        assert listed[test_movie_data["title"]]["finished"] is False
        assert listed[test_movie_data["title"]]["image"] == "https://img.example/matrix.jpg"
        assert listed[test_book_data["title"]]["finished"] is True
        assert listed[test_book_data["title"]]["image"] is None

    def test_done_marks_the_title_finished_and_takes_it_off_the_queue(self, authenticated_client, test_movie_data, test_book_data):
        movie = authenticated_client.post("/movies/", json={**test_movie_data, "watched": False}).json()
        book = authenticated_client.post("/books/", json={**test_book_data, "read": False}).json()
        first = authenticated_client.post("/next-up/", json={"category": "movies", "item_id": movie["id"]}).json()
        authenticated_client.post("/next-up/", json={"category": "books", "item_id": book["id"]})

        done = authenticated_client.post(f"/next-up/{first['id']}/finish")
        assert done.status_code == 200
        assert done.json() == {"category": "movies", "item_id": movie["id"], "title": test_movie_data["title"], "was_finished": False}

        updated = authenticated_client.get(f"/movies/{movie['id']}").json()
        assert updated["watched"] is True
        # Only the completion flag changes.
        assert (updated["rating"], updated["review"], updated["director"]) == (
            test_movie_data["rating"], test_movie_data["review"], test_movie_data["director"])
        remaining = authenticated_client.get("/next-up/").json()
        assert [(item["title"], item["position"]) for item in remaining] == [(test_book_data["title"], 0)]

        # A reflection can be opened straight after, as it can from the library.
        assert authenticated_client.post("/completion-moments/", json={"category": "movies", "item_id": movie["id"]}).status_code == 200
        assert authenticated_client.post(f"/next-up/{first['id']}/finish").status_code == 404

    def test_done_on_an_already_finished_title_just_clears_it(self, authenticated_client, test_book_data):
        book = authenticated_client.post("/books/", json=test_book_data).json()
        entry = authenticated_client.post("/next-up/", json={"category": "books", "item_id": book["id"]}).json()
        done = authenticated_client.post(f"/next-up/{entry['id']}/finish").json()
        assert done["was_finished"] is True
        assert authenticated_client.get("/next-up/").json() == []

    def test_clear_finished_keeps_unfinished_titles_in_order(self, authenticated_client, test_movie_data, test_book_data):
        finished = authenticated_client.post("/books/", json=test_book_data).json()
        first = authenticated_client.post("/movies/", json={**test_movie_data, "watched": False}).json()
        second = authenticated_client.post("/movies/", json={**test_movie_data, "title": "Arrival", "watched": False}).json()
        for category, item in (("movies", first), ("books", finished), ("movies", second)):
            authenticated_client.post("/next-up/", json={"category": category, "item_id": item["id"]})

        cleared = authenticated_client.post("/next-up/clear-finished")
        assert cleared.status_code == 200
        assert [(item["title"], item["position"]) for item in cleared.json()] == [(test_movie_data["title"], 0), ("Arrival", 1)]
        assert authenticated_client.get(f"/books/{finished['id']}").json()["read"] is True

    def test_done_needs_an_entry_in_your_queue(self, authenticated_client):
        assert authenticated_client.post("/next-up/999999/finish").status_code == 404


class TestStartingFromTheQueue:
    def _queue(self, client, *items):
        return [client.post("/next-up/", json={"category": category, "item_id": item["id"]}).json() for category, item in items]

    def test_start_moves_the_title_to_the_top_and_leaves_the_library_alone(self, authenticated_client, test_movie_data, test_book_data):
        movie = authenticated_client.post("/movies/", json={**test_movie_data, "watched": False}).json()
        book = authenticated_client.post("/books/", json={**test_book_data, "read": False}).json()
        first, second = self._queue(authenticated_client, ("movies", movie), ("books", book))
        assert first["started_at"] is None and first["now_label"] == "Watching"

        started = authenticated_client.post(f"/next-up/{second['id']}/start")
        assert started.status_code == 200
        rows = started.json()
        assert [(row["title"], row["position"]) for row in rows] == [(test_book_data["title"], 0), (test_movie_data["title"], 1)]
        assert rows[0]["started_at"] and rows[0]["now_label"] == "Reading"
        assert rows[1]["started_at"] is None

        # Starting again keeps the first date.
        again = authenticated_client.post(f"/next-up/{second['id']}/start").json()
        assert again[0]["started_at"] == rows[0]["started_at"]

        library_book = authenticated_client.get(f"/books/{book['id']}").json()
        assert library_book["read"] is False
        assert (library_book["rating"], library_book["review"]) == (test_book_data["rating"], test_book_data["review"])

    def test_undo_start_keeps_the_place_in_the_queue(self, authenticated_client, test_movie_data, test_book_data):
        movie = authenticated_client.post("/movies/", json={**test_movie_data, "watched": False}).json()
        book = authenticated_client.post("/books/", json={**test_book_data, "read": False}).json()
        first, _ = self._queue(authenticated_client, ("movies", movie), ("books", book))
        authenticated_client.post(f"/next-up/{first['id']}/start")
        undone = authenticated_client.delete(f"/next-up/{first['id']}/start")
        assert undone.status_code == 200
        assert [(row["title"], row["started_at"]) for row in undone.json()] == [
            (test_movie_data["title"], None), (test_book_data["title"], None)]

    def test_started_titles_lead_continue(self, authenticated_client, test_movie_data):
        older = authenticated_client.post("/movies/", json={**test_movie_data, "watched": False}).json()
        newer = authenticated_client.post("/movies/", json={**test_movie_data, "title": "Arrival", "watched": False}).json()
        entry, _ = self._queue(authenticated_client, ("movies", older), ("movies", newer))
        before = authenticated_client.get("/statistics/pulse/").json()["continue_items"]
        assert before[0]["title"] == "Arrival"

        authenticated_client.post(f"/next-up/{entry['id']}/start")
        after = authenticated_client.get("/statistics/pulse/").json()["continue_items"]
        assert [(item["title"], item["status_label"]) for item in after[:2]] == [
            (test_movie_data["title"], "Watching now"), ("Arrival", "Not watched")]
        assert len([item for item in after if item["id"] == older["id"]]) == 1

        # Once it's finished it stops showing as on the go.
        authenticated_client.put(f"/movies/{older['id']}", json={"watched": True})
        finished = authenticated_client.get("/statistics/pulse/").json()["continue_items"]
        assert all(item["id"] != older["id"] for item in finished)

    def test_start_is_owner_only(self, authenticated_client, client, test_movie_data):
        movie = authenticated_client.post("/movies/", json={**test_movie_data, "watched": False}).json()
        (entry,) = self._queue(authenticated_client, ("movies", movie))
        assert authenticated_client.post("/next-up/999999/start").status_code == 404
        assert authenticated_client.delete("/next-up/999999/start").status_code == 404
        authenticated_client.headers.pop("Authorization", None)
        authenticated_client.cookies.clear()
        assert client.post(f"/next-up/{entry['id']}/start").status_code == 401


class TestQueueSuggestions:
    def test_suggests_unfinished_titles_that_are_not_queued(self, authenticated_client, test_movie_data, test_book_data):
        unfinished = authenticated_client.post("/movies/", json={**test_movie_data, "watched": False}).json()
        queued = authenticated_client.post("/movies/", json={**test_movie_data, "title": "Arrival", "watched": False}).json()
        authenticated_client.post("/books/", json={**test_book_data, "read": True})
        authenticated_client.post("/next-up/", json={"category": "movies", "item_id": queued["id"]})

        suggestions = authenticated_client.get("/next-up/suggestions")
        assert suggestions.status_code == 200
        assert suggestions.json() == [{
            "category": "movies", "item_id": unfinished["id"], "title": test_movie_data["title"],
            "category_label": "Movie", "image": None,
        }]

    def test_suggestions_take_turns_between_formats(self, authenticated_client, test_movie_data, test_book_data):
        for index in range(5):
            authenticated_client.post("/books/", json={**test_book_data, "title": f"Book {index}", "read": False})
        authenticated_client.post("/movies/", json={**test_movie_data, "watched": False})
        rows = authenticated_client.get("/next-up/suggestions").json()
        assert len(rows) == 6
        assert "movies" in [row["category"] for row in rows[:2]]

    def test_suggestions_skip_hidden_tabs(self, authenticated_client, db_session, test_movie_data):
        from app import models
        authenticated_client.post("/movies/", json={**test_movie_data, "watched": False})
        db_session.query(models.User).update({"movies_visible": False})
        db_session.commit()
        assert authenticated_client.get("/next-up/suggestions").json() == []

    def test_suggestions_need_an_account(self, client):
        assert client.get("/next-up/suggestions").status_code == 401
