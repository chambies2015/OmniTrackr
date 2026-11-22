"""Sweep of the Nov 22 morning merges: #300 member look, #301 corrections log, #302 On your services."""
import asyncio
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app import auth, models, streaming_services as streaming, title_metadata, title_pages, where_to_watch

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def tmdb(monkeypatch):
    monkeypatch.setenv("TMDB_API_KEY", "k")
    monkeypatch.setenv("WATCH_REGION", "US")


def member(db, name="nova"):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, created_at=datetime.utcnow() - timedelta(days=20))
    db.add(user)
    db.commit()
    return user


def where(*streams):
    groups = [{"label": "Stream", "providers": [{"name": name} for name in streams]}] if streams else []
    groups.append({"label": "Rent", "providers": [{"name": "Apple TV"}]})
    return {"v": 1, "groups": groups, "justwatch": True, "region": "US", "fetched": "2026-11-22"}


def cache(db, kind, title, year, data, fetched_at):
    key = where_to_watch.cache_key(kind, title_pages.normalize(title), year)
    row = db.query(models.TitleMetadata).filter_by(key=key).first()
    if row is None:
        row = models.TitleMetadata(key=key)
        db.add(row)
    row.status, row.data, row.fetched_at = "ok", json.dumps(data), fetched_at
    db.commit()
    return key


def sightings(db, key):
    return {row.service: row.baseline for row in db.query(models.ServiceSighting).filter_by(title_key=key)}


# ---------------------------------------------------------------- #302: arrivals

def test_an_old_cached_answer_doesnt_turn_old_services_into_arrivals(db_session):
    now = datetime.utcnow()
    user = member(db_session)
    db_session.add(models.Movie(title="Past Lives", year=2023, watched=False, user_id=user.id,
                                added_at=now - timedelta(days=90)))
    db_session.commit()
    streaming.save(db_session, user, ["netflix", "hulu"], now=now - timedelta(minutes=10))
    # Someone opened Where to watch for it two months ago, when it was on Hulu. Picking
    # services reads that answer straight away, so it becomes the baseline.
    key = cache(db_session, "movie", "Past Lives", 2023, where("Hulu"), now - timedelta(days=60))
    streaming.sync(db_session, [key], now=now - timedelta(minutes=9))
    assert sightings(db_session, key) == {"hulu": True}
    # The refresh a minute later finds it on Netflix too. That could have happened any day in
    # those two months, so it isn't news: no "New" tag and no bell note.
    cache(db_session, "movie", "Past Lives", 2023, where("Hulu", "Netflix"), now - timedelta(minutes=5))
    assert streaming.sync(db_session, [key], now=now - timedelta(minutes=4))["arrived"] == 0
    assert sightings(db_session, key) == {"hulu": True, "netflix": True}
    assert streaming.card(db_session, user, now=now)["new"] == 0
    assert streaming.send_alerts(db_session, now=now)["members"] == 0
    # From here on the title is checked every few days, so the next service it lands on is news.
    later = now + timedelta(days=3)
    cache(db_session, "movie", "Past Lives", 2023, where("Hulu", "Netflix", "Peacock"), later)
    assert streaming.sync(db_session, [key], now=later)["arrived"] == 1
    assert sightings(db_session, key)["peacock"] is False


# ---------------------------------------------------------------- #302: keeping the cache fresh

def test_one_big_list_doesnt_hold_up_everyone_elses_checks(db_session):
    now = datetime.utcnow()
    big, small = member(db_session, "bigimport"), member(db_session, "smalllist")
    db_session.add_all([models.Movie(title=f"Imported film {number}", year=2001, watched=False, user_id=big.id,
                                     added_at=now) for number in range(80)])
    db_session.add_all([models.Movie(title="Small film", year=2020, watched=False, user_id=small.id, added_at=now),
                        models.TVShow(title="Small show", year=2021, watched=False, user_id=small.id, added_at=now)])
    db_session.commit()
    streaming.save(db_session, big, ["netflix"], now=now)
    streaming.save(db_session, small, ["hulu"], now=now)
    due = [entry.title for entry in streaming.stale_entries(db_session, now, limit=10)]
    assert len(due) == 10
    assert {"Small film", "Small show"} <= set(due)


