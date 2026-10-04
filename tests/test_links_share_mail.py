"""Oct 4: title-page links from the library, one-tap sharing, and plain-text email parts."""
import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from app import email as email_utils, for_you, funnel, models, title_pages


def member(db, name, **extra):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True, **extra)
    db.add(user)
    db.flush()
    return user


def seed(db):
    for name in ("a1", "a2"):
        user = member(db, name)
        db.add(models.Movie(user_id=user.id, title="Arrival", director="Denis Villeneuve", year=2016, rating=9,
                            review=("Arrival is a quiet, patient film about language and grief. The heptapods are strange "
                                    "without being cartoonish and the structure rewards a rewatch. ") * 3,
                            review_public=True))
    db.commit()


# ---------------------------------------------------------------- links

def test_popular_picks_carry_their_title_page(db_session):
    seed(db_session)
    picks = for_you.popular_titles(db_session, "movies")
    assert picks and picks[0]["url"] == "/titles/movie/arrival-2016"


@pytest.mark.parametrize("title,year,expected", [
    ("Interstellar", "2014", "/titles/movie/interstellar-2014"),
    ("Pokémon: The First Movie", "1998", "/titles/movie/pokemon-the-first-movie-1998"),
    ("2001: A Space Odyssey", "", "/titles/movie/2001-a-space-odyssey"),
    ("!!!", "2000", "/titles/movie/title-2000"),
    ("Hades", "2020-09-17", "/titles/movie/hades-2020"),
])
def test_dashboard_links_use_the_same_slugs_as_the_server(title, year, expected):
    script = ("const m=require('./app/static/title-links.js');"
              f"process.stdout.write(m.titlePath('movie', {json.dumps(title)}, {json.dumps(year)}))")
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    server = title_pages.title_path("movie", title, int(year[:4]) if year else None)
    assert out == expected == server


def test_dashboard_loads_the_title_linker():
    html = Path("app/templates/index.html").read_text(encoding="utf-8")
    assert "/static/title-links.js?v=" in html


# ---------------------------------------------------------------- sharing

def test_share_buttons_on_public_pages(client, db_session):
    seed(db_session)
    title_page = client.get("/titles/movie/arrival-2016").text
    assert "data-share" in title_page and "/static/share.js" in title_page
    review = db_session.query(models.Movie).first()
    detail = client.get(f"/reviews/{review.id}?category=movie").text
    assert "data-share" in detail and "/static/share.js" in detail
    user = db_session.query(models.User).filter_by(username="a1").one()
    db_session.add(models.PublicProfile(user_id=user.id, enabled=True))
    db_session.commit()
    profile = client.get("/u/a1").text
    assert "Share profile" in profile and "/static/share.js" in profile
    collection = Path("app/templates/public_collection.html").read_text(encoding="utf-8")
    assert "data-share" in collection and "/static/share.js" in collection


def test_share_clicks_are_counted_anonymously():
    assert "share_clicked" in funnel.CLIENT_EVENTS and "share_clicked" in funnel.SERVER_EVENTS


# ---------------------------------------------------------------- email

def test_every_email_has_a_plain_text_part(monkeypatch):
    sent = {}

    class Capture:
        def __init__(self, **kwargs):
            sent.update(kwargs)

    monkeypatch.setattr(email_utils, "MessageSchema", Capture)
    asyncio.run(email_utils.send_verification_email("x@example.com", "neo", "tok"))
    assert sent["subtype"].value == "plain" and sent["multipart_subtype"].value == "alternative"
    assert "<html" in sent["alternative_body"].lower()
    assert "Verify Email Address" in sent["body"] and "<a " not in sent["body"]
    assert "token=tok" in sent["body"]  # the link survives as text


def test_html_to_text_keeps_links_and_drops_tags():
    text = email_utils.html_to_text('<html><body><h2>Hi &amp; welcome</h2><p>Open <a href="https://omnitrackr.xyz/?a=1&amp;b=2">your library</a>'
                                    '</p><style>p{color:red}</style></body></html>')
    assert text == "Hi & welcome\nOpen your library (https://omnitrackr.xyz/?a=1&b=2)\n"


def test_sender_has_a_display_name():
    assert email_utils.conf.MAIL_FROM_NAME == "OmniTrackr"
