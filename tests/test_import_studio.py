from app import models


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
            "title,category,creator,year,release_date,rating,status,genre,seasons,episodes\n"
            "Arrival,movie,Denis Villeneuve,2016,,9,watched,Science Fiction,,\n"
            "Severance,tv show,,2022,,9,completed,Drama,2,19\n"
            "Cowboy Bebop,anime,,1998,,10,completed,Science Fiction,1,26\n"
            "Hades,video game,,2020,2020-09-17,9.5,played,Roguelike,,\n"
            "Blue,music,Joni Mitchell,1971,,10,listened,Folk,,\n"
            "Beloved,book,Toni Morrison,1987,,10,read,Fiction,,\n"
        )
        preview = authenticated_client.post(
            "/import-studio/preview/", files=csv_upload("all-media.csv", content), data={"source": "generic"}
        ).json()
        assert preview["ready_count"] == 6
        assert all(preview["by_category"][category] == 1 for category in (
            "movies", "tv-shows", "anime", "video-games", "music", "books"
        ))
        applied = authenticated_client.post(
            "/import-studio/apply/", files=csv_upload("all-media.csv", content),
            data={"source": "generic", "fingerprint_confirmation": preview["fingerprint"]},
        )
        assert applied.status_code == 200
        assert applied.json()["created_count"] == 6
        assert db_session.query(models.Movie).count() == 1
        assert db_session.query(models.TVShow).count() == 1
        assert db_session.query(models.Anime).count() == 1
        assert db_session.query(models.VideoGame).count() == 1
        assert db_session.query(models.Music).count() == 1
        assert db_session.query(models.Book).count() == 1

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
