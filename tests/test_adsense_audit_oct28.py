"""Oct 28, 2026 AdSense pass over the pages added Oct 25-28 (people pages, discussions,
group polls, manga and podcasts).

- "Various", "Unknown" and similar fill-ins are not people: no page, no link, no sitemap entry.
- Sign-in links on indexable pages carry rel="nofollow", like the rest of the site.
- Public copy and the privacy policy cover all eight media types and the new public features.
"""
import re

from app import models, people_pages
from tests.test_people_pages import REVIEW, facts, member, movie, nolan_library


def various_library(db):
    users = [member(db, f"v{i}") for i in range(4)]
    for user in users:
        for title, year in (("Blue", 1971), ("Kid A", 2000), ("Rumours", 1977)):
            db.add(models.Music(user_id=user.id, title=title, artist="Various Artists", year=year, rating=8.0,
                                review=REVIEW, review_public=True))
        for title, year in (("Heat", 1995), ("Collateral", 2004), ("Thief", 1981)):
            movie(db, user, title, year, director="Unknown", rating=8.0, review=REVIEW, review_public=True)
    db.commit()


def test_placeholder_names_are_not_people():
    for name in ("Various", "Various Artists", "Unknown", "N/A", "none", "TBA", "Title", "?", "  "):
        assert not people_pages.is_real_name(name), name
    for name in ("Christopher Nolan", "Na Hong-jin", "Madhouse", "Unknown Mortal Orchestra"):
        assert people_pages.is_real_name(name), name
    assert people_pages.split_names("Various, Hayao Miyazaki", "Director") == ["Hayao Miyazaki"]


def test_placeholder_names_get_no_page_link_or_sitemap_entry(client, db_session):
    various_library(db_session)
    facts(db_session, "album:blue:1971", ("Artist", "Various Artists"))
    facts(db_session, "album:kid a:2000", ("Artist", "Various Artists"))
    assert client.get("/people/various-artists").status_code == 404
    assert client.get("/people/unknown").status_code == 404
    assert "/people/various-artists" not in client.get("/people").text
    assert "/people/unknown" not in client.get("/people").text
    assert "/people/" not in client.get("/titles/movie/heat-1995").text
    album = client.get("/titles/album/blue-1971")
    assert album.status_code == 200 and "/people/" not in album.text
    sitemap = client.get("/sitemap.xml").text
    assert "/people/various" not in sitemap and "/people/unknown" not in sitemap


def test_credits_indexed_before_the_list_stay_out_of_directories(client, db_session):
    nolan_library(db_session)
    for key in ("movie:interstellar:2014", "movie:the prestige:2006"):
        db_session.add(models.TitleCredit(metadata_key=key, kind="movie", entity="person", role="Cast",
                                          name="Various", slug="various"))
    db_session.commit()
    assert "/people/various" not in client.get("/people").text
    assert "/people/various" not in client.get("/people/christopher-nolan").text
    assert client.get("/people/various").status_code == 404


def _signin_anchors(html):
    return [a for a in re.findall(r"<a\b[^>]*>", html) if 'href="/?' in a]


def test_signin_links_on_title_discussion_and_poll_pages_are_nofollow(client, db_session):
    nolan_library(db_session)
    for path in ("/titles/movie/interstellar-2014", "/titles/movie/interstellar-2014/discussions", "/tonight"):
        anchors = _signin_anchors(client.get(path).text)
        assert anchors, path
        assert all('rel="nofollow"' in a for a in anchors), (path, anchors)


def test_public_copy_names_manga_and_podcasts(client):
    for path in ("/", "/about", "/faq", "/use-cases", "/guides"):
        html = client.get(path).text
        assert "manga" in html and "podcasts" in html, path
    assert "music, and books" not in client.get("/about").text


def test_privacy_policy_covers_the_new_public_features(client):
    html = client.get("/privacy").text
    assert "<strong>Manga:</strong>" in html and "<strong>Podcasts:</strong>" in html
    assert "<strong>Title discussions:</strong>" in html and "<strong>Group polls:</strong>" in html
    assert "may appear in search results" in html
    assert "Last Updated: October 28, 2026" in html
