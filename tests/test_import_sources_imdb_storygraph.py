from app import models
from app.import_studio import parse_csv


IMDB_RATINGS = (
    "Const,Your Rating,Date Rated,Title,Original Title,URL,Title Type,IMDb Rating,Runtime (mins),Year,Genres,Num Votes,Release Date,Directors\n"
    "tt0111161,9,2025-01-02,The Shawshank Redemption,The Shawshank Redemption,https://www.imdb.com/title/tt0111161/,Movie,9.3,142,1994,Drama,3000000,1994-10-14,Frank Darabont\n"
    'tt0903747,10,2025-01-03,Breaking Bad,Breaking Bad,https://www.imdb.com/title/tt0903747/,TV Series,9.5,49,2008,"Crime, Drama",2000000,2008-01-20,\n'
    "tt0959621,8,2025-01-03,Pilot,Pilot,https://www.imdb.com/title/tt0959621/,TV Episode,9.0,58,2008,Drama,1,2008-01-20,Vince Gilligan\n"
    'tt5838588,9,2025-01-04,God of War,God of War,https://www.imdb.com/title/tt5838588/,Video Game,9.3,,2018,"Action, Adventure",1,2018-04-20,Cory Barlog\n'
    "tt0000001,7,2025-01-04,A Podcast,A Podcast,https://www.imdb.com/title/tt0000001/,Podcast Series,9,,2018,,1,,\n"
)

IMDB_WATCHLIST = (
    "Position,Const,Created,Modified,Description,Title,Original Title,URL,Title Type,IMDb Rating,Runtime (mins),Year,Genres,Num Votes,Release Date,Directors,Your Rating,Date Rated\n"
    "1,tt15239678,2025-02-01,2025-02-01,Sam says see it big,Dune: Part Two,Dune: Part Two,https://www.imdb.com/title/tt15239678/,Movie,8.5,166,2024,Sci-Fi,600000,2024-03-01,Denis Villeneuve,,\n"
    "2,tt2560140,2025-02-01,2025-02-01,,Attack on Titan,Shingeki no Kyojin,https://www.imdb.com/title/tt2560140/,tvSeries,9.1,24,2013,Animation,500000,2013-09-28,,,\n"
    "3,tt0111161,2025-02-01,2025-02-01,,The Shawshank Redemption,The Shawshank Redemption,https://www.imdb.com/title/tt0111161/,Movie,9.3,142,1994,Drama,3000000,1994-10-14,Frank Darabont,9,2025-01-02\n"
)

STORYGRAPH = (
    "Title,Authors,Contributors,ISBN/UID,Format,Read Status,Date Added,Last Date Read,Dates Read,Read Count,Moods,Pace,"
    "Character- or Plot-Driven?,Strong Character Development?,Loveable Characters?,Diverse Characters?,Flawed Characters?,"
    "Star Rating,Review,Content Warnings,Content Warning Description,Tags,Owned?\n"
    "Piranesi,Susanna Clarke,,9781635575996,paperback,read,2025/01/01,2025/02/01,2025/01/05-2025/02/01,1,mysterious,medium,"
    "Plot,Yes,Yes,No,Yes,4.25,Quietly astonishing,,,,No\n"
    "Dune,Frank Herbert,,9780441172719,digital,to-read,2025/01/01,,,0,,,,,,,,,,,,,No\n"
    "The Overstory,Richard Powers,,9780393635522,hardcover,did-not-finish,2025/01/01,,,0,,,,,,,,2.5,,,,,No\n"
)


def upload(name, content):
    return {"file": (name, content.encode("utf-8"), "text/csv")}


def test_imdb_ratings_are_detected_and_routed_by_title_type():
    source, rows = parse_csv(IMDB_RATINGS.encode())
    assert source == "imdb"
    movie, show, episode, game, podcast = rows
    assert movie.category == "movies"
    assert movie.data["director"] == "Frank Darabont"
    assert movie.data["year"] == 1994
    assert movie.data["rating"] == 9
    assert movie.data["watched"] is True
    assert show.category == "tv-shows" and show.data["year"] == 2008 and show.data["watched"] is True
    assert episode.category is None and "episode" in episode.error.lower()
    assert game.category == "video-games"
    assert game.data["release_date"].date().isoformat() == "2018-04-20"
    assert game.data["genres"] == "Action, Adventure"
    assert game.data["played"] is True
    assert podcast.category is None and "podcast" in podcast.error.lower()


def test_imdb_watchlist_rows_without_a_rating_stay_unfinished_and_keep_list_notes():
    source, rows = parse_csv(IMDB_WATCHLIST.encode())
    assert source == "imdb"
    dune, titan, shawshank = rows
    assert dune.data["watched"] is False and dune.data["rating"] is None
    assert dune.data["review"] == "Sam says see it big"
    assert dune.data["review_public"] is False
    # Older exports use camelCase title types.
    assert titan.category == "tv-shows" and titan.data["watched"] is False
    assert shawshank.data["watched"] is True and shawshank.data["rating"] == 9


