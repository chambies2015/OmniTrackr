from html.parser import HTMLParser
from pathlib import Path

import pytest

from app import models
from app.import_studio import classify_rows, parse_csv


def csv_upload(name: str, content: str):
    return {"file": (name, content.encode("utf-8"), "text/csv")}


class TestImportStudio:
    def test_preview_is_read_only_and_apply_is_additive(self, authenticated_client, db_session):
        existing = models.Movie(
            user_id=1, title="The Matrix", director="The Wachowskis", year=1999,
            rating=9.8, watched=True, review="Keep this richer record", review_public=False,
        )
        db_session.add(existing)
        db_session.commit()
        content = (
            "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
            "2026-01-01,The Matrix,1999,https://letterboxd.com/film/the-matrix/,4.0,No,,2026-01-01\n"
            "2026-01-02,Arrival,2016,https://letterboxd.com/film/arrival/,4.5,No,,2026-01-02\n"
        )

        preview = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("watched.csv", content), data={"source": "auto"}
        )
        assert preview.status_code == 200
        data = preview.json()
        assert data["detected_source"] == "letterboxd"
        assert data["ready_count"] == 1
        assert data["duplicate_count"] == 1
        assert data["preview"][0]["values"]["rating"] == 8
        assert data["preview"][0]["values"]["review"] is None
        assert "Keep this richer record" not in preview.text
        assert data["preview"][1]["values"]["rating"] == 9
        assert data["preview"][1]["values"]["completed"] is True
        assert db_session.query(models.Movie).count() == 1

        applied = authenticated_client.post(
            "/import-studio/apply/",
            files=csv_upload("watched.csv", content),
            data={"source": "auto", "fingerprint_confirmation": data["fingerprint"]},
        )
        assert applied.status_code == 200
        assert applied.json()["created_count"] == 1
        assert db_session.query(models.Movie).count() == 2
        unchanged = db_session.query(models.Movie).filter(models.Movie.title == "The Matrix").one()
        assert unchanged.rating == 9.8
        assert unchanged.review == "Keep this richer record"
        arrival = db_session.query(models.Movie).filter(models.Movie.title == "Arrival").one()
        assert arrival.rating == 9.0
        assert arrival.review_public is False

        repeated = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("watched.csv", content), data={"source": "auto"}
        )
        assert repeated.json()["ready_count"] == 0
        assert repeated.json()["duplicate_count"] == 2

    def test_confirmation_is_bound_to_file_and_interpretation(self, authenticated_client):
        content = "title,year\nMoon,2009\n"
        preview = authenticated_client.post(
            "/import-studio/preview/",
            files=csv_upload("movies.csv", content),
            data={"source": "generic", "category": "movies", "mapping_json": "{}"},
        ).json()

        changed_file = authenticated_client.post(
            "/import-studio/apply/",
            files=csv_upload("movies.csv", "title,year\nMoon,2010\n"),
            data={
                "source": "generic", "category": "movies", "mapping_json": "{}",
                "fingerprint_confirmation": preview["fingerprint"],
            },
        )
        assert changed_file.status_code == 409
        assert changed_file.headers["cache-control"] == "private, no-store"

        changed_mapping = authenticated_client.post(
            "/import-studio/apply/",
            files=csv_upload("movies.csv", content),
            data={
                "source": "generic", "category": "movies", "mapping_json": '{"title":"year"}',
                "fingerprint_confirmation": preview["fingerprint"],
            },
        )
        assert changed_mapping.status_code == 409

    def test_goodreads_and_myanimelist_formats(self, authenticated_client, db_session):
        goodreads = (
            "Title,Author,My Rating,Year Published,Exclusive Shelf,Date Read,My Review\n"
            'Piranesi,Susanna Clarke,5,2020,read,2025/02/01,"A private note"\n'
        )
        preview = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("goodreads_library_export.csv", goodreads), data={"source": "auto"}
        ).json()
        assert preview["detected_source"] == "goodreads"
        applied = authenticated_client.post(
            "/import-studio/apply/", files=csv_upload("goodreads_library_export.csv", goodreads),
            data={"source": "auto", "fingerprint_confirmation": preview["fingerprint"]},
        )
        assert applied.status_code == 200
        book = db_session.query(models.Book).one()
        assert book.rating == 10
        assert book.read is True
        assert book.review == "A private note"
        assert book.review_public is False

        mal = (
            "series_title,series_episodes,my_score,my_status,series_start,my_comments\n"
            "Frieren: Beyond Journey's End,28,9,Completed,2023-09-29,Patient and reflective\n"
        )
        mal_preview = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("animelist.csv", mal), data={"source": "auto"}
        ).json()
        assert mal_preview["detected_source"] == "myanimelist"
        mal_apply = authenticated_client.post(
            "/import-studio/apply/", files=csv_upload("animelist.csv", mal),
            data={"source": "auto", "fingerprint_confirmation": mal_preview["fingerprint"]},
        )
        assert mal_apply.status_code == 200
        anime = db_session.query(models.Anime).one()
        assert anime.year == 2023
        assert anime.episodes == 28
        assert anime.watched is True

    def test_generic_mixed_categories_and_column_mapping(self, authenticated_client, db_session):
        content = (
            "Thing,Kind,Maker,Released,My verdict,Done,Thoughts\n"
            "Dune,book,Frank Herbert,1965,9.5,yes,Still enormous\n"
            "Kind of Blue,album,Miles Davis,1959,10,true,Perfect late-night record\n"
        )
        mapping = (
            '{"title":"Thing","category":"Kind","creator":"Maker","year":"Released",'
            '"rating":"My verdict","status":"Done","review":"Thoughts"}'
        )
        preview = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("history.csv", content),
            data={"source": "generic", "mapping_json": mapping},
        )
        assert preview.status_code == 200
        data = preview.json()
        assert data["ready_count"] == 2
        assert data["by_category"]["books"] == 1
        assert data["by_category"]["music"] == 1

        applied = authenticated_client.post(
            "/import-studio/apply/", files=csv_upload("history.csv", content),
            data={"source": "generic", "mapping_json": mapping, "fingerprint_confirmation": data["fingerprint"]},
        )
        assert applied.status_code == 200
        assert db_session.query(models.Book).one().author == "Frank Herbert"
        assert db_session.query(models.Music).one().artist == "Miles Davis"

    def test_generic_csv_supports_all_six_media_categories(self, authenticated_client, db_session):
        content = (
            "title,category,creator,year,release_date,rating,status,genre,seasons,episodes,review\n"
            "Arrival,movie,Denis Villeneuve,2016,,9,watched,Science Fiction,,,Movie note\n"
            "Severance,tv show,,2022,,9,completed,Drama,2,19,TV note\n"
            "Cowboy Bebop,anime,,1998,,10,completed,Science Fiction,1,26,Anime note\n"
            "Hades,video game,,2020,2020-09-17,9.5,played,Roguelike,,,Game note\n"
            "Blue,music,Joni Mitchell,1971,,10,listened,Folk,,,Music note\n"
            "Beloved,book,Toni Morrison,1987,,10,read,Fiction,,,Book note\n"
        )
        preview = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("all-media.csv", content), data={"source": "generic"}
        ).json()
        assert preview["ready_count"] == 6
        assert all(preview["by_category"][category] == 1 for category in (
            "movies", "tv-shows", "anime", "video-games", "music", "books"
        ))
        candidates = {item["category"]: item["values"] for item in preview["preview"]}
        assert all(values["completed"] for values in candidates.values())
        assert candidates["movies"]["creator"] == "Denis Villeneuve"
        assert candidates["movies"]["year"] == 2016
        assert candidates["tv-shows"]["seasons"] == 2
        assert candidates["tv-shows"]["episodes"] == 19
        assert candidates["anime"]["seasons"] == 1
        assert candidates["anime"]["episodes"] == 26
        assert candidates["video-games"]["release_date"] == "2020-09-17"
        assert candidates["video-games"]["rating"] == 9.5
        assert candidates["music"]["creator"] == "Joni Mitchell"
        assert candidates["books"]["creator"] == "Toni Morrison"
        applied = authenticated_client.post(
            "/import-studio/apply/", files=csv_upload("all-media.csv", content),
            data={"source": "generic", "fingerprint_confirmation": preview["fingerprint"]},
        )
        assert applied.status_code == 200
        assert applied.json()["created_count"] == 6
        for category, model, completion_field in (
            ("movies", models.Movie, "watched"), ("tv-shows", models.TVShow, "watched"),
            ("anime", models.Anime, "watched"), ("video-games", models.VideoGame, "played"),
            ("music", models.Music, "listened"), ("books", models.Book, "read"),
        ):
            saved = db_session.query(model).one()
            assert getattr(saved, completion_field) is True
            assert saved.rating == candidates[category]["rating"]
            assert saved.review == candidates[category]["review"]
            assert saved.review_public is False
        assert db_session.query(models.VideoGame).one().release_date.date().isoformat() == "2020-09-17"
        assert db_session.query(models.VideoGame).one().genres == "Roguelike"
        assert db_session.query(models.Music).one().genre == "Folk"
        assert db_session.query(models.Book).one().genre == "Fiction"

        repeated = authenticated_client.post(
            "/import-studio/apply/", files=csv_upload("all-media.csv", content),
            data={"source": "generic", "fingerprint_confirmation": preview["fingerprint"]},
        )
        assert repeated.status_code == 200
        assert repeated.json()["created_count"] == 0
        assert repeated.json()["duplicate_count"] == 6

    def test_invalid_rows_are_reported_without_blocking_valid_rows(self, authenticated_client, db_session):
        content = "title,category,year\nValid Film,movie,2020\n,book,2021\nUnknown Thing,podcast,2022\n"
        preview = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("mixed.csv", content), data={"source": "generic"}
        )
        assert preview.status_code == 200
        data = preview.json()
        assert data["ready_count"] == 1
        assert data["invalid_count"] == 2
        assert db_session.query(models.Movie).count() == 0
        assert any(item["status"] == "invalid" for item in data["preview"])

    def test_file_validation_templates_and_private_headers(self, authenticated_client):
        wrong = authenticated_client.post(
            "/import-studio/preview/", files={"file": ("history.exe", b"title\nAlien", "text/plain")}
        )
        assert wrong.status_code == 400
        assert wrong.headers["cache-control"] == "private, no-store"

        undecodable = authenticated_client.post(
            "/import-studio/preview/", files={"file": ("history.csv", b"\xff\xfe\x00", "text/csv")}
        )
        assert undecodable.status_code == 400

        template = authenticated_client.get("/import-studio/template/books/")
        assert template.status_code == 200
        assert template.headers["content-type"].startswith("text/csv")
        assert "attachment" in template.headers["content-disposition"]
        assert template.text.startswith("title,author,year")
        assert template.headers["cache-control"] == "private, no-store"
        assert template.headers["x-robots-tag"] == "noindex, nofollow"

    def test_import_studio_requires_authentication(self, client):
        content = "title,category\nArrival,movie\n"
        preview = client.post("/import-studio/preview/", files=csv_upload("items.csv", content))
        assert preview.status_code == 401
        assert preview.headers["cache-control"] == "private, no-store"
        template = client.get("/import-studio/template/movies/")
        assert template.status_code == 401

    def test_dashboard_and_public_guide_explain_the_safe_workflow(self, authenticated_client, client):
        dashboard = authenticated_client.get("/")
        assert dashboard.status_code == 200
        assert 'id="importStudio"' in dashboard.text
        assert "Preview import" in dashboard.text
        assert "Existing records are never overwritten" in dashboard.text
        assert 'data-action="apply-library-import"' in dashboard.text

        guide = client.get("/export-import-guide")
        assert guide.status_code == 200
        assert "How Import Helps: Two Paths with Different Jobs" in guide.text
        assert "Letterboxd" in guide.text
        assert "Goodreads" in guide.text
        assert "MyAnimeList" in guide.text
        assert "The confirmed batch is atomic" in guide.text

    def test_filtered_pagination_reaches_every_error_and_keeps_confirmation(self, authenticated_client, db_session):
        content = "title,category,rating\n" + "".join(f"Film {index},movies,8\n" for index in range(130))
        content += "Film 0,movies,4\nBroken rating,movies,nan\nMissing category,podcast,8\n"
        options = {"source": "generic"}

        def preview(**paging):
            response = authenticated_client.post(
                "/import-studio/preview/", files=csv_upload("large.csv", content), data={**options, **paging},
            )
            assert response.status_code == 200
            assert response.headers["cache-control"] == "private, no-store"
            return response.json()

        first = preview()
        assert first["preview_total"] == first["total_rows"] == 133
        assert first["preview_offset"] == 0
        assert first["preview_limit"] == len(first["preview"]) == 100
        assert first["preview_truncated"] is True
        second = preview(offset=100)
        assert [row["row"] for row in first["preview"] + second["preview"]] == list(range(2, 135))
        errors = preview(status_filter="invalid", limit=1)
        next_error = preview(status_filter="invalid", limit=1, offset=1)
        assert errors["preview_total"] == 2
        assert errors["preview"][0]["row"] == 133
        assert errors["preview"][0]["values"] is None
        assert "Rating" in errors["preview"][0]["reason"]
        assert next_error["preview"][0]["row"] == 134
        duplicate = preview(status_filter="duplicate")
        assert duplicate["preview_total"] == 1
        assert duplicate["preview"][0]["values"]["rating"] == 4
        for result in (second, errors, next_error, duplicate):
            assert result["fingerprint"] == first["fingerprint"]
            assert result["ready_count"] == 130
            assert result["duplicate_count"] == 1
            assert result["invalid_count"] == 2
            assert result["by_category"]["movies"] == 130
        assert db_session.query(models.Movie).count() == 0

        applied = authenticated_client.post(
            "/import-studio/apply/", files=csv_upload("large.csv", content),
            data={**options, "fingerprint_confirmation": errors["fingerprint"]},
        )
        assert applied.status_code == 200
        assert applied.json()["created_count"] == 130
        assert applied.json()["invalid_count"] == 2
        assert applied.json()["duplicate_count"] == 1

    @pytest.mark.parametrize("paging", [
        {"status_filter": "anything"}, {"offset": -1}, {"limit": 0}, {"limit": 101}, {"offset": "nan"},
    ])
    def test_invalid_preview_options_are_private_errors(self, authenticated_client, paging):
        response = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("items.csv", "title,category\nArrival,movies\n"), data=paging,
        )
        assert response.status_code == 422
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-robots-tag"] == "noindex, nofollow"

    def test_failed_batch_rolls_back_every_new_row(self, authenticated_client, db_session, monkeypatch):
        existing = models.Music(user_id=1, title="Keep", artist="Me", year=2025, rating=9.5, listened=True, review="Private")
        db_session.add(existing)
        db_session.commit()
        content = "title,category,creator,year\nFirst,movies,Director,2025\nSecond,books,Author,2025\n"
        options = {"source": "generic"}
        preview = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("batch.csv", content), data=options,
        ).json()

        def fail_commit():
            db_session.flush()
            raise RuntimeError("Synthetic storage failure")

        monkeypatch.setattr(db_session, "commit", fail_commit)
        response = authenticated_client.post(
            "/import-studio/apply/", files=csv_upload("batch.csv", content),
            data={**options, "fingerprint_confirmation": preview["fingerprint"]},
        )
        assert response.status_code == 500
        assert response.headers["cache-control"] == "private, no-store"
        assert db_session.query(models.Movie).count() == 0
        assert db_session.query(models.Book).count() == 0
        retained = db_session.query(models.Music).one()
        assert (retained.rating, retained.listened, retained.review) == (9.5, True, "Private")

    def test_apply_rechecks_duplicates_added_after_preview(self, authenticated_client, db_session):
        content = "title,artist,year,rating,listened,review\nBlue,Joni Mitchell,1971,8,true,CSV note\n"
        options = {"source": "generic", "category": "music"}
        preview = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("music.csv", content), data=options,
        ).json()
        assert preview["ready_count"] == 1
        db_session.add(models.Music(
            user_id=1, title="Blue", artist="Joni Mitchell", year=1971, rating=9.5,
            listened=True, review="Added while preview was open", review_public=True,
        ))
        db_session.commit()
        applied = authenticated_client.post(
            "/import-studio/apply/", files=csv_upload("music.csv", content),
            data={**options, "fingerprint_confirmation": preview["fingerprint"]},
        )
        assert applied.status_code == 200
        assert applied.json()["created_count"] == 0
        assert applied.json()["duplicate_count"] == 1
        retained = db_session.query(models.Music).one()
        assert retained.review == "Added while preview was open"
        assert retained.review_public is True
        assert retained.rating == 9.5

    def test_preview_uses_only_this_users_library_and_csv_candidate_values(self, authenticated_client, db_session):
        other = models.User(email="other@example.com", username="other", hashed_password="unused")
        db_session.add(other)
        db_session.flush()
        db_session.add(models.Book(user_id=other.id, title="Other library", author="Author", year=2020, review="Never expose this"))
        db_session.commit()
        response = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("books.csv", "title,author,year,review\nOther library,Author,2020,Uploaded note\n"),
            data={"source": "generic", "category": "books"},
        )
        assert response.status_code == 200
        assert response.json()["ready_count"] == 1
        assert response.json()["duplicate_count"] == 0
        assert response.json()["preview"][0]["values"]["review"] == "Uploaded note"
        assert "Never expose this" not in response.text