def test_a_title_refreshed_meanwhile_isnt_looked_up_again(db_session, monkeypatch):
    now = datetime.utcnow()
    user = member(db_session)
    db_session.add_all([models.Movie(title=f"Film {number}", year=2010 + number, watched=False, user_id=user.id,
                                     added_at=now) for number in range(4)])
    db_session.commit()
    streaming.save(db_session, user, ["netflix"], now=now)
    entries = streaming.stale_entries(db_session, now, user_id=user.id)
    assert len(entries) == 4
    looked = []

    async def fake_facts(db, client, kind, normalized, display, year, creator=None, wait=8.0):
        return {}

    async def fake_where(db, client, kind, normalized, display, year, metadata, wait=5.0, creator=None, force=False):
        looked.append(display)
        title_metadata.store(db, where_to_watch.cache_key(kind, normalized, year), where("Netflix"), "ok")
        return where("Netflix")

    monkeypatch.setattr(title_metadata, "get_or_fetch", fake_facts)
    monkeypatch.setattr(where_to_watch, "get_or_fetch", fake_where)
    # Two runs that listed their titles before either of them looked anything up.
    monkeypatch.setattr(streaming, "stale_entries", lambda *args, **kwargs: list(entries))
    from tests.conftest import TestingSessionLocal
    assert asyncio.run(streaming.warm(TestingSessionLocal, object(), pause=0)) == 4
    assert asyncio.run(streaming.warm(TestingSessionLocal, object(), pause=0)) == 0
    assert sorted(looked) == sorted(entry.title for entry in entries)


def test_saving_twice_quickly_starts_one_round_of_lookups(monkeypatch):
    calls = []

    async def slow_warm(session_factory, client, limit=streaming.WARM_BATCH, user_id=None, pause=1.5):
        calls.append(user_id)
        await asyncio.sleep(0.05)
        return 0

    class App:
        class state:
            external_api_client = object()

    monkeypatch.setattr(streaming, "enabled_for_process", lambda: True)
    monkeypatch.setattr(streaming, "warm", slow_warm)
    monkeypatch.setattr(streaming, "_sync_and_alert", lambda *args, **kwargs: {})

    async def both():
        await asyncio.gather(streaming.after_save(App, 7), streaming.after_save(App, 7), streaming.after_save(App, 8))

    asyncio.run(both())
    assert sorted(calls) == [7, 8]
    asyncio.run(streaming.after_save(App, 7))  # finished, so the next save looks up again
    assert sorted(calls) == [7, 7, 8]


# ---------------------------------------------------------------- #302: Site stats

def test_site_stats_script_tag_moved_with_the_streaming_block():
    html = (ROOT / "app/templates/site_stats.html").read_text()
    tag = re.search(r'/static/site-stats\.js\?v=([\w.-]+)"', html).group(1)
    # site-stats.js gained the "On your services" block in #302, but kept the tag it had since
    # Nov 20. Static files are cached for a year, so the block stayed empty for anyone who had
    # opened Site stats before.
    assert tag != "20261120-widgets-1"
    assert tag == "20261122-sweep-b-1"
    assert "growthStreaming" in (ROOT / "app/static/site-stats.js").read_text()


def test_streaming_script_tag_moved_with_the_new_summary():
    index = (ROOT / "app/templates/index.html").read_text()
    assert '/static/streaming.js?v=20261122-sweep-b-1" defer' in index


def test_changelog_lists_the_sweep():
    changelog = (ROOT / "app/templates/changelog.html").read_text()
    assert 'id="security-nov22b-2026-heading"' in changelog
    assert changelog.index("security-nov22b-2026-heading") < changelog.index("on-your-services-nov22-2026-heading")


# ---------------------------------------------------------------- #301: change notes on guides that go live later

def test_a_guide_that_goes_live_after_a_restart_still_gets_its_note(monkeypatch):
    from datetime import date

    from app import corrections_log
    from app.discover_catalog import MONTHLY_EDITIONS

    class Today(date):
        current = date(2026, 11, 30)

        @classmethod
        def today(cls):
            return cls.current

    monkeypatch.setattr(corrections_log, "date", Today)
    corrections_log._guide_names_on.cache_clear()
    path = "/discover/monthly/december-2026"
    monkeypatch.setitem(MONTHLY_EDITIONS["december-2026"], "published_date", "2099-01-01")
    assert path not in corrections_log._guide_names()
    # The server was started before the edition's day. The list of guides used to be cached for
    # the life of the process, so the new edition never got its "About this guide" note.
    monkeypatch.setitem(MONTHLY_EDITIONS["december-2026"], "published_date", "2026-01-01")
    Today.current = date(2026, 12, 1)
    assert path in corrections_log._guide_names()
