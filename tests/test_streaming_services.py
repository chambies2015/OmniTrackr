"""On your services: picking services, the home card, arrivals, notes, the library filter, the weekly email."""
import asyncio
import json
from datetime import datetime, timedelta

import pytest

from app import auth, digest, models, streaming_services as streaming, title_metadata, title_pages, web_push, where_to_watch
from app.site_traffic import RECORDER

CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    monkeypatch.setenv("TMDB_API_KEY", "k")
    monkeypatch.setenv("WATCH_REGION", "US")
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "stream" and name == key)


def member(db, name="nova"):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, created_at=datetime.utcnow() - timedelta(days=20))
    db.add(user)
    db.commit()
    return user


def headers(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}", **CHROME}


def where(*streams, justwatch=True, rent=("Apple TV",)):
    groups = []
    if streams:
        groups.append({"label": "Stream", "providers": [{"name": name} for name in streams]})
    if rent:
        groups.append({"label": "Rent", "providers": [{"name": name} for name in rent]})
    return {"v": 1, "groups": groups, "justwatch": justwatch, "region": "US", "fetched": "2026-11-22"}


def cache(db, kind, title, year, data, fetched_at=None):
    key = where_to_watch.cache_key(kind, title_pages.normalize(title), year)
    row = db.query(models.TitleMetadata).filter_by(key=key).first()
    if row is None:
        row = models.TitleMetadata(key=key)
        db.add(row)
    row.status = "ok"
    row.data = json.dumps(data)
    row.fetched_at = fetched_at or datetime.utcnow()
    db.commit()
    return key


def shelf(db, user):
    added = datetime.utcnow() - timedelta(days=30)
    rows = [
        models.Movie(title="Dune: Part Two", year=2024, watched=False, user_id=user.id, added_at=added,
                     poster_url="https://image.tmdb.org/t/p/w342/dune.jpg"),
        models.Movie(title="Past Lives", year=2023, watched=False, user_id=user.id, added_at=added),
        models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id, added_at=added),
        models.Anime(title="Frieren", year=2023, watched=False, user_id=user.id, added_at=added),
        models.Movie(title="Arrival", year=2016, watched=True, user_id=user.id, added_at=added),
        models.Book(title="Piranesi", read=False, user_id=user.id),
    ]
    db.add_all(rows)
    db.commit()
    return rows


def card(client, user):
    response = client.get("/api/streaming", headers=headers(user))
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    return response.json()["card"]


def pick(client, user, services, alerts=True):
    response = client.put("/api/streaming", json={"services": services, "alerts": alerts}, headers=headers(user))
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------- names

@pytest.mark.parametrize("name, service", [
    ("Netflix", "netflix"), ("Netflix basic with Ads", "netflix"), ("Netflix Standard with Ads", "netflix"),
    ("Max", "hbomax"), ("HBO Max", "hbomax"), ("Max Amazon Channel", "hbomax"), ("Disney Plus", "disney"),
    ("Disney+", "disney"), ("Apple TV Plus", "apple"), ("Apple TV+", "apple"), ("Peacock Premium Plus", "peacock"),
    ("Paramount Plus Essential", "paramount"), ("Paramount+ with Showtime", "paramount"),
    ("Paramount Plus Apple TV Channel ", "paramount"), ("Amazon Prime Video with Ads", "prime"),
    ("Crunchyroll Amazon Channel", "crunchyroll"), ("AMC+", "amc"), ("Tubi TV", "tubi"), ("The Roku Channel", "roku"),
    ("Paramount+ Roku Premium Channel", "paramount"), ("Peacock Premium", "peacock"), ("Apple TV Amazon Channel", "apple"),
    ("Amazon Prime Video Free with Ads", "prime"), ("HBO Max Amazon Channel", "hbomax"),
    ("Starz Roku Premium Channel", "starz"), ("Hulu", "hulu"),
])
def test_provider_names_map_to_one_service(name, service):
    assert streaming.service_for(name) == service


def test_unknown_providers_and_rent_or_buy_dont_count():
    for name in ("Fandango At Home", "Apple TV Store", "Amazon Video", "YouTube TV", "Fandango at Home Free"):
        assert streaming.service_for(name) is None, name
    data = {"groups": [{"label": "Rent", "providers": [{"name": "Prime Video"}]},
                       {"label": "Buy", "providers": [{"name": "Apple TV"}]},
                       {"label": "Originally aired on", "providers": [{"name": "Netflix"}]},
                       {"label": "Made for", "providers": [{"name": "Disney+"}]},
                       {"label": "Official streams", "providers": [{"name": "Crunchyroll"}]},
                       {"label": "Free with ads", "providers": [{"name": "Tubi TV"}]}]}
    assert streaming.services_in(data) == {"disney", "crunchyroll", "tubi"}


