"""Regression tests for the Oct 29 sweep of the exports, tags and episode calendar."""
import io
import zipfile
from datetime import datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import event

from app import episode_calendar, models, release_calendar
from tests.test_library_export import owner, rows


def test_ics_drops_a_url_that_could_start_a_new_property():
    event_ = {"uid": "x@omnitrackr.xyz", "date": "2026-11-01", "summary": "Show", "description": "",
              "url": "https://www.tvmaze.com/shows/1\r\nATTENDEE:mailto:someone@example.com"}
    body = release_calendar.build_ics("Feed", "", [event_])
    assert "ATTENDEE" not in body
    assert "URL:" not in body
    event_["url"] = "https://www.tvmaze.com/shows/1/severance"
    assert "URL:https://www.tvmaze.com/shows/1/severance" in release_calendar.build_ics("Feed", "", [event_])


def test_stale_check_reads_the_cache_in_one_query(authenticated_client, db_session):
    user = owner(db_session)
    db_session.add_all([models.TVShow(user_id=user.id, title=f"Show {n}", year=2020) for n in range(12)])
    db_session.commit()
    fresh = episode_calendar.airing_key("tv-shows", "Show 0", 2020)
    old = episode_calendar.airing_key("tv-shows", "Show 1", 2020)
    db_session.add_all([
        models.TitleMetadata(key=fresh, status="ok", data="{}", fetched_at=datetime.utcnow()),
        models.TitleMetadata(key=old, status="ok", data="{}", fetched_at=datetime.utcnow() - timedelta(days=2)),
    ])
    db_session.commit()
    statements = []
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(db_session.get_bind(), "before_cursor_execute", listener)
    try:
        wanted = episode_calendar._stale_shows(db_session, [user.id])
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", listener)
    assert len([sql for sql in statements if "title_metadata" in sql]) == 1
    titles = {title for _, title, _ in wanted}
    assert "Show 0" not in titles and "Show 1" in titles and len(titles) == 11


def test_only_a_few_member_refreshes_run_at_once(monkeypatch):
    monkeypatch.setattr(episode_calendar, "enabled_for_process", lambda: True)
    monkeypatch.setattr(episode_calendar, "_queued", {1, 2, 3})
    app = SimpleNamespace(state=SimpleNamespace(external_api_client=object()))
    episode_calendar.queue_member(app, 4)
    assert episode_calendar._queued == {1, 2, 3}


def test_spreadsheet_export_includes_tags_and_quotes_formula_headers(authenticated_client, db_session):
    user = owner(db_session)
    movie = models.Movie(user_id=user.id, title="Arrival", director="Denis Villeneuve", year=2016)
    db_session.add(movie)
    db_session.commit()
    assert authenticated_client.put(f"/library/tags/movies/{movie.id}", json={"tags": ["=cmd", "cozy"]}).status_code == 200
    tab = authenticated_client.post("/custom-tabs/", json={
        "name": "Board Games", "source_type": "none", "allow_uploads": False,
        "fields": [{"key": "players", "label": "=1+1", "field_type": "text", "required": False, "order": 0}],
    })
    assert tab.status_code in (200, 201), tab.text
    archive = zipfile.ZipFile(io.BytesIO(authenticated_client.get("/export/spreadsheet/").content))
    tags = rows(archive.read("tags.csv").decode("utf-8"))
    assert sorted(row["tag"] for row in tags) == ["'=cmd", "cozy"]
    assert {row["title"] for row in tags} == {"Arrival"}
    header = archive.read("custom-tabs/board-games.csv").decode("utf-8").lstrip("﻿").splitlines()[0]
    assert header == "title,'=1+1,poster_url"