@pytest.mark.parametrize("category,completion", [
    ("movies", "watched"), ("tv-shows", "watched"), ("anime", "watched"),
    ("video-games", "played"), ("music", "listened"), ("books", "read"),
])
def test_generic_completion_columns_and_explicit_false_mapping(category, completion):
    content = f"title,{completion},Done\nA title,true,no\n".encode()
    _, rows = parse_csv(content, "generic", category)
    assert rows[0].data[completion] is True
    _, mapped = parse_csv(content, "generic", category, {"status": "Done"})
    assert mapped[0].data[completion] is False


def test_explicit_generic_mappings_override_aliases_and_preserve_original_columns():
    content = (
        "title,name,author,creator,rating,score,read,status,review,notes,year,Release,genre,Other genre\n"
        "Old title,Chosen title,Old author,Chosen author,9,0,yes,no,Old note,,1990,2020,Old genre,Chosen genre\n"
    ).encode()
    mapping = {
        "title": "name", "creator": "creator", "rating": "score", "status": "status",
        "review": "notes", "year": "Release", "genre": "Other genre",
    }
    _, rows = parse_csv(content, "generic", "books", mapping)
    data = rows[0].data
    assert (data["title"], data["author"], data["rating"], data["read"], data["review"], data["year"], data["genre"]) == (
        "Chosen title", "Chosen author", 0, False, None, 2020, "Chosen genre",
    )
    # Swapping canonical fields must not make mapping order change their source.
    for swapped in ({"title": "author", "creator": "title"}, {"creator": "title", "title": "author"}):
        _, swapped_rows = parse_csv(content, "generic", "books", swapped)
        assert (swapped_rows[0].data["title"], swapped_rows[0].data["author"]) == ("Old author", "Old title")


