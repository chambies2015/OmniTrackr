"""Weekly episode air dates for a member's private release calendar.

The private calendar (``release_calendar``) lists premieres, new seasons and
sequels from Release Radar. Members can also ask for every new episode of the
TV shows and anime they haven't marked as watched. Those dates come from TVmaze
(TV) and AniList (anime) and are cached per show in ``title_metadata`` under
``airing:`` keys, shared by everyone who tracks the same show.

Calendar apps poll the feed often, so a feed request only ever reads that cache.
A background sweep refreshes the shows of members who have episodes turned on,
and turning the option on queues that member's shows straight away.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from . import models, title_metadata
from .digest import app_url
from .for_you import normalize_title
from .title_pages import normalize, title_path

PAST_DAYS = 7
AHEAD_DAYS = 60
MAX_EPISODES_PER_SHOW = 40
MEMBER_SHOWS = 60
MEMBER_EPISODE_LIMIT = 300
DEFAULT_MINUTES = 30
FRESH = {"ok": timedelta(hours=20), "ended": timedelta(days=14), "miss": timedelta(days=10), "error": timedelta(hours=6)}
SWEEP_EVERY_SECONDS = 1800
SWEEP_BATCH = 120
FIRST_SWEEP_DELAY_SECONDS = 300
PAUSE = {"tv-shows": 1.0, "anime": 2.5}  # TVmaze allows ~20 calls / 10 s; AniList is slower.
MODELS = {"tv-shows": models.TVShow, "anime": models.Anime}
PAGE_KIND = {"tv-shows": "tv", "anime": "anime"}
PRIVATE_FLAG = {"tv-shows": "tv_shows_private", "anime": "anime_private"}
SOURCES = {"tv-shows": "TVmaze", "anime": "AniList"}
GENERIC_NAME = re.compile(r"^(episode|ep\.?)\s*\d+$", re.IGNORECASE)
ANILIST_QUERY = """
query ($q: String) {
  Page(perPage: 6) {
    media(search: $q, type: ANIME, sort: SEARCH_MATCH) {
      id siteUrl status duration synonyms
      title { romaji english }
      startDate { year }
      airingSchedule(notYetAired: true, perPage: 30) { nodes { episode airingAt } }
    }
  }
}
"""


def enabled_for_process() -> bool:
    if os.getenv("EPISODE_CALENDAR", "").strip().lower() in ("off", "0", "false", "no"):
        return False
    return os.getenv("TESTING", "").lower() != "true"


def airing_key(category: str, title: str, year: Optional[int]) -> str:
    return "airing:" + title_metadata.cache_key(PAGE_KIND[category], normalize(title), year)


# ---------------------------------------------------------------- sources

def _clean_text(value, limit: int = 200) -> str:
    return " ".join(str(value or "").split())[:limit]


def _in_window(day: date, today: date) -> bool:
    return today - timedelta(days=PAST_DAYS) <= day <= today + timedelta(days=AHEAD_DAYS)


def tvmaze_episodes(show: dict, episodes: list, today: date) -> dict:
    """The cached shape for one TVmaze show: its upcoming (and last week's) episodes."""
    found = []
    for episode in episodes if isinstance(episodes, list) else []:
        if not isinstance(episode, dict):
            continue
        number, season = episode.get("number"), episode.get("season")
        try:
            day = date.fromisoformat(episode.get("airdate") or "")
        except ValueError:
            continue
        if type(number) is not int or type(season) is not int or season < 1 or not _in_window(day, today):
            continue
        start = None
        # Streaming drops often have no air time; those stay all-day events.
        if episode.get("airtime") and episode.get("airstamp"):
            try:
                stamp = datetime.fromisoformat(episode["airstamp"].replace("Z", "+00:00"))
                start = stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except (ValueError, AttributeError):
                start = None
        runtime = episode.get("runtime")
        name = _clean_text(episode.get("name"))
        found.append({
            "season": season, "number": number,
            "name": "" if GENERIC_NAME.match(name) else name,
            "date": day.isoformat(), "start": start,
            "minutes": runtime if type(runtime) is int and 0 < runtime <= 600 else None,
        })
    found.sort(key=lambda e: (e["date"], e["season"], e["number"]))
    network = (show.get("network") or {}).get("name") or (show.get("webChannel") or {}).get("name")
    return {
        "source": "TVmaze",
        "source_id": show.get("id"),
        "source_url": show.get("url") if str(show.get("url") or "").startswith("https://www.tvmaze.com/") else None,
        "show": _clean_text(show.get("name")),
        "network": _clean_text(network, 80),
        "ended": show.get("status") == "Ended" and not found,
        "episodes": found[:MAX_EPISODES_PER_SHOW],
    }


async def fetch_tv(client, title: str, year: Optional[int], today: date) -> Optional[dict]:
    results = await title_metadata._get_json(client, "https://api.tvmaze.com/search/shows", {"q": title}) or []
    show = None
    for result in results[:8] if isinstance(results, list) else []:
        candidate = (result or {}).get("show") or {}
        premiered = candidate.get("premiered") or ""
        if title_metadata._title_matches(title, candidate.get("name", "")) and (
                not year or premiered.startswith(str(year)) or not premiered):
            show = candidate
            break
    if not show or type(show.get("id")) is not int:
        return None
    await asyncio.sleep(PAUSE["tv-shows"])
    episodes = await title_metadata._get_json(client, f"https://api.tvmaze.com/shows/{show['id']}/episodes")
    if episodes is None:
        raise RuntimeError("TVmaze episode list unavailable")
    return tvmaze_episodes(show, episodes, today)


def anilist_episodes(media: dict, today: date) -> dict:
    found = []
    minutes = media.get("duration") if type(media.get("duration")) is int and 0 < media["duration"] <= 600 else None
    for node in ((media.get("airingSchedule") or {}).get("nodes") or []):
        if not isinstance(node, dict) or type(node.get("episode")) is not int or type(node.get("airingAt")) is not int:
            continue
        stamp = datetime.fromtimestamp(node["airingAt"], tz=timezone.utc)
        if not _in_window(stamp.date(), today):
            continue
        found.append({"season": None, "number": node["episode"], "name": "", "date": stamp.date().isoformat(),
                      "start": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"), "minutes": minutes})
    found.sort(key=lambda e: (e["date"], e["number"]))
    title = media.get("title") or {}
    site = media.get("siteUrl") or ""
    return {
        "source": "AniList",
        "source_id": media.get("id"),
        "source_url": site if site.startswith("https://anilist.co/") else None,
        "show": _clean_text(title.get("english") or title.get("romaji")),
        "network": "",
        "ended": media.get("status") in ("FINISHED", "CANCELLED") and not found,
        "episodes": found[:MAX_EPISODES_PER_SHOW],
    }


async def fetch_anime(client, title: str, year: Optional[int], today: date) -> Optional[dict]:
    response = await client.post("https://graphql.anilist.co", json={"query": ANILIST_QUERY, "variables": {"q": title}},
                                 headers=title_metadata.HEADERS,
                                 timeout=title_metadata.TIMEOUT)
    if response.status_code != 200:
        raise RuntimeError(f"AniList answered {response.status_code}")
    media_list = (((response.json() or {}).get("data") or {}).get("Page") or {}).get("media") or []
    matches = []
    for media in media_list if isinstance(media_list, list) else []:
        if not isinstance(media, dict) or type(media.get("id")) is not int:
            continue
        names = [(media.get("title") or {}).get("english"), (media.get("title") or {}).get("romaji"),
                 *(media.get("synonyms") or [])]
        if any(title_metadata._title_matches(title, name or "") for name in names):
            matches.append(media)
    # Anime splits seasons into separate entries, so a member tracking "Jujutsu Kaisen"
    # wants the season airing now, whatever year the first one started.
    for media in matches:
        if media.get("status") in ("RELEASING", "NOT_YET_RELEASED") and (media.get("airingSchedule") or {}).get("nodes"):
            return anilist_episodes(media, today)
    for media in matches:
        started = (media.get("startDate") or {}).get("year")
        if not year or type(started) is not int or abs(started - year) <= 1:
            return anilist_episodes(media, today)
    return None


FETCHERS = {"tv-shows": fetch_tv, "anime": fetch_anime}


# ---------------------------------------------------------------- cache

def _status_of(data: Optional[dict]) -> str:
    if data is None:
        return "miss"
    return "ended" if data.get("ended") else "ok"


def stale(db: Session, key: str) -> bool:
    row = db.query(models.TitleMetadata.status, models.TitleMetadata.fetched_at).filter_by(key=key).first()
    if row is None:
        return True
    return datetime.utcnow() - row.fetched_at >= FRESH.get(row.status, FRESH["error"])


async def refresh_show(db: Session, client, category: str, title: str, year: Optional[int], today: date) -> None:
    key = airing_key(category, title, year)
    try:
        data = await FETCHERS[category](client, " ".join(title.split()), year, today)
    except asyncio.CancelledError:
        raise
    except Exception:
        await run_in_threadpool(title_metadata.store, db, key, None, "error")
        return
    await run_in_threadpool(title_metadata.store, db, key, data, _status_of(data))


def cached_schedules(db: Session, keys: list[str]) -> dict[str, dict]:
    """Batch-read cached schedules. Never touches the network."""
    keys = list(dict.fromkeys(keys))
    found = {}
    for start in range(0, len(keys), 500):
        rows = db.query(models.TitleMetadata.key, models.TitleMetadata.data).filter(
            models.TitleMetadata.key.in_(keys[start:start + 500]),
            models.TitleMetadata.status.in_(("ok", "ended")),
        ).all()
        for key, data in rows:
            try:
                parsed = json.loads(data) if data else None
            except ValueError:
                parsed = None
            if isinstance(parsed, dict):
                found[key] = parsed
    return found


# ---------------------------------------------------------------- a member's shows

def member_shows(db: Session, user_id: int) -> list[tuple[str, object]]:
    """(category, item) for unfinished shows, the ones with saved progress first, then the newest."""
    shows = []
    for category, model in MODELS.items():
        started = {item_id for item_id, in db.query(models.ProgressCheckpoint.item_id).filter(
            models.ProgressCheckpoint.user_id == user_id,
            models.ProgressCheckpoint.category == category,
            models.ProgressCheckpoint.position.isnot(None),
        )}
        rows = db.query(model).filter(
            model.user_id == user_id, or_(model.watched == False, model.watched.is_(None)),  # noqa: E712
        ).all()
        for item in rows:
            if (item.title or "").strip():
                added = item.added_at or datetime.min
                shows.append(((item.id in started), added, item.id, category, item))
    shows.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    seen, result = set(), []
    for *_, category, item in shows:
        key = airing_key(category, item.title, item.year)
        if key not in seen:
            seen.add(key)
            result.append((category, item))
    return result[:MEMBER_SHOWS]


def _event(category: str, item, schedule: dict, episode: dict, link: str) -> dict:
    title = schedule.get("show") or (item.title or "").strip()
    season, number = episode.get("season"), episode["number"]
    if category == "tv-shows" and season:
        code = f"S{season}E{number}"
        summary = f"{title} {code}" + (f": {episode['name']}" if episode.get("name") else "")
        what = f"Season {season}, episode {number}" + (f": {episode['name']}" if episode.get("name") else "")
        uid = f"ep-tvm-{schedule.get('source_id')}-s{season}e{number}@omnitrackr.xyz"
    else:
        summary = f"{title} episode {number}"
        what = f"Episode {number}"
        uid = f"ep-al-{schedule.get('source_id')}-e{number}@omnitrackr.xyz"
    lines = [f"New episode of a show on your OmniTrackr list. {what}."]
    if schedule.get("network"):
        lines.append(f"On {schedule['network']}.")
    lines += [
        "",
        f"Mark your progress on OmniTrackr: {link}",
        f"Air dates come from {schedule.get('source') or SOURCES[category]} and can move. "
        "Your calendar picks up changes on its next refresh.",
    ]
    event = {"uid": uid, "date": episode["date"], "summary": summary, "description": "\n".join(lines), "url": link}
    if episode.get("start"):
        event["start"] = episode["start"]
        event["minutes"] = episode.get("minutes") or DEFAULT_MINUTES
    return event


def member_episode_events(db: Session, user: models.User, today: date,
                          skip: Iterable[tuple[str, str]] = ()) -> list[dict]:
    """Episode events for a member's unfinished shows, from the cache only.

    ``skip`` holds (normalized title, date) pairs the feed already has as a
    Release Radar premiere, so a season opener isn't listed twice.
    """
    skip = set(skip)
    shows = member_shows(db, user.id)
    schedules = cached_schedules(db, [airing_key(category, item.title, item.year) for category, item in shows])
    base = app_url()
    events, seen = [], set()
    for category, item in shows:
        schedule = schedules.get(airing_key(category, item.title, item.year))
        if not schedule or schedule.get("source_id") is None:
            continue
        if getattr(user, PRIVATE_FLAG[category], False):
            link = schedule.get("source_url") or f"{base}/"
        else:
            link = f"{base}{title_path(PAGE_KIND[category], item.title, item.year)}"
        for episode in schedule.get("episodes") or []:
            if not isinstance(episode, dict) or type(episode.get("number")) is not int:
                continue
            try:
                day = date.fromisoformat(episode.get("date") or "")
            except ValueError:
                continue
            if not _in_window(day, today) or any((normalize_title(name), episode["date"]) in skip
                                                  for name in (item.title, schedule.get("show") or "")):
                continue
            event = _event(category, item, schedule, episode, link)
            if event["uid"] not in seen:
                seen.add(event["uid"])
                events.append(event)
    events.sort(key=lambda e: (e.get("start") or e["date"], e["summary"].lower()))
    return events[:MEMBER_EPISODE_LIMIT]


def upcoming_count(db: Session, user: models.User, today: date) -> int:
    """How many episodes in the next two weeks the feed will list (for the settings panel)."""
    soon = (today + timedelta(days=14)).isoformat()
    return sum(1 for event in member_episode_events(db, user, today) if today.isoformat() <= event["date"] <= soon)


# ---------------------------------------------------------------- refreshing

def _subscribers(db: Session) -> list[int]:
    return [user_id for user_id, in db.query(models.CalendarFeed.user_id).join(
        models.User, models.User.id == models.CalendarFeed.user_id).filter(
        models.CalendarFeed.include_episodes == True,  # noqa: E712
        models.User.is_active == True,  # noqa: E712
    ).all()]


def _stale_shows(db: Session, user_ids: list[int]) -> list[tuple[str, str, Optional[int]]]:
    wanted, seen = [], set()
    for user_id in user_ids:
        for category, item in member_shows(db, user_id):
            key = airing_key(category, item.title, item.year)
            if key in seen:
                continue
            seen.add(key)
            if stale(db, key):
                wanted.append((category, item.title, item.year))
    return wanted


async def refresh_members(session_factory, client, user_ids: Optional[list[int]] = None,
                          batch: int = SWEEP_BATCH, today: Optional[date] = None) -> int:
    """Refresh stale schedules for the given members (every subscriber when None)."""
    db = session_factory()
    fetched = 0
    try:
        ids = user_ids if user_ids is not None else await run_in_threadpool(_subscribers, db)
        shows = await run_in_threadpool(_stale_shows, db, ids)
        for category, title, year in shows[:batch]:
            await refresh_show(db, client, category, title, year, today or datetime.utcnow().date())
            fetched += 1
            await asyncio.sleep(PAUSE[category])
    finally:
        db.close()
    return fetched


_queued: set[int] = set()
_tasks: set = set()


def queue_member(app, user_id: int) -> None:
    """Fetch one member's schedules soon, so their first calendar sync isn't empty.

    Safe to call from a threadpool request: the work is handed to the server's loop.
    """
    client = getattr(app.state, "external_api_client", None)
    if client is None or user_id in _queued or not enabled_for_process():
        return
    from . import release_radar
    from .database import SessionLocal

    async def run():
        try:
            await refresh_members(SessionLocal, client, [user_id], batch=MEMBER_SHOWS)
        except Exception as error:
            print(f"Episode calendar refresh failed: {error}")
        finally:
            _queued.discard(user_id)

    def start():
        task = asyncio.get_running_loop().create_task(run())
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)

    _queued.add(user_id)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = release_radar._event_loop
        if loop is not None and loop.is_running() and not loop.is_closed():
            loop.call_soon_threadsafe(start)
        else:
            _queued.discard(user_id)
        return
    start()


async def sweep_loop(app) -> None:
    from .database import SessionLocal
    await asyncio.sleep(FIRST_SWEEP_DELAY_SECONDS)
    while True:
        try:
            client = getattr(app.state, "external_api_client", None)
            if client is not None:
                await refresh_members(SessionLocal, client)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"Episode calendar sweep failed: {error}")
        await asyncio.sleep(SWEEP_EVERY_SECONDS)
