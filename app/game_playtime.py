"""Real minutes played per library game, kept from Steam imports.

The Import Studio saves a row for each Steam game it adds, and refreshes the
minutes on games that were already in the library (matched by title, only when
exactly one game has that title). The library record itself is never changed.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable, Iterable

from sqlalchemy.orm import Session

from . import models

SOURCES = {"steam"}
MAX_MINUTES = 60 * 24 * 365 * 5


def _key(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().casefold())


def _upsert(db: Session, user_id: int, item_id: int, source: str, external_id: str | None, minutes: int,
            now: datetime, existing: dict[int, models.GamePlaytime]) -> None:
    row = existing.get(item_id)
    if row is None:
        row = models.GamePlaytime(user_id=user_id, item_id=item_id, source=source)
        db.add(row)
        existing[item_id] = row
    row.external_id = external_id
    row.minutes = max(0, min(int(minutes), MAX_MINUTES))
    row.synced_at = now


def save_from_import(db: Session, user_id: int, created: Iterable[tuple[dict[str, Any], Any]],
                     duplicates: Iterable[dict[str, Any]]) -> int:
    """Record Steam minutes for new games and refresh them on matching ones. Caller commits."""
    created = [(item, record) for item, record in created
               if item.get("category") == "video-games" and (item.get("extra") or {}).get("source") in SOURCES]
    duplicates = [item for item in duplicates
                  if item.get("category") == "video-games" and (item.get("extra") or {}).get("source") in SOURCES]
    if not created and not duplicates:
        return 0
    db.flush()  # new records need their ids
    existing = {row.item_id: row for row in db.query(models.GamePlaytime).filter(
        models.GamePlaytime.user_id == user_id, models.GamePlaytime.source == "steam")}
    now = datetime.utcnow()
    saved = 0
    for item, record in created:
        extra = item["extra"]
        _upsert(db, user_id, record.id, extra["source"], extra.get("external_id"), extra.get("minutes", 0), now, existing)
        saved += 1
    if duplicates:
        by_title: dict[str, list[int]] = {}
        for game_id, title in db.query(models.VideoGame.id, models.VideoGame.title).filter(
                models.VideoGame.user_id == user_id):
            by_title.setdefault(_key(title), []).append(game_id)
        for item in duplicates:
            matches = by_title.get(_key(item.get("title") or ""), [])
            if len(matches) != 1:
                continue
            extra = item["extra"]
            _upsert(db, user_id, matches[0], extra["source"], extra.get("external_id"), extra.get("minutes", 0), now, existing)
            saved += 1
    return saved


def refreshable(db: Session, user_id: int, classified: Iterable[dict[str, Any]]) -> int:
    """How many duplicate Steam rows would refresh the hours on a game already in the library."""
    titles = [_key(item.get("title") or "") for item in classified
              if item.get("status") == "duplicate" and item.get("category") == "video-games"
              and (item.get("extra") or {}).get("source") in SOURCES]
    if not titles:
        return 0
    counts: dict[str, int] = {}
    for (title,) in db.query(models.VideoGame.title).filter(models.VideoGame.user_id == user_id):
        counts[_key(title)] = counts.get(_key(title), 0) + 1
    return sum(1 for title in titles if counts.get(title) == 1)


def minutes_by_game(db: Session, user_id: int) -> dict[int, int]:
    return {item_id: minutes for item_id, minutes in db.query(
        models.GamePlaytime.item_id, models.GamePlaytime.minutes).filter(models.GamePlaytime.user_id == user_id)}


def export_rows(db: Session, user_id: int, identity: Callable[[str, Any], dict] | None = None) -> list[dict]:
    """One row per game with playtime, named by title so a backup can be restored elsewhere."""
    games = {game.id: game for game in db.query(models.VideoGame).filter(models.VideoGame.user_id == user_id)}
    rows = []
    for row in db.query(models.GamePlaytime).filter(models.GamePlaytime.user_id == user_id).order_by(
            models.GamePlaytime.minutes.desc(), models.GamePlaytime.id):
        game = games.get(row.item_id)
        if game is None:
            continue
        entry = {"title": game.title, "source": row.source, "external_id": row.external_id,
                 "minutes": row.minutes, "synced_at": row.synced_at.isoformat() if row.synced_at else None}
        if identity is not None:
            entry.update(identity(game, "video-games"))
        rows.append(entry)
    return rows
