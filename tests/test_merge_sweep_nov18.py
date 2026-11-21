"""Nov 18 2026 sweep of PRs #240-#242 (first-week card + reminder, Keep your list sheet, search-visitor counts)."""
import asyncio
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import event

from app import models, week_one
from tests.conftest import engine
from tests.test_week_one import _session_factory, headers, member, schedule, setup, today  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def _shows(db_session, count=3):
    others = [member(db_session, f"m{i}", days_old=40) for i in range(count)]
    for other in others:
        db_session.add(models.TVShow(title="Andor", year=2022, watched=False, seasons=2, user_id=other.id))
    db_session.commit()
    return others, schedule(db_session, "tv-shows", "Andor", 2022, 3)


def test_shows_airing_pool_keeps_one_copy_per_local_day(db_session, monkeypatch):
    _shows(db_session)
    day, tomorrow = today(), today() + timedelta(days=1)
    first = week_one.airing_pool(db_session, day)
    assert [show["title"] for show in first] == ["Andor"]
    week_one.airing_pool(db_session, tomorrow)
    built = []
    monkeypatch.setattr(week_one, "_key_parts", lambda key: built.append(key))
    # Members either side of UTC midnight used to evict each other's copy and rebuild on every card load.
    assert week_one.airing_pool(db_session, day) == first
    assert week_one.airing_pool(db_session, tomorrow)
    assert built == []
    week_one.airing_pool(db_session, day + timedelta(days=9))
    assert day not in week_one._POOL and tomorrow not in week_one._POOL


def test_pool_source_row_stays_off_the_card(client, db_session):
    user = member(db_session)
    db_session.add(models.Movie(title="Heat", year=1995, watched=True, user_id=user.id))
    db_session.commit()
    _shows(db_session)
    picks = client.get(f"/api/week-one?today={today().isoformat()}", headers=headers(user)).json()["card"]["suggestions"]
    assert picks and all("source_id" not in pick and "library_title" not in pick for pick in picks)


def test_saving_a_show_reads_one_shelf_row_not_every_shelf(client, db_session):
    user = member(db_session)
    others, key = _shows(db_session, count=6)
    for other in others:  # plenty of unrelated shared rows that the old scan loaded on every save
        for number in range(20):
            db_session.add(models.TVShow(title=f"Other {number}", year=2020, watched=False, user_id=other.id))
    db_session.commit()
    week_one.airing_pool(db_session, today())
    statements = []
    listener = lambda conn, cursor, statement, *args: statements.append(statement)  # noqa: E731
    event.listen(engine, "before_cursor_execute", listener)
    try:
        response = client.post("/api/week-one/save", headers=headers(user), json={"key": key, "today": today().isoformat()})
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    assert response.status_code == 200 and response.json()["state"] == "created"
    scans = [sql for sql in statements if "FROM tv_shows" in sql and "IN (SELECT users.id" in sql]
    assert scans == []
    saved = db_session.query(models.TVShow).filter_by(user_id=user.id).one()
    assert saved.title == "Andor" and saved.seasons == 2 and saved.watched is False


def test_saving_falls_back_when_the_pool_row_went_private(client, db_session):
    user = member(db_session)
    others, key = _shows(db_session, count=2)
    pool = week_one.airing_pool(db_session, today())
    source = db_session.get(models.TVShow, pool[0]["source_id"])
    owner = db_session.get(models.User, source.user_id)
    owner.tv_shows_private = True
    db_session.commit()
    response = client.post("/api/week-one/save", headers=headers(user), json={"key": key, "today": today().isoformat()})
    assert response.status_code == 200 and response.json()["state"] == "created"
    # Every shelf with it private now: the cached pool can't copy from it.
    for other in others:
        other.tv_shows_private = True
    db_session.query(models.TVShow).filter_by(user_id=user.id).delete()
    db_session.commit()
    gone = client.post("/api/week-one/save", headers=headers(user), json={"key": key, "today": today().isoformat()})
    assert gone.status_code == 404


def _reminder(db_session):
    user = member(db_session)
    db_session.add(models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id))
    db_session.commit()
    schedule(db_session, "tv-shows", "Severance", 2022, 2)
    day = today() + timedelta(days=2)
    week_one.set_reminder(db_session, user, day, today(), 0)
    return user, datetime.combine(day, datetime.min.time()) + timedelta(hours=17, minutes=5)


def test_unsubscribing_after_asking_drops_the_reminder(db_session):
    user, on_time = _reminder(db_session)
    db_session.add(models.EmailOptOut(user_id=user.id))  # the footer link of an earlier email
    db_session.commit()
    sent = []

    async def sender(*args):
        sent.append(args)

    result = asyncio.run(week_one.send_due(_session_factory(db_session), now=on_time, sender=sender))
    assert result["dropped"] == 1 and sent == []
    assert week_one.get_row(db_session, user.id).reminder_status == "dropped"


def test_asking_after_unsubscribing_still_sends(db_session):
    user = member(db_session, "later")
    db_session.add(models.EmailOptOut(user_id=user.id, created_at=datetime.utcnow() - timedelta(days=1)))
    db_session.add(models.TVShow(title="Severance", year=2022, watched=False, user_id=user.id))
    db_session.commit()
    schedule(db_session, "tv-shows", "Severance", 2022, 2)
    day = today() + timedelta(days=2)
    week_one.set_reminder(db_session, user, day, today(), 0)
    sent = []

    async def sender(*args):
        sent.append(args)

    on_time = datetime.combine(day, datetime.min.time()) + timedelta(hours=17, minutes=5)
    assert asyncio.run(week_one.send_due(_session_factory(db_session), now=on_time, sender=sender))["sent"] == 1


def test_home_loads_the_new_card_script():
    html = (ROOT / "app/templates/index.html").read_text()
    assert "/static/week-one.js?v=20261118-week-one-3" in html


def test_card_script_skips_established_members_and_offsite_links():
    script = r"""
    global.document = { readyState: 'complete', addEventListener() {}, getElementById() { return null; } };
    global.window = {};
    let user = null;
    global.getUser = () => user;
    const week = require(process.argv[1]);
    const day = 24 * 60 * 60 * 1000;
    const iso = ms => new Date(ms).toISOString().replace('Z', '');
    const out = [];
    user = { created_at: iso(Date.now() - 3 * day) }; out.push(week.pastFirstWeek());
    user = { created_at: iso(Date.now() - 8 * day) }; out.push(week.pastFirstWeek());
    user = { created_at: iso(Date.now() - 30 * day) }; out.push(week.pastFirstWeek());
    user = { created_at: new Date(Date.now() - 30 * day).toISOString() }; out.push(week.pastFirstWeek());
    user = null; out.push(week.pastFirstWeek());
    out.push(week.localPath('/titles/tv/andor-2022'), week.localPath('//evil.example'), week.localPath('/\\evil.example'),
             week.localPath('https://evil.example'));
    console.log(JSON.stringify(out));
    """
    result = subprocess.run(["node", "-e", script, str(ROOT / "app/static/week-one.js")],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "[false,false,true,true,false,true,false,false,false]"