def test_source_adapter_existing_title_mapping_remains_supported():
    _, rows = parse_csv(
        b"Title,Author,Exclusive Shelf,Alternative\nOriginal,Writer,read,Chosen title\n",
        "auto", column_mapping={"title": "Alternative"},
    )
    assert rows[0].data["title"] == "Chosen title"
    assert rows[0].data["read"] is True


def test_mapped_blank_game_release_date_does_not_fall_back_to_year():
    _, rows = parse_csv(b"title,year,Optional date\nGame,2020,\n", "generic", "video-games", {"release_date": "Optional date"})
    assert rows[0].data["release_date"] is None
    _, rows = parse_csv(b"title,Released\nGame,2020\n", "generic", "video-games", {"year": "Released"})
    assert rows[0].data["release_date"].date().isoformat() == "2020-01-01"


def test_mixed_category_completion_uses_the_relevant_column():
    _, rows = parse_csv(
        b"title,category,watched,read,played,listened\nAlbum,music,false,false,false,true\nBook,books,false,true,false,false\nGame,video-games,false,false,true,false\n",
        "generic",
    )
    assert rows[0].data["listened"] is True
    assert rows[1].data["read"] is True
    assert rows[2].data["played"] is True


def test_game_does_not_validate_an_unused_year_when_release_date_is_supplied():
    _, rows = parse_csv(b"title,year,release_date\nGame,unknown,2020-09-17\n", "generic", "video-games")
    assert rows[0].error is None
    assert rows[0].data["release_date"].date().isoformat() == "2020-09-17"