def test_unknown_imdb_title_type_is_reported_not_guessed():
    content = "Const,Your Rating,Title,Title Type,Year\ntt1,7,Strange Thing,Hologram,2020\n"
    _, rows = parse_csv(content.encode(), "imdb")
    assert rows[0].category is None
    assert "Hologram" in rows[0].error


def test_storygraph_export_is_detected_with_quarter_star_ratings():
    source, rows = parse_csv(STORYGRAPH.encode())
    assert source == "storygraph"
    piranesi, dune, overstory = rows
    assert piranesi.category == "books"
    assert piranesi.data["author"] == "Susanna Clarke"
    assert piranesi.data["rating"] == 8.5
    assert piranesi.data["read"] is True
    assert piranesi.data["review"] == "Quietly astonishing"
    assert piranesi.data["review_public"] is False
    assert dune.data["read"] is False and dune.data["rating"] is None
    assert overstory.data["read"] is False and overstory.data["rating"] == 5


def test_existing_formats_are_still_detected_the_same_way():
    goodreads = "Title,Author,My Rating,Year Published,Exclusive Shelf\nPiranesi,Susanna Clarke,5,2020,read\n"
    letterboxd = "Date,Name,Year,Letterboxd URI,Rating\n2025-01-01,Heat,1995,https://boxd.it/x,4.5\n"
    watchlist = "Position,Name,Year,URL\n1,Heat,1995,https://boxd.it/x\n"
    assert parse_csv(goodreads.encode())[0] == "goodreads"
    assert parse_csv(letterboxd.encode())[0] == "letterboxd"
    assert parse_csv(watchlist.encode())[0] == "letterboxd"


def test_imdb_import_is_additive_and_skips_titles_already_tracked(authenticated_client, db_session):
    first = authenticated_client.post("/import-studio/preview/", files=upload("ratings.csv", IMDB_RATINGS), data={"source": "auto"}).json()
    assert first["detected_source"] == "imdb"
    assert first["ready_count"] == 3 and first["invalid_count"] == 2
    applied = authenticated_client.post(
        "/import-studio/apply/", files=upload("ratings.csv", IMDB_RATINGS),
        data={"source": "auto", "fingerprint_confirmation": first["fingerprint"]},
    )
    assert applied.status_code == 200
    assert applied.json()["by_category"] == {"movies": 1, "tv-shows": 1, "anime": 0, "video-games": 1, "music": 0, "books": 0, "manga": 0}

    second = authenticated_client.post("/import-studio/preview/", files=upload("watchlist.csv", IMDB_WATCHLIST), data={"source": "auto"}).json()
    assert second["ready_count"] == 2 and second["duplicate_count"] == 1
    authenticated_client.post(
        "/import-studio/apply/", files=upload("watchlist.csv", IMDB_WATCHLIST),
        data={"source": "auto", "fingerprint_confirmation": second["fingerprint"]},
    )
    shawshank = db_session.query(models.Movie).filter_by(title="The Shawshank Redemption").one()
    assert shawshank.rating == 9 and shawshank.watched is True
    assert db_session.query(models.Movie).count() == 2
    assert db_session.query(models.TVShow).count() == 2


def test_storygraph_import_creates_private_books(authenticated_client, db_session):
    preview = authenticated_client.post("/import-studio/preview/", files=upload("storygraph.csv", STORYGRAPH), data={"source": "storygraph"}).json()
    assert preview["ready_count"] == 3
    authenticated_client.post(
        "/import-studio/apply/", files=upload("storygraph.csv", STORYGRAPH),
        data={"source": "storygraph", "fingerprint_confirmation": preview["fingerprint"]},
    )
    books = {book.title: book for book in db_session.query(models.Book).all()}
    assert books["Piranesi"].read is True and books["Piranesi"].rating == 8.5
    assert all(book.review_public is False for book in books.values())


def test_dashboard_offers_the_new_formats(authenticated_client):
    page = authenticated_client.get("/").text
    assert '<option value="imdb">' in page
    assert '<option value="storygraph">' in page


def test_switch_guide_is_public_indexable_and_linked(client):
    response = client.get("/switch")
    assert response.status_code == 200
    assert "X-Robots-Tag" not in response.headers
    for name in ("IMDb", "Letterboxd", "Goodreads", "StoryGraph", "MyAnimeList", "Title Type", "4.25 becomes 8.5/10"):
        assert name in response.text
    assert 'href="/switch"' in client.get("/export-import-guide").text
    assert 'href="/switch"' in client.get("/compare").text
    assert "There is no dedicated IMDb" not in client.get("/compare").text
    assert "/switch</loc>" in client.get("/sitemap.xml").text
