"""The year's big ones (Nov 27 2026): a poster grid on "Fill in your year" for titles that aren't in the library,
so an empty or short recap has something to fill in, on the member page, the emailed page and the December email."""
import asyncio
import re
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from app import auth, models, title_pages, year_catchup, year_fill, year_in_review
from app.site_traffic import RECORDER
from app.year_catchup_data import EDITIONS

NOW = datetime(2026, 12, 3, 12, 0)
SPIDER = "movie/spider-man-brand-new-day-2026"
GTA = "game/grand-theft-auto-vi-2026"
PITT = "tv/the-pitt-2025"
SERIAL = "podcast/serial-the-idiot-2026"


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    monkeypatch.setattr(year_fill, "_now", lambda: NOW)
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "yearfill" and name == key)


def member(db, name="reader", *, created=datetime(2026, 3, 1)):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True,
                       is_active=True, created_at=created, last_login_at=NOW - timedelta(days=40))
    db.add(user)
    db.flush()
    return user


def save(db, user, model=models.Movie, title="Dune", **fields):
    row = model(title=title, user_id=user.id, **fields)
    db.add(row)
    db.flush()
    return row


def headers_for(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}


def finishes(db, user):
    return db.query(models.ActivityEntry).filter_by(user_id=user.id, action="completed").all()


# ---------------------------------------------------------------- the list

def test_the_list_is_well_formed():
    raw = EDITIONS[2026]["entries"]
    assert len(raw) >= 40
    kinds = {entry["kind"] for entry in raw}
    assert kinds == set(title_pages.KINDS)                                   # all nine formats
    for entry in raw:
        assert re.fullmatch(r"2026-(0[1-9]|1[0-2])", entry["out"]), entry["title"]
        assert entry["title"] == entry["title"].strip() and entry["year"] <= 2026
        assert set(entry) <= {"kind", "title", "year", "creator", "out", "season", "feature"}
    ids = [entry["id"] for entry in year_catchup.entries(2026)]
    assert len(ids) == len(set(ids))
    features = [entry["feature"] for entry in raw]
    assert len(features) == len(set(features))
    # Grid order: by format, the biggest first.
    order = [entry["kind"] for entry in year_catchup.entries(2026)]
    assert order == sorted(order, key=year_catchup.KIND_ORDER.index)
    assert year_catchup.entries(2026)[0]["id"] == SPIDER


def test_months_start_when_it_came_out():
    gta = year_catchup.find(2026, GTA, date(2026, 12, 3))
    assert gta["when"] == "November 2026"
    assert [m["n"] for m in year_catchup.months_for(gta, 2026, date(2026, 12, 3))] == [11, 12]
    pitt = year_catchup.find(2026, PITT, date(2026, 12, 3))
    assert pitt["when"] == "Season 2 · January 2026" and pitt["question"] == "When did you finish season 2?"
    assert len(year_catchup.months_for(pitt, 2026, date(2026, 12, 3))) == 12
    # Not out yet: not shown, can't be found.
    assert year_catchup.find(2026, GTA, date(2026, 10, 20)) is None
    assert GTA not in [entry["id"] for entry in year_catchup.shown(2026, date(2026, 10, 20))]
    assert year_catchup.available(2026, date(2026, 12, 3)) and not year_catchup.available(2025, date(2026, 12, 3))
    assert not year_catchup.available(2026, date(2027, 2, 1))                # the 2026 recap is over


# ---------------------------------------------------------------- answering

def test_a_month_saves_the_title_finished_and_dated(db_session):
    user = member(db_session)
    db_session.commit()
    result = year_catchup.answer(db_session, user, 2026, SPIDER, "month", 8)
    assert result["state"] == "month" and result["title"] == "Spider-Man: Brand New Day"
    movie = db_session.query(models.Movie).filter_by(user_id=user.id).one()
    assert movie.title == "Spider-Man: Brand New Day" and movie.watched and movie.year == 2026
    assert movie.director == "Destin Daniel Cretton"
    entry = finishes(db_session, user)[0]
    assert entry.occurred_at == datetime(2026, 8, 15, 12, 0) and entry.source == "filled-in"
    assert year_in_review.finished_counts(db_session, user.id, 2026)["movies"] == 1
    record = db_session.query(models.YearCatchupAnswer).one()
    assert (record.answer, record.month, record.category, record.item_id, record.created_row) == (
        "month", 8, "movies", movie.id, True)
    # "Fill in your year" counts it as dated here.
    assert year_fill.filled_total(db_session, user.id, 2026) == 1
    # This month is a plain tick, dated now.
    year_catchup.answer(db_session, user, 2026, GTA, "month", 12)
    game = db_session.query(models.VideoGame).filter_by(user_id=user.id).one()
    assert game.played and game.release_date == datetime(2026, 1, 1)
    assert {e.source for e in finishes(db_session, user)} == {"filled-in", "automatic"}