# ---------------------------------------------------------------- the card

def test_card_asks_once_there_are_two_unfinished_video_titles(client, db_session):
    user = member(db_session)
    db_session.add(models.Movie(title="Dune", year=2021, watched=False, user_id=user.id))
    db_session.add(models.Book(title="Piranesi", read=False, user_id=user.id))
    db_session.commit()
    assert card(client, user) is None
    db_session.add(models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id))
    db_session.commit()
    found = card(client, user)
    assert found["state"] == "choose" and found["tracked"] == 2 and found["kinds"] == ["movies", "tv-shows"]
    assert [s["id"] for s in found["catalog"]][:3] == ["netflix", "prime", "hbomax"]
    assert found["region"] == "US" and found["alerts"] is True


def test_not_now_and_no_thanks(client, db_session):
    user = member(db_session)
    shelf(db_session, user)
    assert client.post("/api/streaming/answer", json={"answer": "later"}, headers=headers(user)).status_code == 200
    assert card(client, user) is None and counted("later") == 1
    choice = streaming.get_choice(db_session, user.id)
    choice.hidden_until = datetime.utcnow() - timedelta(minutes=1)
    db_session.commit()
    assert card(client, user)["state"] == "choose"
    client.post("/api/streaming/answer", json={"answer": "stop"}, headers=headers(user))
    assert card(client, user) is None
    # A link from a note or email brings it back.
    shown = client.post("/api/streaming/answer", json={"answer": "show"}, headers=headers(user)).json()
    assert shown["card"]["state"] == "choose"
    assert client.post("/api/streaming/answer", json={"answer": "nope"}, headers=headers(user)).status_code == 422


def test_picking_services_lists_what_streams_there(client, db_session):
    user = member(db_session)
    shelf(db_session, user)
    cache(db_session, "movie", "Dune: Part Two", 2024, where("Max", "Max Amazon Channel"))
    cache(db_session, "movie", "Past Lives", 2023, where(rent=("Prime Video",)))  # rent only
    cache(db_session, "tv", "Severance", 2022, where("Apple TV Plus"))
    cache(db_session, "movie", "Arrival", 2016, where("Netflix"))  # finished: not on the card
    data = pick(client, user, ["hbomax", "netflix"])
    assert data["chosen"] == ["Netflix", "HBO Max"]
    found = data["card"]
    assert found["state"] == "list"
    assert [item["title"] for item in found["items"]] == ["Dune: Part Two"]
    item = found["items"][0]
    assert item["services"] == [{"id": "hbomax", "name": "HBO Max", "new": False}]
    assert item["path"] == "/titles/movie/dune-part-two-2024" and item["poster"].startswith("https://")
    assert item["new"] is False and item["queued"] is False
    assert found["chosen"] == [{"id": "netflix", "name": "Netflix", "count": 0}, {"id": "hbomax", "name": "HBO Max", "count": 1}]
    # Frieren has no cached answer yet, so it's still being checked.
    assert found["pending"] == 1 and found["total"] == 1
    assert counted("saved_card") == 1
    assert "JustWatch via TMDB" in found["credit"]


def test_unknown_service_is_refused_and_privacy_hides_title_links(client, db_session):
    user = member(db_session)
    shelf(db_session, user)
    bad = client.put("/api/streaming", json={"services": ["netflix", "piratebay"]}, headers=headers(user))
    assert bad.status_code == 422
    user.movies_private = True
    db_session.commit()
    cache(db_session, "movie", "Dune: Part Two", 2024, where("Netflix"))
    item = pick(client, user, ["netflix"])["card"]["items"][0]
    assert item["path"] is None  # opens in the library instead of a public title page


def test_hide_and_changing_services(client, db_session):
    user = member(db_session)
    shelf(db_session, user)
    cache(db_session, "tv", "Severance", 2022, where("Apple TV"))
    pick(client, user, ["netflix"])
    assert card(client, user)["total"] == 0
    pick(client, user, ["netflix", "apple"])
    assert counted("changed") == 1
    assert card(client, user)["total"] == 1
    client.post("/api/streaming/answer", json={"answer": "hide"}, headers=headers(user))
    assert card(client, user) is None
    pick(client, user, [])
    assert counted("cleared") == 1
    assert card(client, user)["state"] == "choose"


# ---------------------------------------------------------------- arrivals

