import gzip
import io
import json
import zipfile

import pytest

from app import models
from app.import_studio import parse_csv


LB_WATCHED = (
    "Date,Name,Year,Letterboxd URI\n"
    "2024-01-01,Arrival,2016,https://boxd.it/a\n"
    "2024-02-01,Heat,1995,https://boxd.it/b\n"
)
LB_DIARY = (
    "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
    "2024-01-01,Arrival,2016,https://boxd.it/x1,3,No,,2024-01-01\n"
    "2024-06-01,Arrival,2016,https://boxd.it/x2,4.5,Yes,,2024-06-01\n"
)
LB_RATINGS = (
    "Date,Name,Year,Letterboxd URI,Rating\n"
    "2024-06-01,Arrival,2016,https://boxd.it/a,5\n"
)
LB_REVIEWS = (
    "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Review,Tags,Watched Date\n"
    "2024-02-01,Heat,1995,https://boxd.it/r1,4,No,The diner scene.,,2024-02-01\n"
)
LB_WATCHLIST = (
    "Date,Name,Year,Letterboxd URI\n"
    "2024-03-01,Past Lives,2023,https://boxd.it/c\n"
    "2024-03-02,Heat,1995,https://boxd.it/b\n"
)
LB_DELETED_DIARY = (
    "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags,Watched Date\n"
    "2024-01-01,Removed Film,2001,https://boxd.it/d,1,No,,2024-01-01\n"
)

MAL_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<myanimelist>
  <myinfo><user_name>someone</user_name><user_export_type>1</user_export_type></myinfo>
  <anime>
    <series_animedb_id>1</series_animedb_id>
    <series_title><![CDATA[Cowboy Bebop]]></series_title>
    <series_type>TV</series_type>
    <series_episodes>26</series_episodes>
    <my_score>9</my_score>
    <my_status>Completed</my_status>
    <my_comments><![CDATA[See you, space cowboy.]]></my_comments>
  </anime>
  <anime>
    <series_title><![CDATA[Frieren]]></series_title>
    <series_episodes>28</series_episodes>
    <my_score>0</my_score>
    <my_status>Plan to Watch</my_status>
  </anime>
  <manga>
    <manga_title><![CDATA[Berserk]]></manga_title>
    <my_score>10</my_score>
    <my_status>Reading</my_status>
  </manga>