@pytest.mark.parametrize("category,field,value,reason", [
    ("movies", "rating", "NaN", "Rating"), ("movies", "rating", "infinity", "Rating"),
    ("movies", "rating", "11", "Rating"), ("movies", "rating", "great", "Rating"),
    ("movies", "year", "-1", "Year"), ("movies", "year", "no idea", "Year"),
    ("tv-shows", "seasons", "1.5", "Seasons"), ("anime", "episodes", "-4", "Episodes"),
    ("video-games", "release_date", "2024-99-99", "Release date"),
])
def test_invalid_values_name_the_field_instead_of_silently_changing_it(category, field, value, reason):
    _, rows = parse_csv(f"title,{field}\nAn entry,{value}\n".encode(), "generic", category)
    assert rows[0].data is None
    assert reason in rows[0].error


def test_blank_numeric_fields_remain_optional_and_zero_rating_is_preserved():
    _, rows = parse_csv(b"title,year,rating,seasons,episodes\nUnrated,,,,\nZero rating,,0,,\n", "generic", "tv-shows")
    assert rows[0].data["year"] == 0
    assert rows[0].data["rating"] is None
    assert rows[0].data["seasons"] is None
    assert rows[0].data["episodes"] is None
    assert rows[1].data["rating"] == 0


def test_missing_mapped_column_is_reported_instead_of_importing_empty_values():
    with pytest.raises(ValueError, match="Mapped CSV columns were not found"):
        parse_csv(b"title\nArrival\n", "generic", "movies", {"rating": "Absent score"})


