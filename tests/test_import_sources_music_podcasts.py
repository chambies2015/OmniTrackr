"""Spotify, podcast app OPML, Rate Your Music and Libib imports (October 31, 2026)."""
import io
import json
import zipfile

import pytest

from app import models
from app.import_studio import parse_csv


SPOTIFY_LIBRARY = {
    "tracks": [
        {"artist": "Radiohead", "album": "In Rainbows", "track": "Reckoner", "uri": "spotify:track:1"},
        {"artist": "Radiohead", "album": "In Rainbows", "track": "Nude", "uri": "spotify:track:2"},
        {"artist": "Radiohead", "album": "In Rainbows", "track": "Weird Fishes/Arpeggi", "uri": "spotify:track:3"},
        {"artist": "Carly Rae Jepsen", "album": "E·MO·TION", "track": "Run Away With Me", "uri": "spotify:track:4"},
    ],
    "albums": [
        {"artist": "Kendrick Lamar", "album": "To Pimp a Butterfly", "uri": "spotify:album:1"},
        {"artist": "Radiohead", "album": "In Rainbows", "uri": "spotify:album:2"},
    ],
    "shows": [
        {"name": "Song Exploder", "publisher": "Hrishikesh Hirway", "uri": "spotify:show:1"},
        {"name": "Song Exploder", "publisher": "Hrishikesh Hirway", "uri": "spotify:show:1"},
    ],
    "episodes": [{"name": "Episode 1", "show": "Song Exploder", "uri": "spotify:episode:1"}],
    "bannedTracks": [], "artists": [], "bannedArtists": [], "other": [],
}

OPML = """<?xml version="1.0" encoding="utf-8"?>
<opml version="1.0">
  <head><title>Pocket Casts Feeds</title></head>
  <body>
    <outline text="feeds">
      <outline type="rss" text="99% Invisible" xmlUrl="https://feeds.simplecast.com/BqbsxVfO" />
      <outline type="rss" text="Radiolab" title="Radiolab" xmlUrl="https://feeds.feedburner.com/radiolab" />
      <outline type="rss" text="Radiolab" xmlUrl="https://example.com/radiolab-mirror" />
      <outline text="A folder with no feed" />
    </outline>
  </body>
</opml>
"""

OVERCAST_OPML = """<?xml version="1.0" encoding="utf-8"?>
<opml version="1.0">
  <body>
    <outline text="feeds">
      <outline type="rss" text="The Memory Palace" title="The Memory Palace" xmlUrl="https://example.com/mp.xml">
        <outline type="podcast-episode" title="Episode one" url="https://example.com/1" played="1" />
      </outline>
    </outline>
  </body>
</opml>
"""

RYM = (
    "RYM Album, First Name,Last Name,First Name localized, Last Name localized,Title,Release_Date,Rating,Ownership,Purchase Date,Media Type,Review\n"
    '"1","","Radiohead","","","OK Computer","1997","10","n","","",""\n'
    '"2","Kate","Bush","","","Hounds of Love","1985","0","o","","CD","Side two is a whole film."\n'
    '"3","","Simon &amp; Garfunkel","","","Bookends","1968","0","w","","",""\n'
    '"4","","Boards of Canada","","","Music Has the Right to Children","1998","7","n","","",""\n'
)

LIBIB = (
    "item_type,title,creators,first_name,last_name,ean_isbn13,upc_isbn10,description,publisher,publish_date,group,tags,"
    "notes,price,length,number_of_discs,number_of_players,age_group,ensemble,aspect_ratio,esrb,rating,review,review_date,"
    "status,began,completed,added,copies\n"
    'book,The Left Hand of Darkness,"Ursula K. Le Guin",Ursula K.,Le Guin,9780441478125,,,Ace,1969-03-01,,,,,,,,,,,,4,Still the best ice walk.,,Completed,,2025-01-03,2025-01-01,1\n'
    'book,Middlemarch,George Eliot,George,Eliot,9780141439549,,,Penguin,1871,,,,,,,,,,,,0,,,Not begun,,,2025-01-01,1\n'
    'movie,Spirited Away,"Rumi Hiiragi, Miyu Irino",,,,786936223631,,,2002-09-20,,,,,,,,,,,,5,,,Completed,,,2025-01-01,1\n'
    'videogame,Hades,Supergiant Games,,,,,,,2020-09-17,,,,,,,,,,,,,,,In progress,,,2025-01-01,1\n'
    'music,Blue,Joni Mitchell,Joni,Mitchell,,075992719920,,,June 1971,,,,,,,,,,,,,,,,,,2025-01-01,1\n'
    'board game,Catan,,,,,,,,,,,,,,,,,,,,,,,,,,2025-01-01,1\n'
)