def test_first_check_is_a_baseline_and_later_services_are_arrivals(client, db_session):
    user = member(db_session)
    shelf(db_session, user)
    then = datetime.utcnow() - timedelta(days=5)
    key = cache(db_session, "movie", "Past Lives", 2023, where("Hulu"), fetched_at=then - timedelta(days=1))
    choice = streaming.save(db_session, user, ["netflix", "hulu"], now=then - timedelta(days=2))
    assert streaming.sync(db_session, [key], now=then)["compared"] == 1
    rows = db_session.query(models.ServiceSighting).filter_by(title_key=key).all()
    assert [(r.service, r.baseline) for r in rows] == [("hulu", True)]
    # Unchanged cache row: nothing to compare.
    assert streaming.sync(db_session, [key], now=then)["compared"] == 0
    # A week later the title shows up on Netflix too.
    cache(db_session, "movie", "Past Lives", 2023, where("Hulu", "Netflix basic with Ads"), fetched_at=then + timedelta(hours=1))
    stats = streaming.sync(db_session, [key], now=then + timedelta(hours=2))
    assert stats["arrived"] == 1
    found = card(client, user)
    item = next(i for i in found["items"] if i["title"] == "Past Lives")
    assert item["new"] is True and found["new"] == 1
    assert {s["id"]: s["new"] for s in item["services"]} == {"netflix": True, "hulu": False}
    sent = streaming.send_alerts(db_session, now=then + timedelta(hours=3))
    assert sent == {"members": 1, "titles": 1}
    note = db_session.query(models.Notification).filter_by(user_id=user.id, type="service_arrival").one()
    assert note.message == "Past Lives is now streaming on Netflix, and it's on your list."
    assert note.link == "/#on-your-services"
    # Never told twice.
    assert streaming.send_alerts(db_session, now=then + timedelta(hours=4)) == {"members": 0, "titles": 0}
    assert counted("alert_sent") == 1 and counted("alert_titles") == 1
    assert choice.alerts is True


def test_no_note_when_alerts_are_off_or_the_service_was_picked_later(db_session):
    user = member(db_session)
    shelf(db_session, user)
    now = datetime.utcnow()
    key = cache(db_session, "tv", "Severance", 2022, where(), fetched_at=now - timedelta(days=3))
    streaming.sync(db_session, [key], now=now - timedelta(days=3))
    cache(db_session, "tv", "Severance", 2022, where("Apple TV"), fetched_at=now - timedelta(days=1))
    streaming.sync(db_session, [key], now=now - timedelta(days=1))
    # Picked Apple TV today, after the show arrived: the card shows it, no note.
    streaming.save(db_session, user, ["apple"], now=now)
    assert streaming.send_alerts(db_session, now=now)["members"] == 0
    other = member(db_session, "maya")
    db_session.add(models.TVShow(title="Severance", year=2022, watched=False, user_id=other.id,
                                 added_at=now - timedelta(days=40)))
    db_session.commit()
    streaming.save(db_session, other, ["apple"], alerts=False, now=now - timedelta(days=10))
    assert streaming.send_alerts(db_session, now=now)["members"] == 0
    streaming.save(db_session, other, None, alerts=True, now=now)
    assert streaming.send_alerts(db_session, now=now)["members"] == 1


def test_several_arrivals_make_one_note(db_session):
    user = member(db_session)
    shelf(db_session, user)
    start = datetime.utcnow() - timedelta(days=2)
    streaming.save(db_session, user, ["netflix", "hbomax", "crunchyroll"], now=start - timedelta(days=1))
    keys = [cache(db_session, kind, title, year, where(), fetched_at=start)
            for kind, title, year in (("movie", "Dune: Part Two", 2024), ("movie", "Past Lives", 2023),
                                      ("tv", "Severance", 2022), ("anime", "Frieren", 2023))]
    streaming.sync(db_session, keys, now=start)
    later = start + timedelta(days=1)
    cache(db_session, "movie", "Dune: Part Two", 2024, where("Max"), fetched_at=later)
    cache(db_session, "movie", "Past Lives", 2023, where("Netflix"), fetched_at=later)
    data = {"groups": [{"label": "Official streams", "providers": [{"name": "Crunchyroll"}]}], "justwatch": False}
    cache(db_session, "anime", "Frieren", 2023, data, fetched_at=later)
    streaming.sync(db_session, keys, now=later)
    assert streaming.send_alerts(db_session, now=later)["titles"] == 3
    note = db_session.query(models.Notification).filter_by(user_id=user.id).one()
    assert note.message.startswith("Now on your services: ")
    assert note.message.endswith("and 1 more from your list.")