def test_want_and_no(db_session):
    user = member(db_session)
    db_session.commit()
    assert year_catchup.answer(db_session, user, 2026, PITT, "want")["state"] == "want"
    show = db_session.query(models.TVShow).filter_by(user_id=user.id).one()
    assert show.title == "The Pitt" and not show.watched and show.year == 2025
    assert year_catchup.answer(db_session, user, 2026, SERIAL, "no")["state"] == "no"
    assert db_session.query(models.Podcast).filter_by(user_id=user.id).count() == 0
    assert finishes(db_session, user) == []
    found = year_catchup.grid(db_session, user.id, 2026)
    states = {item["id"]: item["state"] for group in found["groups"] for item in group["items"]}
    assert states[PITT] == "want" and states[SERIAL] == "no" and states[SPIDER] == "open"
    assert found["got"] == 0 and found["want"] == 1 and found["open"] == found["total"] - 2


def test_bad_answers_are_refused(db_session):
    user = member(db_session)
    db_session.commit()
    for args in ((SPIDER, "month", 6),          # before it came out
                 (SPIDER, "month", 13), (SPIDER, "month", None), (SPIDER, "drop", None),
                 ("movie/not-on-the-list", "want", None)):
        with pytest.raises(ValueError):
            year_catchup.answer(db_session, user, 2026, *args)
    with pytest.raises(ValueError):
        year_catchup.answer(db_session, user, 2025, SPIDER, "want")
    assert db_session.query(models.Movie).count() == 0 and db_session.query(models.YearCatchupAnswer).count() == 0


def test_titles_already_in_the_library_are_marked_not_asked(db_session):
    user = member(db_session)
    save(db_session, user, title="spider-man: brand new day", watched=True)   # any case
    save(db_session, user, model=models.TVShow, title="The Pitt")
    db_session.commit()
    found = year_catchup.grid(db_session, user.id, 2026)
    states = {item["id"]: item["state"] for group in found["groups"] for item in group["items"]}
    assert states[SPIDER] == "library_done" and states[PITT] == "library_saved"
    assert found["got"] == 1
    result = year_catchup.answer(db_session, user, 2026, SPIDER, "month", 9)
    assert result["state"] == "library" and result["done"] is True
    assert db_session.query(models.Movie).filter_by(user_id=user.id).count() == 1
    assert year_catchup.answer(db_session, user, 2026, GTA, "no")["state"] == "no"
    assert year_catchup.answer(db_session, user, 2026, GTA, "want")["state"] == "already"   # first answer stays
    assert SPIDER not in [item["id"] for item in year_catchup.featured(db_session, user.id, 2026)]


def test_undo(db_session):
    user = member(db_session)
    db_session.commit()
    year_catchup.answer(db_session, user, 2026, SPIDER, "month", 8)
    assert year_catchup.undo(db_session, user, 2026, SPIDER)
    assert db_session.query(models.Movie).count() == 0 and finishes(db_session, user) == []
    assert db_session.query(models.YearFillAnswer).count() == 0
    assert not year_catchup.undo(db_session, user, 2026, SPIDER)
    # A day later the title stays in the library; only the date and the answer go.
    year_catchup.answer(db_session, user, 2026, SPIDER, "month", 8)
    movie = db_session.query(models.Movie).one()
    movie.added_at = datetime.utcnow() - timedelta(days=2)                   # added_at is stamped with the real clock
    db_session.commit()
    assert year_catchup.undo(db_session, user, 2026, SPIDER)
    assert db_session.query(models.Movie).count() == 1 and finishes(db_session, user) == []
    # It now waits in "Ticked off, no date" instead.
    assert [card["title"] for card in year_fill.undated(db_session, user.id, 2026)[0]] == ["Spider-Man: Brand New Day"]


def test_another_member_cannot_touch_answers(db_session):
    user = member(db_session)
    other = member(db_session, "other")
    db_session.commit()
    year_catchup.answer(db_session, user, 2026, SPIDER, "month", 8)
    assert not year_catchup.undo(db_session, other, 2026, SPIDER)
    assert db_session.query(models.Movie).filter_by(user_id=user.id).count() == 1


# ---------------------------------------------------------------- the member page