def build_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=(2024, 1, 1, 0, 0, 0)), data)
    return buffer.getvalue()


def spotify_zip():
    return build_zip({
        "Spotify Account Data/YourLibrary.json": json.dumps(SPOTIFY_LIBRARY),
        "Spotify Account Data/StreamingHistory_music_0.json": json.dumps(
            [{"endTime": "2024-01-01 10:00", "artistName": "Radiohead", "trackName": "Nude", "msPlayed": 1000}]),
        "Spotify Account Data/Playlist1.json": json.dumps({"playlists": []}),
    })


def by_title(rows):
    return {row.title: row for row in rows}


def test_spotify_library_json_brings_saved_albums_well_liked_albums_and_shows():
    source, rows = parse_csv(json.dumps(SPOTIFY_LIBRARY).encode(), filename="YourLibrary.json")
    assert source == "spotify"
    found = by_title(rows)
    # In Rainbows is both saved and has three liked songs: it appears once.
    assert set(found) == {"To Pimp a Butterfly", "In Rainbows", "Song Exploder"}
    album = found["In Rainbows"]
    assert album.category == "music"
    assert album.data["artist"] == "Radiohead"
    assert album.data["listened"] is True and album.data["rating"] is None
    show = found["Song Exploder"]
    assert show.category == "podcasts"
    assert show.data["host"] == "Hrishikesh Hirway"
    assert show.data["listened"] is False


def test_spotify_account_data_zip_is_read_as_downloaded():
    source, rows = parse_csv(spotify_zip(), filename="my_spotify_data.zip")
    assert source == "spotify"
    assert len(rows) == 3


def test_spotify_chosen_for_a_spreadsheet_explains_which_file_to_use():
    with pytest.raises(ValueError, match="YourLibrary.json"):
        parse_csv(b"title,artist\nBlue,Joni Mitchell\n", "spotify", filename="music.csv")


def test_opml_subscriptions_become_podcasts_once_each():
    source, rows = parse_csv(OPML.encode(), filename="podcasts_opml.xml")
    assert source == "opml"
    assert [row.title for row in rows] == ["99% Invisible", "Radiolab"]
    assert all(row.category == "podcasts" and row.data["listened"] is False for row in rows)


def test_overcast_extended_opml_skips_episode_outlines():
    source, rows = parse_csv(OVERCAST_OPML.encode(), filename="overcast.opml")
    assert source == "opml"
    assert [row.title for row in rows] == ["The Memory Palace"]


def test_opml_with_a_doctype_is_refused():
    hostile = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><opml><body/></opml>'
    with pytest.raises(ValueError, match="document type"):
        parse_csv(hostile.encode(), filename="feeds.opml")


def test_rate_your_music_export_keeps_ratings_out_of_ten():
    source, rows = parse_csv(RYM.encode(), filename="user_albums_export.csv")
    assert source == "rateyourmusic"
    ok, hounds, bookends, boc = rows
    assert (ok.data["title"], ok.data["artist"], ok.data["year"]) == ("OK Computer", "Radiohead", 1997)
    assert ok.data["rating"] == 10 and ok.data["listened"] is True
    assert hounds.data["artist"] == "Kate Bush"
    # Owned but unrated still counts as heard; the review stays private.
    assert hounds.data["rating"] is None and hounds.data["listened"] is True
    assert hounds.data["review"] == "Side two is a whole film." and hounds.data["review_public"] is False
    # The export escapes ampersands, and wishlist albums arrive unheard.
    assert bookends.data["artist"] == "Simon & Garfunkel"
    assert bookends.data["listened"] is False
    assert boc.data["rating"] == 7


def test_libib_export_routes_each_item_type_to_its_shelf():
    source, rows = parse_csv(LIBIB.encode(), filename="library_export.csv")
    assert source == "libib"
    left, middlemarch, spirited, hades, blue, catan = rows
    assert left.category == "books"
    assert (left.data["author"], left.data["year"], left.data["rating"], left.data["read"]) == ("Ursula K. Le Guin", 1969, 8, True)
    assert left.data["review"] == "Still the best ice walk."
    assert middlemarch.data["read"] is False and middlemarch.data["rating"] is None and middlemarch.data["year"] == 1871
    assert spirited.category == "movies"
    assert spirited.data["director"] == "Unknown director" and spirited.data["watched"] is True
    assert spirited.data["rating"] == 10 and spirited.data["year"] == 2002
    assert hades.category == "video-games" and hades.data["played"] is False
    assert hades.data["release_date"].year == 2020
    assert blue.category == "music" and blue.data["artist"] == "Joni Mitchell" and blue.data["year"] == 1971
    assert catan.category is None and "board game" in catan.error