def test_a_short_gap_is_a_blip_but_a_long_one_is_an_arrival(db_session):
    now = datetime.utcnow()
    key = cache(db_session, "movie", "Dune", 2021, where("Netflix"), fetched_at=now - timedelta(days=40))
    streaming.sync(db_session, [key], now=now - timedelta(days=40))
    # Gone (TMDB answered without it), then back after a week: a blip.
    cache(db_session, "movie", "Dune", 2021, where(), fetched_at=now - timedelta(days=30))
    assert streaming.sync(db_session, [key], now=now - timedelta(days=30))["left"] == 1
    cache(db_session, "movie", "Dune", 2021, where("Netflix"), fetched_at=now - timedelta(days=23))
    assert streaming.sync(db_session, [key], now=now - timedelta(days=23))["arrived"] == 0
    row = db_session.query(models.ServiceSighting).filter_by(title_key=key).one()
    assert row.baseline is True and row.gone_at is None
    # Gone for three weeks, then back: that's an arrival.
    cache(db_session, "movie", "Dune", 2021, where(), fetched_at=now - timedelta(days=22))
    streaming.sync(db_session, [key], now=now - timedelta(days=22))
    cache(db_session, "movie", "Dune", 2021, where("Netflix"), fetched_at=now)
    assert streaming.sync(db_session, [key], now=now)["arrived"] == 1
    db_session.refresh(row)
    assert row.baseline is False and row.first_seen_at == now


def test_an_answer_without_tmdb_never_marks_services_gone(db_session):
    now = datetime.utcnow()
    key = cache(db_session, "tv", "Severance", 2022, where("Apple TV"), fetched_at=now - timedelta(days=4))
    streaming.sync(db_session, [key], now=now - timedelta(days=4))
    made_for = {"groups": [{"label": "Made for", "providers": [{"name": "Apple TV+"}]}], "justwatch": False}
    cache(db_session, "tv", "Severance", 2022, {"groups": [], "justwatch": False}, fetched_at=now)
    assert streaming.sync(db_session, [key], now=now)["left"] == 0
    cache(db_session, "tv", "Severance", 2022, made_for, fetched_at=now + timedelta(minutes=1))
    assert streaming.sync(db_session, [key], now=now + timedelta(minutes=2))["arrived"] == 0


# ---------------------------------------------------------------- refreshing the cache

def test_stale_titles_come_first_and_warm_looks_them_up(db_session, monkeypatch):
    user = member(db_session)
    shelf(db_session, user)
    now = datetime.utcnow()
    streaming.save(db_session, user, ["netflix"], now=now)
    cache(db_session, "movie", "Dune: Part Two", 2024, where("Netflix"), fetched_at=now - timedelta(days=4))
    cache(db_session, "movie", "Past Lives", 2023, where("Netflix"), fetched_at=now - timedelta(hours=2))
    due = [entry.title for entry in streaming.stale_entries(db_session, now)]
    # Never looked up first, then the oldest; fresh answers and finished titles are left alone.
    assert due[:2] == ["Frieren", "Severance"] or due[:2] == ["Severance", "Frieren"]
    assert due[2:] == ["Dune: Part Two"]
    looked = []

    async def fake_facts(db, client, kind, normalized, display, year, creator=None, wait=8.0):
        return {}

    async def fake_where(db, client, kind, normalized, display, year, metadata, wait=5.0, creator=None, force=False):
        looked.append((display, force))
        return {}

    monkeypatch.setattr(title_metadata, "get_or_fetch", fake_facts)
    monkeypatch.setattr(where_to_watch, "get_or_fetch", fake_where)
    from tests.conftest import TestingSessionLocal
    fetched = asyncio.run(streaming.warm(TestingSessionLocal, object(), limit=2, pause=0))
    assert fetched == 2 and all(force for _, force in looked)


# ---------------------------------------------------------------- the library filter and the dialog

def test_on_my_services_library_filter(client, db_session):
    user = member(db_session)
    shelf(db_session, user)
    cache(db_session, "movie", "Arrival", 2016, where("Netflix"))
    cache(db_session, "movie", "Dune: Part Two", 2024, where("Hulu"))
    page = client.get("/library/page/movies?on_services=true", headers=headers(user)).json()
    assert page["total"] == 0  # nothing picked yet
    pick(client, user, ["netflix"])
    page = client.get("/library/page/movies?on_services=true", headers=headers(user)).json()
    assert [item["title"] for item in page["items"]] == ["Arrival"]  # finished titles count in the library
    page = client.get("/library/page/movies?on_services=true&completion=unfinished", headers=headers(user)).json()
    assert page["total"] == 0
    assert client.get("/library/page/books?on_services=true", headers=headers(user)).status_code == 422