def test_member_page_and_api(client, db_session):
    user = member(db_session)
    db_session.commit()
    headers = headers_for(user)
    html = client.get("/year-in-review/2026/fill", headers=headers).text
    assert 'id="big-ones"' in html and "/static/year-catchup.js" in html
    assert 'data-id="movie/spider-man-brand-new-day-2026"' in html and "I got to it" in html
    assert 'value="month-7"' in html and 'value="month-6"' not in html.split('id="yc-movie-spider-man')[1].split("</li>")[0]
    saved = client.post("/api/year-in-review/2026/big-ones", headers=headers,
                        json={"id": SPIDER, "answer": "month", "month": 8})
    assert saved.status_code == 200
    body = saved.json()
    assert body["state"] == "month" and body["got"] == 1 and body["finished_total"] == 1 and body["filled"] == 1
    assert counted("catchup_got_page") == 1
    assert client.post("/api/year-in-review/2026/big-ones", headers=headers,
                       json={"id": SPIDER, "answer": "month", "month": 9}).json()["state"] == "already"
    assert client.post("/api/year-in-review/2026/big-ones", headers=headers,
                       json={"id": GTA, "answer": "month", "month": 3}).status_code == 422
    undone = client.post("/api/year-in-review/2026/big-ones/undo", headers=headers, json={"id": SPIDER})
    assert undone.json()["undone"] is True and undone.json()["got"] == 0 and counted("catchup_undone_page") == 1
    assert client.post("/api/year-in-review/2026/big-ones", json={"id": SPIDER, "answer": "no"}).status_code == 401
    assert client.post("/api/year-in-review/2025/big-ones", headers=headers,
                       json={"id": SPIDER, "answer": "no"}).status_code == 404
    assert client.get("/api/year-in-review/2026/big-ones/art/movie/not-a-pick", headers=headers).status_code == 404


def test_page_with_titles_to_date_keeps_them_first(client, db_session):
    user = member(db_session)
    save(db_session, user, title="Arrival", watched=True)
    db_session.commit()
    html = client.get("/year-in-review/2026/fill", headers=headers_for(user)).text
    assert html.index("Ticked off, no date") < html.index("2026’s big ones")
    assert "OmniTrackr started dating what you finish in September" in html


def test_recap_page_points_a_short_recap_at_the_big_ones(client, db_session):
    user = member(db_session)
    db_session.commit()
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(user))
    recap = client.get("/year-in-review/2026").text
    assert "Add 2026’s big ones" in recap and "Your recap is empty so far." in recap
    assert 'href="/year-in-review/2026/fill#big-ones"' in recap


def test_recap_card_for_titles_to_date_also_offers_the_big_ones(client, db_session):
    user = member(db_session)
    save(db_session, user, title="Arrival", watched=True)
    db_session.commit()
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(user))
    recap = client.get("/year-in-review/2026").text
    assert "ticked off with no date" in recap
    assert 'href="/year-in-review/2026/fill#big-ones">Add 2026’s big ones</a>' in recap


# ---------------------------------------------------------------- the emailed page

def _link(user):
    return f"/fill-in/{year_fill.make_token(user.id, 2026, [], catchup=True)}"


def test_emailed_page_saves_without_signing_in(client, db_session):
    user = member(db_session)
    db_session.commit()
    path = _link(user)
    chrome = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36"}
    page = client.get(path + f"?pick={SPIDER}", headers=chrome)
    assert page.status_code == 200 and "Your 2026, reader" in page.text and "Got to 0 of" in page.text
    assert "noindex" in page.headers["x-robots-tag"] and "/static/year-catchup.js" not in page.text
    opened = page.text.split('id="yc-movie-spider-man-brand-new-day-2026"')[1].split("</li>")[0]
    assert '<details class="yc-pick" open>' in opened
    assert counted("catchup_opened_email") == 1
    saved = client.post(path, data={"pick": SPIDER, "choice": "month-8"}, follow_redirects=False)
    assert saved.status_code == 303 and saved.headers["location"] == "?r=1#yc-movie-spider-man-brand-new-day-2026"
    assert finishes(db_session, user)[0].occurred_at == datetime(2026, 8, 15, 12, 0)
    assert counted("catchup_got_email") == 1
    after = client.get(path + "?r=1", headers=chrome).text
    assert "Watched in August" in after and "Got to 1 of" in after and counted("catchup_opened_email") == 1
    client.post(path, data={"pick": PITT, "choice": "want"})
    assert db_session.query(models.TVShow).filter_by(user_id=user.id).count() == 1
    client.post(path, data={"pick": SPIDER, "choice": "undo"})
    assert finishes(db_session, user) == [] and counted("catchup_undone_email") == 1
    for data in ({"pick": "movie/not-a-pick", "choice": "want"}, {"pick": GTA, "choice": "month-2"},
                 {"pick": SPIDER, "choice": "month-x"}, {"pick": SPIDER, "choice": "drop"}):
        assert client.post(path, data=data, follow_redirects=False).status_code == 303
    assert finishes(db_session, user) == [] and db_session.query(models.Movie).count() == 0
    db_session.refresh(user)
    assert user.last_seen_on is not None


