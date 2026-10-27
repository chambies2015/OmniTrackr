"""Episode guides for TV shows and anime, built on the private progress checkpoint.

A member's place in a show stays the single ``ProgressCheckpoint`` row it has
always been: nothing here adds per-member storage. This module only adds:

* a shared, cached season layout (episodes per season) from TVmaze for TV and
  MyAnimeList (via Jikan) for anime, kept in ``title_metadata`` under its own
  ``episodes:`` keys so the title-page cache is untouched;
* a fallback layout from the episode count the member typed themselves;
* the arithmetic that turns "Season 2, episode 4" into a progress bar and the
  next episode to watch.
"""
from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from . import models, title_metadata
from .title_pages import normalize

KINDS = {"tv-shows": "tv", "anime": "anime"}
FRESH = {"ok": timedelta(days=7), "miss": timedelta(days=3), "error": timedelta(hours=6)}
MAX_SEASONS = 80
MAX_SEASON_EPISODES = 3000


def layout_key(category: str, title: str, year: Optional[int]) -> str:
    return "episodes:" + title_metadata.cache_key(KINDS[category], normalize(title), year)


def _clean(seasons) -> list[dict]:
    """Keep only sane, numbered regular seasons, in order."""
    result = {}
    for season in seasons if isinstance(seasons, list) else []:
        if not isinstance(season, dict):
            continue
        number, episodes = season.get("number"), season.get("episodes")
        if (type(number) is int and 1 <= number <= 10000 and type(episodes) is int
                and 0 < episodes <= MAX_SEASON_EPISODES and number not in result):
            result[number] = episodes
    return [{"number": number, "episodes": result[number]} for number in sorted(result)[:MAX_SEASONS]]


# ---------------------------------------------------------------- sources

async def tvmaze_layout(client, title: str, year: Optional[int]) -> list[dict]:
    results = await title_metadata._get_json(client, "https://api.tvmaze.com/search/shows", {"q": title}) or []
    show = None
    for result in results[:8]:
        candidate = result.get("show") or {}
        premiered = candidate.get("premiered") or ""
        if title_metadata._title_matches(title, candidate.get("name", "")) and (
                not year or premiered.startswith(str(year)) or not premiered):
            show = candidate
            break
    if not show or type(show.get("id")) is not int:
        return []
    episodes = await title_metadata._get_json(client, f"https://api.tvmaze.com/shows/{show['id']}/episodes") or []
    counts: dict[int, int] = {}
    for episode in episodes if isinstance(episodes, list) else []:
        season, number = episode.get("season"), episode.get("number")
        # Specials carry no episode number and stay out of the season grid.
        if type(season) is int and type(number) is int and season >= 1:
            counts[season] = counts.get(season, 0) + 1
    return _clean([{"number": season, "episodes": count} for season, count in counts.items()])


async def jikan_layout(client, title: str, year: Optional[int]) -> list[dict]:
    data = await title_metadata._get_json(client, "https://api.jikan.moe/v4/anime", {"q": title, "limit": 6}) or {}
    for result in data.get("data", []) if isinstance(data, dict) else []:
        names = [result.get("title"), result.get("title_english")] + [t.get("title") for t in result.get("titles") or []]
        aired = ((result.get("aired") or {}).get("from") or "")[:4]
        if any(title_metadata._title_matches(title, name or "") for name in names) and (not year or aired == str(year) or not aired):
            return _clean([{"number": 1, "episodes": result.get("episodes")}])
    return []


SOURCES = {"tv-shows": (tvmaze_layout, "TVmaze", "https://www.tvmaze.com/"),
           "anime": (jikan_layout, "MyAnimeList", "https://myanimelist.net/")}


# ---------------------------------------------------------------- cache

def _decode(data: Optional[dict]) -> list[dict]:
    return _clean((data or {}).get("seasons"))


def cached_layouts(db: Session, keys: list[str]) -> dict[str, list[dict]]:
    """Batch-read cached layouts for list views. Never touches the network."""
    keys = list(dict.fromkeys(keys))
    found = {}
    for start in range(0, len(keys), 500):
        rows = db.query(models.TitleMetadata.key, models.TitleMetadata.data).filter(
            models.TitleMetadata.key.in_(keys[start:start + 500]),
            models.TitleMetadata.status == "ok",
        ).all()
        for key, data in rows:
            try:
                seasons = _decode(json.loads(data) if data else None)
            except ValueError:
                seasons = []
            if seasons:
                found[key] = seasons
    return found


_locks: dict[str, asyncio.Lock] = {}


async def get_or_fetch_layout(db: Session, client, category: str, title: str, year: Optional[int],
                              wait: float = 6.0) -> list[dict]:
    key = layout_key(category, title, year)
    data, fresh = await run_in_threadpool(title_metadata.cached, db, key, FRESH)
    if fresh or client is None:
        return _decode(data)
    lock = _locks.setdefault(key, asyncio.Lock())
    if lock.locked():
        return _decode(data)
    async with lock:
        await run_in_threadpool(db.rollback)
        fetch = SOURCES[category][0]
        try:
            seasons = await asyncio.wait_for(fetch(client, " ".join(title.split()), year), timeout=wait)
            await run_in_threadpool(title_metadata.store, db, key, {"seasons": seasons} if seasons else None,
                                    "ok" if seasons else "miss")
            return seasons or _decode(data)
        except Exception:
            await run_in_threadpool(title_metadata.store, db, key, None, "error")
            return _decode(data)
        finally:
            _locks.pop(key, None)