def test_public_guide_examples_produce_the_documented_outcomes(db_session):
    class Examples(HTMLParser):
        def __init__(self):
            super().__init__()
            self.current = None
            self.samples = {}

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "pre" and attributes.get("class") == "csv-example":
                self.current = attributes["aria-label"]
                self.samples[self.current] = ""

        def handle_data(self, data):
            if self.current:
                self.samples[self.current] += data

        def handle_endtag(self, tag):
            if tag == "pre":
                self.current = None

    examples = Examples()
    examples.feed((Path(__file__).resolve().parents[1] / "app/templates/export_import_guide.html").read_text(encoding="utf-8"))
    _, music = parse_csv(examples.samples["Music CSV example"].encode(), "generic", "music")
    assert [row.error for row in music] == [None, None]
    assert [(row.data["listened"], row.data["rating"]) for row in music] == [(True, 8.5), (False, None)]
    assert music[0].data["review"] == "Quiet rhythms, best with headphones."
    _, books = parse_csv(examples.samples["Books CSV example"].encode(), "generic", "books")
    classified = classify_rows(db_session, 1, books)
    statuses = [row["status"] for row in classified]
    assert statuses.count("ready") == 3
    assert statuses.count("duplicate") == 1
    assert statuses.count("invalid") == 1
    assert 0 in [row.data["rating"] for row in books if row.data]
    assert None in [row.data["rating"] for row in books if row.data]