def test_a_link_without_the_big_ones_cannot_save_them(client, db_session):
    user = member(db_session)
    movie = save(db_session, user, title="Arrival", watched=True)
    db_session.commit()
    token = year_fill.make_token(user.id, 2026, [{"category": "movies", "id": movie.id}])
    page = client.get(f"/fill-in/{token}").text
    assert "big ones" not in page
    client.post(f"/fill-in/{token}", data={"pick": SPIDER, "choice": "want"})
    assert db_session.query(models.Movie).count() == 1
    # A link with neither titles nor the big ones is never made, and wouldn't open.
    empty = year_fill._serializer().dumps({"u": user.id, "y": 2026, "i": []})
    assert year_fill.read_token(empty) is None and client.get(f"/fill-in/{empty}").status_code == 404


def test_a_link_with_both(client, db_session):
    user = member(db_session)
    movie = save(db_session, user, title="Arrival", watched=True)
    db_session.commit()
    token = year_fill.make_token(user.id, 2026, [{"category": "movies", "id": movie.id}], catchup=True)
    assert year_fill.read_token(token)["catchup"] is True
    page = client.get(f"/fill-in/{token}").text
    assert "Arrival" in page and 'id="big-ones"' in page and page.index("Arrival") < page.index('id="big-ones"')


# ---------------------------------------------------------------- the December email

def test_empty_library_gets_the_big_ones_email(db_session):
    user = member(db_session)
    show = save(db_session, user, model=models.TVShow, title="The Pitt", watched=True)   # already has it: no poster
    db_session.add(models.ActivityEntry(user_id=user.id, category="tv-shows", item_id=show.id, title="The Pitt",
                                        action="completed", source="automatic", occurred_at=datetime(2025, 3, 1)))
    db_session.commit()
    subject, html, text, _ = year_fill.email_for(db_session, user, NOW)
    assert subject == "Spider-Man: Brand New Day, Grand Theft Auto VI, Toy Story 5: which did you get to in 2026?"
    assert "Your 2026 recap on OmniTrackr is empty so far" in text and "You don't need to sign in" in text
    assert "The Pitt" not in html and "I got to it" in html and "See all 46" in html
    links = re.findall(r'href="([^"]*/fill-in/[^"]*)"', html)
    first = urlsplit(links[0].replace("&amp;", "&"))
    assert parse_qs(first.query)["pick"] == [SPIDER] and first.fragment == "yc-movie-spider-man-brand-new-day-2026"
    token = first.path.rsplit("/", 1)[1]
    assert year_fill.read_token(token) == {"user_id": user.id, "year": 2026, "items": [], "catchup": True}
    assert year_fill.email_variant(db_session, user, NOW) == "big"


def test_a_short_recap_gets_it_too(db_session):
    user = member(db_session)
    movie = save(db_session, user, title="Alien", watched=True)
    db_session.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=movie.id, title="Alien",
                                        action="completed", source="automatic", occurred_at=datetime(2026, 10, 1)))
    db_session.commit()
    subject, html, text, _ = year_fill.email_for(db_session, user, NOW)
    assert "which did you get to in 2026?" in subject
    assert "Your 2026 recap on OmniTrackr has 1 finish so far" in text


def test_send_due_counts_the_big_ones(db_session):
    user = member(db_session)
    db_session.commit()
    year_fill.set_status(db_session, "sending")
    sent = []

    class KeepOpen:
        def __init__(self, db):
            self._db = db

        def __getattr__(self, name):
            return getattr(self._db, name)

        def close(self):
            pass

    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject))
    result = asyncio.run(year_fill.send_due(lambda: KeepOpen(db_session), now=NOW, sender=sender))
    assert result["sent"] == 1 and "which did you get to" in sent[0][1]
    assert counted("sent") == 1 and counted("sent_big") == 1
    assert user.id in {row.user_id for row in db_session.query(models.EmailCampaignSend)}


def test_owner_preview_of_the_big_ones(client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "boss")
    owner = member(db_session, "boss")
    for n in range(6):
        movie = save(db_session, owner, title=f"Film {n}", watched=True)
        db_session.add(models.ActivityEntry(user_id=owner.id, category="movies", item_id=movie.id, title=movie.title,
                                            action="completed", source="automatic", occurred_at=datetime(2026, 10, 1)))
    db_session.commit()
    headers = headers_for(owner)
    plain = client.get("/site-stats/year-fill-preview", headers=headers).text
    assert "Your 2026 in review is ready" in plain
    big = client.get("/site-stats/year-fill-preview?variant=big", headers=headers).text
    assert "which did you get to in 2026?" in big and "Members with an empty or thin recap get this one" in big
    card = client.get("/api/site-stats/year-fill", headers=headers).json()
    assert {"source", "got", "want", "no", "undone"} <= set(card["page"]["big_by_source"][0])
