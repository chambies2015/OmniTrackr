"""Old Site stats source labels written by scanners are folded into the "(unreadable tag)" row."""
from datetime import date

import pytest
from sqlalchemy import create_engine, text

from app import migrations, site_traffic
from app.database import Base

PROBE = "'>\"></script><svg/onload=confirm('xsss-utm_source18')>"


@pytest.fixture
def traffic_engine(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'traffic.db').as_posix()}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(migrations, "engine", engine)
    yield engine
    engine.dispose()


def _insert(engine, rows):
    with engine.connect() as conn:
        for day, kind, key, count in rows:
            conn.execute(text("INSERT INTO site_traffic_daily (day, kind, key, count) VALUES (:day, :kind, :key, :count)"),
                         {"day": day, "kind": kind, "key": key, "count": count})
        conn.commit()


def _rows(engine):
    with engine.connect() as conn:
        found = conn.execute(text("SELECT day, kind, key, count FROM site_traffic_daily ORDER BY day, kind, key")).fetchall()
    return {(str(day), kind, key): count for day, kind, key, count in found}


def test_probe_labels_move_into_the_unreadable_row_and_keep_their_counts(traffic_engine):
    day, other = date(2026, 10, 29), date(2026, 10, 30)
    _insert(traffic_engine, [
        (day, "source", PROBE, 3),
        (day, "source", "<img src=x onerror=alert(1)>", 2),
        (day, "source", site_traffic.BAD_TAG, 1),
        (day, "source", "google.com", 40),
        (day, "source", "(direct)", 12),
        (day, "human_source", PROBE, 1),
        (other, "source", "news.ycombinator.com", 5),
        (other, "page", "/u/someone/match?x=<script>", 7),
    ])

    migrations.fold_unreadable_traffic_sources()
    rows = _rows(traffic_engine)

    assert rows[(str(day), "source", site_traffic.BAD_TAG)] == 6
    assert rows[(str(day), "human_source", site_traffic.BAD_TAG)] == 1
    assert rows[(str(day), "source", "google.com")] == 40
    assert rows[(str(day), "source", "(direct)")] == 12
    assert rows[(str(other), "source", "news.ycombinator.com")] == 5
    # Page paths are a different kind and are left alone.
    assert rows[(str(other), "page", "/u/someone/match?x=<script>")] == 7
    assert not any("<" in key for (_, kind, key) in rows if kind in ("source", "human_source"))


def test_fold_is_idempotent_and_quiet_without_the_table(traffic_engine, tmp_path, monkeypatch):
    _insert(traffic_engine, [(date(2026, 10, 29), "source", PROBE, 2)])
    migrations.fold_unreadable_traffic_sources()
    migrations.fold_unreadable_traffic_sources()
    assert _rows(traffic_engine) == {("2026-10-29", "source", site_traffic.BAD_TAG): 2}

    empty = create_engine(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    monkeypatch.setattr(migrations, "engine", empty)
    migrations.fold_unreadable_traffic_sources()  # no table: nothing to do, no error


@pytest.mark.parametrize("label, unreadable", [
    (PROBE, True), ("javascript:alert(1)", True), ("a=b", True), ("x;y", True),
    ("newsletter", False), ("google.com", False), ("my site.co.uk", False), ("(direct)", False),
    (site_traffic.BAD_TAG, False), ("", False),
])
def test_which_labels_count_as_unreadable(label, unreadable):
    assert migrations.unreadable_traffic_source(label, site_traffic.BAD_TAG) is unreadable