def test_where_to_watch_marks_the_members_services(client, db_session, monkeypatch):
    user = member(db_session)
    shelf(db_session, user)
    data = where("Netflix basic with Ads", "Hulu", rent=("Netflix",))
    cache(db_session, "movie", "Past Lives", 2023, data)
    pick(client, user, ["netflix"])
    async def no_facts(*args, **kwargs):
        return {}

    monkeypatch.setattr(title_metadata, "get_or_fetch", no_facts)
    response = client.get("/api/where-to-watch?kind=movie&title=Past%20Lives&year=2023", headers=headers(user))
    assert response.status_code == 200
    assert response.json()["mine"] == ["Netflix basic with Ads"]


# ---------------------------------------------------------------- notes, email, counters

def test_push_switch_and_bell_link():
    assert web_push.TITLES["service_arrival"] == "Now on your services"
    assert web_push.topic_of("service_arrival") == "streaming"
    assert next(topic for topic in web_push.TOPICS if topic[0] == "streaming")[3] is True


def test_weekly_email_lists_new_arrivals(db_session):
    user = member(db_session)
    shelf(db_session, user)
    now = datetime.utcnow()
    key = cache(db_session, "movie", "Past Lives", 2023, where(), fetched_at=now - timedelta(days=3))
    streaming.sync(db_session, [key], now=now - timedelta(days=3))
    cache(db_session, "movie", "Past Lives", 2023, where("Netflix"), fetched_at=now - timedelta(days=1))
    streaming.sync(db_session, [key], now=now - timedelta(days=1))
    assert streaming.digest_line(db_session, user, now) == []  # no services picked
    streaming.save(db_session, user, ["netflix"], now=now - timedelta(days=9))
    lines = streaming.digest_line(db_session, user, now)
    assert lines == [{"title": "Past Lives", "label": "Movie", "services": ["Netflix"]}]
    streaming.save(db_session, user, None, False)  # unticked "Tell me when..." on the card
    assert streaming.digest_line(db_session, user, now) == []
    streaming.save(db_session, user, None, True)
    report = {"matches": [], "popular": [{"title": "Wicked", "label": "Movie", "date": "2026-11-27", "url": "/x"}]}
    subject, html, text = digest.build_digest("nova", report, "https://example.com/u", streaming=lines)
    assert "New on your services" in html and "Now on Netflix" in html
    assert "- Past Lives (Movie) - now on Netflix" in text


def test_event_counters_and_site_stats(client, db_session):
    user = member(db_session)
    shelf(db_session, user)
    assert client.post("/api/streaming/event", json={"event": "where"}, headers=headers(user)).json() == {"counted": True}
    assert client.post("/api/streaming/event", json={"event": "nonsense"}, headers=headers(user)).status_code == 422
    assert counted("where") == 1
    pick(client, user, ["netflix", "hbomax"])
    found = streaming.stats(db_session, 30, datetime.utcnow())
    assert found["members_now"] == 1 and found["alerts_on_now"] == 1
    assert found["by_service"] == [{"name": "Netflix", "count": 1}, {"name": "HBO Max", "count": 1}]
    assert set(found["labels"]) == set(streaming.COUNTERS)


def test_signed_out_requests_are_refused(client):
    assert client.get("/api/streaming").status_code == 401
    assert client.put("/api/streaming", json={"services": ["netflix"]}).status_code in (401, 403)


def test_card_script_styles_and_hooks_are_wired():
    from pathlib import Path
    from app import dashboard_assets
    root = Path(__file__).resolve().parents[1]
    index = (root / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    bundle = dashboard_assets.full_source()
    tag = index[index.index('<section id="onYourServices"'):]
    assert tag[:tag.index(">")].endswith("hidden")
    assert '/static/streaming.js?v=20261122-tonight-share-1" defer' in index
    assert '/static/streaming.css?v=20261122-tonight-share-1' in index
    for hook in ("window.OmniStreaming?.refresh();", "window.OmniStreaming?.reset();",
                 "window.OmniStreaming?.renderFilters(category, host);",
                 "if (filters.onServices) parsed.searchParams.set('on_services', 'true');",
                 "notif.type === 'service_arrival' && notif.link === '/#on-your-services'"):
        assert hook in bundle, hook
    links = (root / "app" / "static" / "title-links.js").read_text(encoding="utf-8")
    assert "where-dialog__provider--mine" in links and "'You have it'" in links