# ---------------------------------------------------------------- arithmetic

def layout_for(item, category: str, fetched: list[dict]) -> dict:
    """The season grid to show: the fetched layout, else the member's own episode count."""
    if fetched:
        return {"seasons": fetched, "source": SOURCES[category][1], "source_url": SOURCES[category][2]}
    episodes = getattr(item, "episodes", None)
    if type(episodes) is int and 0 < episodes <= MAX_SEASON_EPISODES:
        seasons = getattr(item, "seasons", None)
        # One season numbers as Season 1; several seasons with only a total
        # count, and anime in general, number continuously.
        number = 1 if category == "tv-shows" and (seasons is None or seasons <= 1) else None
        return {"seasons": [{"number": number, "episodes": episodes}], "source": None, "source_url": None}
    return {"seasons": [], "source": None, "source_url": None}


def _continuous(seasons: list[dict]) -> bool:
    return len(seasons) == 1 and seasons[0]["number"] is None


def absolute(seasons: list[dict], season: Optional[int], position: Optional[int]) -> Optional[int]:
    """How many regular episodes a checkpoint covers, or None when it can't be placed."""
    if position is None:
        return 0
    if season is None:
        return position
    if season == 0:
        return None
    if not seasons or _continuous(seasons):
        return position if season == 1 else None
    offset = 0
    for entry in seasons:
        if entry["number"] >= season:
            break
        offset += entry["episodes"]
    return offset + position


def locate(seasons: list[dict], index: int) -> Optional[tuple]:
    """The (season, episode) of the index-th regular episode, 1-based."""
    for entry in seasons:
        if index <= entry["episodes"]:
            return entry["number"], index
        index -= entry["episodes"]
    return None


def next_episode(seasons: list[dict], season: Optional[int], position: Optional[int]) -> Optional[tuple]:
    """The episode after a checkpoint. None means the member is caught up."""
    if position is None:
        return (seasons[0]["number"], 1) if seasons else (None, 1)
    if season == 0:
        return 0, position + 1
    if not seasons:
        return season, position + 1
    if _continuous(seasons):
        if season not in (None, 1):
            return season, position + 1
        return (season, position + 1) if position < seasons[0]["episodes"] else None
    if season is None:
        return locate(seasons, position + 1)
    for index, entry in enumerate(seasons):
        if entry["number"] == season:
            if position < entry["episodes"]:
                return season, position + 1
            return (seasons[index + 1]["number"], 1) if index + 1 < len(seasons) else None
    # A season the layout doesn't know yet (newer than the cache, or a gap).
    return season, position + 1


def summarize(layout: dict, checkpoint) -> dict:
    """Progress numbers for one show from its layout and checkpoint (model or None)."""
    seasons = layout["seasons"]
    active = checkpoint is not None and checkpoint.unit == "episode" and checkpoint.position
    season = checkpoint.season if active else None
    position = checkpoint.position if active else None
    total = sum(entry["episodes"] for entry in seasons) or None
    watched = absolute(seasons, season, position)
    upcoming = next_episode(seasons, season, position)
    percent = None
    if total and watched is not None:
        percent = max(0, min(100, round(100 * watched / total)))
    return {
        "total": total,
        "watched": watched,
        "percent": percent,
        "season_count": len([entry for entry in seasons if entry["number"] is not None]),
        "current": {"season": season, "episode": position} if active else None,
        "next": {"season": upcoming[0], "episode": upcoming[1]} if upcoming else None,
        "caught_up": bool(active) and upcoming is None,
        "revision": checkpoint.revision if checkpoint is not None else 0,
    }


def progress_map(db: Session, user_id: int, category: str, items) -> dict:
    """Episode progress for owned list items, keyed by item id. Cache-only and batched.

    Cleared checkpoints are read too: their revision is what the next write expects.
    """
    items = list(items)
    if category not in KINDS or not items:
        return {}
    keys = {item.id: layout_key(category, item.title or "", item.year) for item in items}
    layouts = cached_layouts(db, list(keys.values()))
    checkpoints = {}
    ids = list(keys)
    for start in range(0, len(ids), 500):
        for entry in db.query(models.ProgressCheckpoint).filter(
            models.ProgressCheckpoint.user_id == user_id,
            models.ProgressCheckpoint.category == category,
            models.ProgressCheckpoint.item_id.in_(ids[start:start + 500]),
        ):
            checkpoints[entry.item_id] = entry
    return {
        item.id: summarize(layout_for(item, category, layouts.get(keys[item.id], [])), checkpoints.get(item.id))
        for item in items
    }


def attach(db: Session, user_id: int, entries: list[dict], id_key: str = "id") -> None:
    """Add ``episode_progress`` to serialized dashboard entries for owned shows and anime."""
    models_by_category = {"tv-shows": models.TVShow, "anime": models.Anime}
    wanted: dict[str, set] = {}
    for entry in entries:
        if entry.get("category") in models_by_category and type(entry.get(id_key)) is int:
            wanted.setdefault(entry["category"], set()).add(entry[id_key])
    for category, ids in wanted.items():
        model = models_by_category[category]
        items = db.query(model).filter(model.user_id == user_id, model.id.in_(ids)).all()
        found = progress_map(db, user_id, category, items)
        for entry in entries:
            if entry.get("category") == category and entry.get(id_key) in found:
                entry["episode_progress"] = found[entry[id_key]]