def test_spotify_import_never_replaces_or_repeats_what_you_already_have(authenticated_client, db_session):
    user_id = db_session.query(models.User).one().id
    db_session.add(models.Music(user_id=user_id, title="In Rainbows", artist="Radiohead", year=2007,
                                rating=9.5, listened=True, review="Mine"))
    db_session.add(models.Podcast(user_id=user_id, title="Song Exploder", host="Hrishikesh Hirway", listened=True))
    db_session.commit()
    files = {"file": ("my_spotify_data.zip", spotify_zip(), "application/zip")}
    preview = authenticated_client.post("/import-studio/preview/", files=files, data={"source": "auto"})
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["detected_source"] == "spotify"
    assert (data["ready_count"], data["duplicate_count"]) == (1, 2)

    applied = authenticated_client.post(
        "/import-studio/apply/", files={"file": ("my_spotify_data.zip", spotify_zip(), "application/zip")},
        data={"source": "auto", "fingerprint_confirmation": data["fingerprint"]},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["created_count"] == 1
    kept = db_session.query(models.Music).filter(models.Music.title == "In Rainbows").one()
    assert (kept.rating, kept.review, kept.year) == (9.5, "Mine", 2007)
    assert db_session.query(models.Music).count() == 2
    assert db_session.query(models.Podcast).count() == 1

    # A second run finds nothing new.
    again = authenticated_client.post("/import-studio/preview/", files=files, data={"source": "auto"}).json()
    assert again["ready_count"] == 0


def test_opml_upload_is_accepted_by_extension(authenticated_client):
    files = {"file": ("subscriptions.opml", OPML.encode(), "text/x-opml")}
    preview = authenticated_client.post("/import-studio/preview/", files=files, data={"source": "opml"})
    assert preview.status_code == 200, preview.text
    assert preview.json()["detected_source"] == "opml"
    assert preview.json()["by_category"]["podcasts"] == 2


# ---------------------------------------------------------------------------
# "Switch from X" guides

import re  # noqa: E402

from app import switch_guides  # noqa: E402

SLUGS = sorted(switch_guides.GUIDES)


def _json_ld(html):
    return [json.loads(block) for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)]


@pytest.mark.parametrize("slug", SLUGS)
def test_each_switch_guide_is_a_complete_indexable_page(client, slug):
    response = client.get(f"/switch/{slug}")
    assert response.status_code == 200
    assert "X-Robots-Tag" not in response.headers
    html = response.text
    assert '<meta name="robots" content="index, follow' in html
    assert html.count(f'<link rel="canonical" href="https://omnitrackr.xyz/switch/{slug}">') == 1
    assert "{{" not in html
    # The shared reading layout: breadcrumbs through the hub, related cards, unique anchors.
    assert '<html lang="en" data-reader>' in html
    trail = next(item for item in _json_ld(html) if item.get("@type") == "BreadcrumbList")["itemListElement"]
    assert [item["item"] for item in trail][-2:] == ["https://omnitrackr.xyz/switch", f"https://omnitrackr.xyz/switch/{slug}"]
    assert html.count('class="reader-related__card"') == 3
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    for anchor in re.findall(r'href="#([^"]+)"', html):
        assert anchor in ids, anchor
    faq = next(item for item in _json_ld(html) if item.get("@type") == "FAQPage")
    assert len(faq["mainEntity"]) >= 3
    assert all("<" not in question["acceptedAnswer"]["text"] for question in faq["mainEntity"])
    # Enough of its own words to stand on its own.
    words = len(re.sub(r"<[^>]+>", " ", html[html.index('id="reader-main"'):html.index("</main>")]).split())
    assert words >= 600, words


def test_switch_guides_link_to_each_other_and_from_the_hub(client):
    hub = client.get("/switch").text
    sitemap = client.get("/sitemap.xml").text
    for slug in SLUGS:
        assert f'href="/switch/{slug}"' in hub
        assert f"/switch/{slug}</loc>" in sitemap
        for other in switch_guides.GUIDES[slug]["related"]:
            assert other in switch_guides.GUIDES
        # The hub anchor each guide links back to exists.
        assert f'id="{switch_guides.GUIDES[slug]["hub"]}"' in hub


def test_unknown_switch_guide_is_a_404(client):
    assert client.get("/switch/myspace").status_code == 404


def test_dashboard_offers_the_music_and_podcast_formats(authenticated_client):
    page = authenticated_client.get("/").text
    for value in ("spotify", "opml", "rateyourmusic", "libib"):
        assert f'<option value="{value}">' in page
    assert ".opml" in page