</myanimelist>
"""

TRAKT_WATCHED_MOVIES = [
    {"plays": 2, "last_watched_at": "2024-01-01T00:00:00.000Z",
     "movie": {"title": "Blade Runner", "year": 1982, "ids": {"trakt": 1}}},
]
TRAKT_WATCHED_SHOWS = [
    {"plays": 3, "show": {"title": "Severance", "year": 2022, "aired_episodes": 2},
     "seasons": [{"number": 1, "episodes": [{"number": 1}, {"number": 2}]}]},
    {"plays": 1, "show": {"title": "The Wire", "year": 2002, "aired_episodes": 60},
     "seasons": [{"number": 1, "episodes": [{"number": 1}]}]},
]
TRAKT_RATINGS = [
    {"rated_at": "2024-01-02T00:00:00.000Z", "rating": 9, "type": "movie",
     "movie": {"title": "Blade Runner", "year": 1982}},
    {"rated_at": "2024-01-02T00:00:00.000Z", "rating": 10, "type": "episode",
     "episode": {"title": "Pilot"}, "show": {"title": "Severance", "year": 2022}},
]
TRAKT_WATCHLIST = [
    {"listed_at": "2024-01-03T00:00:00.000Z", "type": "movie", "movie": {"title": "Dune", "year": 2021}},
]
TRAKT_CUSTOM_LIST = [
    {"listed_at": "2024-01-03T00:00:00.000Z", "type": "movie", "movie": {"title": "Cats", "year": 2019}},
]

ANILIST = {
    "source": "anilist", "user": "someone",
    "anime": {"lists": [{"name": "Completed", "entries": [
        {"status": "COMPLETED", "score": 8.5, "notes": "Rewatch every winter",
         "media": {"id": 1, "title": {"english": "Attack on Titan", "romaji": "Shingeki no Kyojin"},
                   "startDate": {"year": 2013}, "episodes": 25, "format": "TV"}},
        {"status": "PLANNING", "score": 0,
         "media": {"id": 2, "title": {"english": None, "romaji": "Mushishi"},
                   "startDate": {"year": 2005}, "episodes": 26, "format": "TV"}},
    ]}, {"name": "Custom", "entries": [
        {"status": "COMPLETED", "score": 8.5,
         "media": {"id": 1, "title": {"english": "Attack on Titan"}, "startDate": {"year": 2013}}},
    ]}]},
    "manga": {"lists": [{"entries": [
        {"status": "REPEATING", "score": 9,
         "media": {"id": 3, "title": {"english": "Vagabond"}, "startDate": {"year": 1998}, "format": "MANGA"}},
    ]}]},
}


def build_zip(files):
    # A fixed timestamp keeps the bytes identical between calls; writestr(name) stamps the
    # current time, so a preview and an apply built a second apart got different fingerprints.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in files.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=(2024, 1, 1, 0, 0, 0)), text)
    return buffer.getvalue()


def letterboxd_zip():
    return build_zip({
        "watched.csv": LB_WATCHED, "diary.csv": LB_DIARY, "ratings.csv": LB_RATINGS,
        "reviews.csv": LB_REVIEWS, "watchlist.csv": LB_WATCHLIST, "profile.csv": "Username\nsomeone\n",
        "deleted/diary.csv": LB_DELETED_DIARY, "lists/favourites.csv": "Letterboxd list export v7\n",
    })


def by_title(rows):
    return {row.title: row for row in rows}


def test_letterboxd_zip_merges_its_files_into_one_entry_per_film():
    source, rows = parse_csv(letterboxd_zip(), filename="letterboxd-someone-2024.zip")
    assert source == "letterboxd"
    films = by_title(rows)
    assert set(films) == {"Arrival", "Heat", "Past Lives"}
    # ratings.csv holds the current rating and wins over older diary ratings.
    assert films["Arrival"].data["rating"] == 10
    assert films["Arrival"].data["watched"] is True
    assert films["Heat"].data["review"] == "The diner scene."
    assert films["Heat"].data["review_public"] is False
    assert films["Heat"].data["watched"] is True
    assert films["Past Lives"].data["watched"] is False
    assert all(row.category == "movies" and row.error is None for row in rows)


def test_letterboxd_watchlist_csv_on_its_own_stays_unwatched():
    _, rows = parse_csv(LB_WATCHLIST.encode(), filename="watchlist.csv")
    assert [row.data["watched"] for row in rows] == [False, False]
    _, rows = parse_csv(LB_WATCHED.encode(), filename="watched.csv")
    assert [row.data["watched"] for row in rows] == [True, True]


def test_mal_xml_and_gzip_become_anime_and_books():
    for content, name in ((MAL_XML.encode(), "animelist.xml"), (gzip.compress(MAL_XML.encode()), "animelist_1.xml.gz")):
        source, rows = parse_csv(content, filename=name)
        assert source == "myanimelist"
        items = by_title(rows)
        assert items["Cowboy Bebop"].category == "anime"
        assert items["Cowboy Bebop"].data["rating"] == 9
        assert items["Cowboy Bebop"].data["episodes"] == 26
        assert items["Cowboy Bebop"].data["watched"] is True
        assert items["Cowboy Bebop"].data["review"] == "See you, space cowboy."
        assert items["Frieren"].data["rating"] is None
        assert items["Frieren"].data["watched"] is False
        assert items["Berserk"].category == "manga"
        assert items["Berserk"].data["read"] is False


def test_xml_with_entity_declarations_is_refused():
    hostile = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><myanimelist></myanimelist>'
    with pytest.raises(ValueError, match="document type"):
        parse_csv(hostile.encode(), filename="list.xml")


def test_entity_declarations_after_a_long_comment_are_refused_too():
    padded = ('<?xml version="1.0"?><!--' + "x" * 10000 + '--><!DOCTYPE myanimelist [<!ENTITY a "aaaa">]>'
              "<myanimelist><anime><series_title>&a;</series_title></anime></myanimelist>")
    with pytest.raises(ValueError, match="document type"):
        parse_csv(padded.encode(), filename="list.xml")


def test_trakt_export_zip_reads_history_ratings_and_watchlist_only():
    content = build_zip({
        "watched-movies.json": json.dumps(TRAKT_WATCHED_MOVIES),
        "watched-shows.json": json.dumps(TRAKT_WATCHED_SHOWS),
        "ratings-movies.json": json.dumps(TRAKT_RATINGS),
        "watchlist-movies.json": json.dumps(TRAKT_WATCHLIST),
        "lists-avoid.json": json.dumps(TRAKT_CUSTOM_LIST),
        "collection-movies.json": json.dumps([{"collected_at": "x", "movie": {"title": "Owned", "year": 2000}}]),
        "user-profile.json": json.dumps({"username": "someone"}),
    })
    source, rows = parse_csv(content, filename="trakt-export.zip")
    assert source == "trakt"
    items = by_title(rows)
    assert set(items) == {"Blade Runner", "Severance", "The Wire", "Dune"}
    assert items["Blade Runner"].data["rating"] == 9
    assert items["Blade Runner"].data["watched"] is True
    # Every aired episode seen marks a show watched; a partial one stays in progress.
    assert items["Severance"].category == "tv-shows"
    assert items["Severance"].data["watched"] is True
    assert items["Severance"].data["rating"] is None
    assert items["The Wire"].data["watched"] is False
    assert items["Dune"].data["watched"] is False


def test_single_trakt_json_file_is_read():
    source, rows = parse_csv(json.dumps(TRAKT_WATCHLIST).encode(), filename="watchlist-movies.json")
    assert source == "trakt"
    assert [(row.title, row.data["watched"]) for row in rows] == [("Dune", False)]


def test_anilist_lists_become_anime_and_books_once_each():
    source, rows = parse_csv(json.dumps(ANILIST).encode(), filename="anilist-someone.json")
    assert source == "anilist"
    items = by_title(rows)
    assert set(items) == {"Attack on Titan", "Mushishi", "Vagabond"}
    assert items["Attack on Titan"].data["rating"] == 8.5
    assert items["Attack on Titan"].data["year"] == 2013
    assert items["Attack on Titan"].data["watched"] is True
    assert items["Mushishi"].data["watched"] is False
    assert items["Vagabond"].category == "manga"
    assert items["Vagabond"].data["read"] is True


def test_a_chosen_source_that_does_not_match_the_file_is_explained():
    with pytest.raises(ValueError, match="looks like a Letterboxd export"):
        parse_csv(letterboxd_zip(), "goodreads", filename="export.zip")
    with pytest.raises(ValueError, match="Letterboxd, Trakt or Spotify"):
        parse_csv(build_zip({"notes.csv": "a,b\n1,2\n"}), filename="other.zip")


def test_zip_upload_previews_and_applies_without_touching_existing_entries(authenticated_client, db_session):
    user_id = db_session.query(models.User).one().id
    db_session.add(models.Movie(user_id=user_id, title="Arrival", director="Denis Villeneuve", year=2016,
                                rating=6.0, watched=True, review="Mine"))
    db_session.add(models.Anime(user_id=user_id, title="Cowboy Bebop", year=1998, rating=7.0, watched=True))
    db_session.commit()
    files = {"file": ("letterboxd.zip", letterboxd_zip(), "application/zip")}
    preview = authenticated_client.post("/import-studio/preview/", files=files, data={"source": "auto"})
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["detected_source"] == "letterboxd"
    assert (data["ready_count"], data["duplicate_count"]) == (2, 1)

    applied = authenticated_client.post(
        "/import-studio/apply/", files={"file": ("letterboxd.zip", letterboxd_zip(), "application/zip")},
        data={"source": "auto", "fingerprint_confirmation": data["fingerprint"]},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["created_count"] == 2
    arrival = db_session.query(models.Movie).filter(models.Movie.title == "Arrival").one()
    assert (arrival.rating, arrival.review) == (6.0, "Mine")

    # MyAnimeList XML has no years, so a blank year matches the same title already tracked.
    xml = {"file": ("animelist.xml", MAL_XML.encode(), "text/xml")}
    preview = authenticated_client.post("/import-studio/preview/", files=xml, data={"source": "auto"}).json()
    assert preview["duplicate_count"] == 1
    assert preview["ready_count"] == 2


def test_renaming_a_file_requires_a_fresh_preview(authenticated_client):
    preview = authenticated_client.post(
        "/import-studio/preview/", files={"file": ("watched.csv", LB_WATCHLIST.encode(), "text/csv")}, data={"source": "auto"},
    ).json()
    applied = authenticated_client.post(
        "/import-studio/apply/", files={"file": ("watchlist.csv", LB_WATCHLIST.encode(), "text/csv")},
        data={"source": "auto", "fingerprint_confirmation": preview["fingerprint"]},
    )
    assert applied.status_code == 409


def test_unsupported_upload_types_are_refused(authenticated_client):
    response = authenticated_client.post(
        "/import-studio/preview/", files={"file": ("list.pdf", b"%PDF-1.4", "application/pdf")}, data={"source": "auto"},
    )
    assert response.status_code == 400
    assert "ZIP, XML, OPML or JSON" in response.json()["detail"]
