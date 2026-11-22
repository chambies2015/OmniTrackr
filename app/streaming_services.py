"""On your services: what on a member's list they can stream on the services they have (Nov 2026).

A member picks the streaming services they pay for, or use free, once. The home card then lists the
films, shows and anime they haven't finished that are streaming on one of them, newest arrivals
first, and each of those three libraries gets an "On my services" filter. When something on their
list arrives on one of their services, they get one bell note (pushed to devices with the "On your
services" switch on) and a line in the weekly email.

Availability comes from where_to_watch's cache: TMDB watch providers (data from JustWatch), the
service a show was made for on TVmaze, and an anime's official streams on MyAnimeList. A background
job keeps that cache fresh for unfinished titles on these members' lists, a few dozen titles every
half hour, and then compares each refreshed title with what it was on before.

``service_sightings`` keeps, per title and service, when it was first and last seen there. The first
time a title is compared sets a baseline: whatever it is already on is not news. After that, a
service that appears is an arrival. A title that drops off a service and is back within two weeks
was most likely a source that failed for a week, so it doesn't count as arriving again.

The services a member picks are private and are never shown to anyone else. Counters go into
``site_traffic_daily`` under kind "stream" and name no member.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, title_metadata, title_pages, where_to_watch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- the services

# (id, name, free to watch, names the sources use for it once _clean has tidied them)
SERVICES = (
    ("netflix", "Netflix", False, ("netflix",)),
    ("prime", "Prime Video", False, ("amazon prime video", "prime video", "amazon prime", "amazon prime video free")),
    ("hbomax", "HBO Max", False, ("hbo max", "max")),
    ("disney", "Disney+", False, ("disney plus",)),
    ("hulu", "Hulu", False, ("hulu",)),
    ("apple", "Apple TV", False, ("apple tv plus", "apple tv")),
    ("peacock", "Peacock", False, ("peacock",)),
    ("paramount", "Paramount+", False, ("paramount plus", "paramount plus with showtime")),
    ("crunchyroll", "Crunchyroll", False, ("crunchyroll",)),
    ("hidive", "HIDIVE", False, ("hidive",)),
    ("starz", "Starz", False, ("starz",)),
    ("mgm", "MGM+", False, ("mgm plus",)),
    ("amc", "AMC+", False, ("amc plus",)),
    ("shudder", "Shudder", False, ("shudder",)),
    ("criterion", "Criterion Channel", False, ("criterion channel", "the criterion channel")),
    ("mubi", "MUBI", False, ("mubi",)),
    ("britbox", "BritBox", False, ("britbox",)),
    ("acorn", "Acorn TV", False, ("acorn tv", "acorntv")),
    ("tubi", "Tubi", True, ("tubi", "tubi tv")),
    ("pluto", "Pluto TV", True, ("pluto tv",)),
    ("roku", "The Roku Channel", True, ("the roku channel", "roku channel")),
    ("plex", "Plex", True, ("plex", "plex channel")),
    ("kanopy", "Kanopy", True, ("kanopy",)),
    ("hoopla", "Hoopla", True, ("hoopla",)),
)
SERVICE_IDS = tuple(service[0] for service in SERVICES)
NAMES = {service[0]: service[1] for service in SERVICES}
ALIASES = {alias: service[0] for service in SERVICES for alias in service[3]}
ORDER = {service_id: index for index, service_id in enumerate(SERVICE_IDS)}
MAX_PICKED = len(SERVICES)

# Where-to-watch groups that mean "you can watch it there with what you already have".
# Rent and Buy cost extra, and "Originally aired on" is a TV network, so neither counts.
STREAM_GROUPS = {"Stream", "Free", "Free with ads", "Official streams", "Made for"}

_CHANNEL = re.compile(r"\s+(?:amazon channel|apple tv channel|roku premium channel)$")
_TIER = re.compile(r"\s+(?:(?:basic|standard|premium)\s+)?(?:with ads|no ads|without ads)$")
_PLAN = re.compile(r"\s+(?:premium plus|premium|essential|kids)$")


def _clean(name) -> str:
    """"Netflix basic with Ads", "Max Amazon Channel" and "Peacock Premium Plus" become the service's own name."""
    text = str(name or "").casefold().replace("+", " plus ").replace("&", " and ")
    text = " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())
    for _ in range(3):
        before = text
        text = _PLAN.sub("", _TIER.sub("", _CHANNEL.sub("", text)))
        if text == before:
            break
    return text


def service_for(name) -> Optional[str]:
    return ALIASES.get(_clean(name))


def _stream_providers(where: Optional[dict]):
    for group in (where or {}).get("groups") or []:
        if not isinstance(group, dict) or group.get("label") not in STREAM_GROUPS:
            continue
        for provider in group.get("providers") or []:
            if isinstance(provider, dict) and provider.get("name"):
                yield provider


def services_in(where: Optional[dict]) -> set[str]:
    """The catalogue services a cached where-to-watch result says the title streams on."""
    return {service for provider in _stream_providers(where) if (service := service_for(provider["name"]))}


def catalog() -> list[dict]:
    return [{"id": service_id, "name": name, "free": free} for service_id, name, free, _ in SERVICES]


def region() -> str:
    return where_to_watch.region()


# ---------------------------------------------------------------- rules

MIN_TITLES = 2                      # unfinished films, shows and anime before the card asks
NEW_FOR = timedelta(days=14)        # how long an arrival wears its "New" tag on the card
BLIP = timedelta(days=14)           # gone for less than this and back again: not an arrival
ALERT_WINDOW = timedelta(days=7)    # arrivals older than this when first noticed aren't announced
LATER = timedelta(days=30)          # "Not now" on the question
HIDE = timedelta(days=21)           # "Hide this card" once services are picked
REFRESH_AFTER = timedelta(days=3)   # titles on these lists are rechecked this often (the cache keeps 7 days)
RETRY = {"miss": timedelta(days=3), "error": timedelta(hours=6)}
CARD_LIMIT = 60
ROW_LIMIT = 2000                    # per library, newest first
WARM_BATCH = 30                     # titles refreshed per background run
AFTER_SAVE_BATCH = 12               # titles refreshed right after a member picks services
CHECK_EVERY_SECONDS = 30 * 60
FIRST_CHECK_DELAY_SECONDS = 420
NOTIFICATION_TYPE = "service_arrival"
LINK = "/#on-your-services"
NAMES_SHOWN = 2
DIGEST_SHOWN = 5
CHUNK = 400

# Library category -> title page kind. Only these three have streaming services to show.
CATEGORIES = {"movies": "movie", "tv-shows": "tv", "anime": "anime"}
CATEGORY_LABELS = {"movies": "Movie", "tv-shows": "TV show", "anime": "Anime"}
PRIVATE_FLAG = {"movies": "movies_private", "tv-shows": "tv_shows_private", "anime": "anime_private"}

COUNTERS = {
    "seen_choose": "Saw the card asking which services they have",
    "seen_list": "Saw the card listing what's on their services",
    "saved_card": "Picked services for the first time",
    "changed": "Changed their services",
    "cleared": "Cleared all their services",
    "later": "Not now",
    "stop": "No thanks",
    "hide": "Hid the card",
    "alerts_on": "Turned arrival notes on",
    "alerts_off": "Turned arrival notes off",
    "where": "Opened where to watch from the card",
    "queued": "Added a title to Up next from the card",
    "opened": "Opened a title from the card",
    "filter": "Used the On my services library filter",
    "from_alert": "Opened the card from an arrival note",
    "alert_sent": "Members told about an arrival",
    "alert_titles": "Titles in those notes",
}
EVENTS = {"where", "queued", "opened", "filter", "from_alert", "seen_choose", "seen_list"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def count(key: str, amount: int = 1) -> bool:
    """Add to a "stream" counter for today. Never raises."""
    try:
        from .site_traffic import RECORDER
        if not RECORDER.enabled or key not in COUNTERS or amount <= 0:
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "stream", key)] += amount
            RECORDER._events += amount
        return True
    except Exception:
        return False


def enabled_for_process() -> bool:
    if os.getenv("TESTING", "").lower() == "true":
        return False
    return os.getenv("STREAMING_ALERTS", "on").strip().lower() not in {"off", "false", "0", "no"}


def _chunks(values: list) -> list[list]:
    return [values[start:start + CHUNK] for start in range(0, len(values), CHUNK)]


# ---------------------------------------------------------------- a member's choice

def get_choice(db: Session, user_id: int) -> Optional[models.StreamingChoice]:
    return db.query(models.StreamingChoice).filter(models.StreamingChoice.user_id == user_id).first()


def _choice(db: Session, user_id: int, now: datetime) -> models.StreamingChoice:
    row = get_choice(db, user_id)
    if row is None:
        row = models.StreamingChoice(user_id=user_id, alerts=True, created_at=now, updated_at=now)
        db.add(row)
        db.flush()
    return row


def chosen(choice: Optional[models.StreamingChoice]) -> dict[str, datetime]:
    """{service id: when the member picked it}, in catalogue order, leaving out anything unreadable."""
    if choice is None or not choice.services:
        return {}
    try:
        saved = json.loads(choice.services)
    except (TypeError, ValueError):
        return {}
    if not isinstance(saved, dict):
        return {}
    found = {}
    for service_id in SERVICE_IDS:
        when = saved.get(service_id)
        if not isinstance(when, str):
            continue
        try:
            found[service_id] = datetime.fromisoformat(when)
        except ValueError:
            continue
    return found


def save(db: Session, user: models.User, services: Optional[list[str]], alerts: Optional[bool] = None,
         now: Optional[datetime] = None) -> models.StreamingChoice:
    """Replace the member's services (None keeps them) and/or their arrival-note switch."""
    now = now or _now()
    row = _choice(db, user.id, now)
    before = chosen(row)
    if services is not None:
        unknown = [service for service in services if service not in NAMES]
        if unknown:
            raise ValueError("Unknown streaming service")
        wanted = list(dict.fromkeys(services))[:MAX_PICKED]
        picked = {service: before.get(service, now) for service in SERVICE_IDS if service in wanted}
        row.services = json.dumps({service: when.isoformat(timespec="seconds") for service, when in picked.items()})
        # Picking services is asking for the card, so anything that kept it away is undone.
        row.hidden_until = None
        row.stopped_at = None
        if picked and not before:
            count("saved_card")
        elif picked and set(picked) != set(before):
            count("changed")
        elif before and not picked:
            count("cleared")
    if alerts is not None and bool(alerts) != bool(row.alerts):
        row.alerts = bool(alerts)
        count("alerts_on" if alerts else "alerts_off")
    row.updated_at = now
    db.commit()
    return row


ANSWERS = ("later", "stop", "hide", "show")


def answer(db: Session, user: models.User, what: str, now: Optional[datetime] = None) -> bool:
    if what not in ANSWERS:
        raise ValueError("Unknown answer")
    now = now or _now()
    row = _choice(db, user.id, now)
    if what == "later":
        row.hidden_until = now + LATER
    elif what == "stop":
        row.stopped_at = now
    elif what == "hide":
        row.hidden_until = now + HIDE
    else:
        row.hidden_until = None
        row.stopped_at = None
    row.updated_at = now
    db.commit()
    if what != "show":
        count(what)
    return True


# ---------------------------------------------------------------- the member's titles

@dataclass
class Entry:
    category: str
    kind: str
    id: int
    title: str
    year: Optional[int]
    poster: Optional[str]
    finished: bool
    added_at: Optional[datetime]
    creator: Optional[str]
    key: str


def entries_for(db: Session, user_id: int, unfinished_only: bool = True,
                categories: Iterable[str] = tuple(CATEGORIES)) -> list[Entry]:
    """The member's films, shows and anime (unfinished ones by default), newest first in each library."""
    found = []
    for category in categories:
        kind = CATEGORIES[category]
        model = title_pages.KINDS[kind][0]
        columns = [model.id, model.title, model.year, model.poster_url, model.watched, model.added_at]
        if kind == "movie":
            columns.append(model.director)
        query = db.query(*columns).filter(model.user_id == user_id)
        if unfinished_only:
            query = query.filter(or_(model.watched.is_(False), model.watched.is_(None)))
        for row in query.order_by(model.id.desc()).limit(ROW_LIMIT).all():
            display = " ".join(str(row.title or "").split())
            normalized = title_pages.normalize(display)
            if not normalized:
                continue
            year = row.year if isinstance(row.year, int) and 1800 <= row.year <= 2200 else None
            found.append(Entry(category, kind, row.id, display, year,
                               row.poster_url if isinstance(row.poster_url, str) and row.poster_url.startswith("https://") else None,
                               bool(row.watched), row.added_at, getattr(row, "director", None) or None,
                               where_to_watch.cache_key(kind, normalized, year)))
    return found


def _sightings(db: Session, keys: Iterable[str], services: Optional[set] = None) -> dict[str, list[models.ServiceSighting]]:
    """Live sightings for these titles, on these services when given."""
    found: dict[str, list[models.ServiceSighting]] = {}
    keys = sorted(set(keys))
    if services is not None and not services:
        return found
    for chunk in _chunks(keys):
        query = db.query(models.ServiceSighting).filter(
            models.ServiceSighting.title_key.in_(chunk), models.ServiceSighting.gone_at.is_(None))
        if services is not None:
            query = query.filter(models.ServiceSighting.service.in_(sorted(services)))
        for row in query.all():
            found.setdefault(row.title_key, []).append(row)
    for rows in found.values():
        rows.sort(key=lambda row: ORDER.get(row.service, 99))
    return found


def _is_new(row: models.ServiceSighting, now: datetime) -> bool:
    return not row.baseline and row.first_seen_at is not None and row.first_seen_at >= now - NEW_FOR


# ---------------------------------------------------------------- the home card

def _private(user: models.User, category: str) -> bool:
    return bool(getattr(user, PRIVATE_FLAG[category], False))


def _queued(db: Session, user_id: int) -> set[tuple[str, int]]:
    return {(category, item_id) for category, item_id in db.query(
        models.NextUpItem.category, models.NextUpItem.item_id).filter(
        models.NextUpItem.user_id == user_id, models.NextUpItem.category.in_(tuple(CATEGORIES))).all()}


def _pending(db: Session, keys: set[str]) -> int:
    """Titles not compared yet: no cached answer at all, or a cached one the check hasn't read."""
    if not keys:
        return 0
    status, checked = {}, set()
    for chunk in _chunks(sorted(keys)):
        status.update(dict(db.query(models.TitleMetadata.key, models.TitleMetadata.status).filter(
            models.TitleMetadata.key.in_(chunk)).all()))
        checked.update(key for key, in db.query(models.ServiceTitleCheck.title_key).filter(
            models.ServiceTitleCheck.title_key.in_(chunk)).all())
    return sum(1 for key in keys if key not in checked and status.get(key) in (None, "ok", "error"))


def credit() -> str:
    parts = ["JustWatch via TMDB"] if where_to_watch.tmdb_enabled() else []
    parts += ["TVmaze", "MyAnimeList"]
    return f"Streaming info from {_and(parts)}, for {region()} services."


def card(db: Session, user: models.User, now: Optional[datetime] = None) -> Optional[dict]:
    """The "On your services" card, or None when it shouldn't show."""
    now = now or _now()
    choice = get_choice(db, user.id)
    picked = chosen(choice)
    if choice is not None and choice.hidden_until is not None and choice.hidden_until > now:
        return None
    entries = entries_for(db, user.id)
    alerts = True if choice is None else bool(choice.alerts)
    base = {"catalog": catalog(), "region": region(), "alerts": alerts, "tracked": len(entries),
            "tmdb_notice": where_to_watch.tmdb_enabled(), "credit": credit()}
    if not picked:
        if (choice is not None and choice.stopped_at is not None) or len(entries) < MIN_TITLES:
            return None
        kinds = sorted({entry.category for entry in entries}, key=list(CATEGORIES).index)
        return {**base, "state": "choose", "chosen": [], "kinds": kinds}
    if not entries:
        return None
    by_key = _sightings(db, {entry.key for entry in entries}, set(picked))
    queued = _queued(db, user.id)
    items, counts, seen_keys = [], {service: 0 for service in picked}, set()
    for entry in entries:
        rows = by_key.get(entry.key)
        if not rows or (entry.category, entry.id) in seen_keys:
            continue
        seen_keys.add((entry.category, entry.id))
        newest = max((row.first_seen_at for row in rows if _is_new(row, now)), default=None)
        for row in rows:
            counts[row.service] = counts.get(row.service, 0) + 1
        items.append({
            "category": entry.category, "kind": entry.kind, "id": entry.id, "title": entry.title, "year": entry.year,
            "label": CATEGORY_LABELS[entry.category], "poster": entry.poster,
            "services": [{"id": row.service, "name": NAMES[row.service], "new": _is_new(row, now)} for row in rows],
            "new": newest is not None, "since": newest.date().isoformat() if newest else None,
            "path": None if _private(user, entry.category) else title_pages.title_path(entry.kind, entry.title, entry.year),
            "queued": (entry.category, entry.id) in queued,
            "_order": (0 if newest else 1, -(newest.timestamp() if newest else 0)),
        })
    items.sort(key=lambda item: item["_order"])
    for item in items:
        item.pop("_order")
    return {
        **base, "state": "list",
        "chosen": [{"id": service, "name": NAMES[service], "count": counts.get(service, 0)} for service in picked],
        "items": items[:CARD_LIMIT], "total": len(items), "new": sum(1 for item in items if item["new"]),
        "pending": _pending(db, {entry.key for entry in entries}),
    }


def picked_names(db: Session, user_id: int) -> list[str]:
    return [NAMES[service] for service in chosen(get_choice(db, user_id))]


def mine(db: Session, user_id: int, where: Optional[dict]) -> list[str]:
    """Provider names in a where-to-watch result that stream on services this member picked."""
    picked = set(chosen(get_choice(db, user_id)))
    if not picked:
        return []
    return list(dict.fromkeys(provider["name"] for provider in _stream_providers(where)
                              if service_for(provider["name"]) in picked))


def ids_on_services(db: Session, user: models.User, category: str) -> set[int]:
    """Ids of every title in this library (finished ones too) that streams on one of the member's services."""
    if category not in CATEGORIES:
        return set()
    picked = set(chosen(get_choice(db, user.id)))
    if not picked:
        return set()
    entries = entries_for(db, user.id, unfinished_only=False, categories=(category,))
    live = _sightings(db, {entry.key for entry in entries}, picked)
    return {entry.id for entry in entries if entry.key in live}


# ---------------------------------------------------------------- comparing titles

def _diff(db: Session, key: str, where: dict, first: bool, now: datetime) -> tuple[int, int]:
    current = services_in(where)
    # Without TMDB's part of the answer (it failed or found nothing this time), what's missing may only
    # be missing from this lookup, so nothing is marked gone.
    complete = bool(where.get("justwatch")) or not where_to_watch.tmdb_enabled()
    existing = {row.service: row for row in db.query(models.ServiceSighting).filter(
        models.ServiceSighting.title_key == key).all()}
    arrived = left = 0
    for service in sorted(current):
        row = existing.get(service)
        if row is None:
            db.add(models.ServiceSighting(title_key=key, service=service, first_seen_at=now, last_seen_at=now,
                                          baseline=first))
            arrived += 0 if first else 1
            continue
        if row.gone_at is not None:
            if now - row.gone_at >= BLIP:
                row.first_seen_at = now
                row.baseline = False
                arrived += 1
            row.gone_at = None
        row.last_seen_at = now
    if complete:
        for service, row in existing.items():
            if service not in current and row.gone_at is None:
                row.gone_at = now
                left += 1
    return arrived, left


def sync(db: Session, keys: Iterable[str], now: Optional[datetime] = None) -> dict:
    """Compare every title whose cached answer changed since it was last read. No network."""
    now = now or _now()
    stats = {"compared": 0, "arrived": 0, "left": 0}
    for chunk in _chunks(sorted(set(keys))):
        rows = db.query(models.TitleMetadata.key, models.TitleMetadata.data, models.TitleMetadata.fetched_at).filter(
            models.TitleMetadata.key.in_(chunk), models.TitleMetadata.status == "ok").all()
        if not rows:
            continue
        checks = {row.title_key: row for row in db.query(models.ServiceTitleCheck).filter(
            models.ServiceTitleCheck.title_key.in_(chunk)).all()}
        try:
            for key, data, fetched_at in rows:
                check = checks.get(key)
                if check is not None and check.source_fetched_at == fetched_at:
                    continue
                try:
                    where = json.loads(data) if data else None
                except ValueError:
                    where = None
                if not isinstance(where, dict):
                    continue
                arrived, left = _diff(db, key, where, check is None, now)
                stats["compared"] += 1
                stats["arrived"] += arrived
                stats["left"] += left
                if check is None:
                    db.add(models.ServiceTitleCheck(title_key=key, first_checked_at=now, checked_at=now,
                                                    source_fetched_at=fetched_at))
                else:
                    check.checked_at = now
                    check.source_fetched_at = fetched_at
            db.commit()
        except IntegrityError:
            # Another worker compared the same title at the same moment; it'll be read again next run.
            db.rollback()
    return stats


def _members(db: Session) -> list[models.StreamingChoice]:
    rows = db.query(models.StreamingChoice).join(models.User, models.User.id == models.StreamingChoice.user_id).filter(
        models.User.is_active == True,  # noqa: E712
        models.StreamingChoice.services.isnot(None),
    ).all()
    return [row for row in rows if chosen(row)]


def member_keys(db: Session, user_id: Optional[int] = None, unfinished_only: bool = False) -> set[str]:
    user_ids = [user_id] if user_id is not None else [row.user_id for row in _members(db)]
    return {entry.key for uid in user_ids for entry in entries_for(db, uid, unfinished_only=unfinished_only)}


def _due(row, now: datetime) -> bool:
    if row is None:
        return True
    status, fetched_at = row
    if status == "ok":
        return now - fetched_at >= REFRESH_AFTER
    return now - fetched_at >= RETRY.get(status, RETRY["error"])


def stale_entries(db: Session, now: Optional[datetime] = None, user_id: Optional[int] = None,
                  limit: int = WARM_BATCH) -> list[Entry]:
    """Unfinished titles on these members' lists whose where-to-watch answer is missing or getting old.

    Titles nobody has looked up come first, then the oldest answers.
    """
    now = now or _now()
    user_ids = [user_id] if user_id is not None else [row.user_id for row in _members(db)]
    unique: dict[str, Entry] = {}
    for uid in user_ids:
        for entry in entries_for(db, uid):
            unique.setdefault(entry.key, entry)
    cached = {}
    for chunk in _chunks(sorted(unique)):
        for key, status, fetched_at in db.query(models.TitleMetadata.key, models.TitleMetadata.status,
                                                models.TitleMetadata.fetched_at).filter(
                models.TitleMetadata.key.in_(chunk)).all():
            cached[key] = (status, fetched_at)
    due = [entry for key, entry in unique.items() if _due(cached.get(key), now)]
    due.sort(key=lambda entry: (entry.key in cached, cached.get(entry.key, (None, datetime.min))[1]))
    return due[:limit]


async def warm(session_factory, client, limit: int = WARM_BATCH, user_id: Optional[int] = None,
               pause: float = 1.5) -> int:
    """Refresh where-to-watch for titles that are due, a few at a time. Returns how many were looked up."""
    from starlette.concurrency import run_in_threadpool
    db = session_factory()
    fetched = 0
    try:
        entries = await run_in_threadpool(stale_entries, db, None, user_id, limit)
        for entry in entries:
            normalized = title_pages.normalize(entry.title)
            metadata = await title_metadata.get_or_fetch(db, client, entry.kind, normalized, entry.title, entry.year,
                                                         entry.creator, wait=20)
            await where_to_watch.get_or_fetch(db, client, entry.kind, normalized, entry.title, entry.year, metadata,
                                              wait=20, creator=entry.creator, force=True)
            fetched += 1
            if pause:
                await asyncio.sleep(pause)
    finally:
        db.close()
    return fetched


# ---------------------------------------------------------------- arrival notes

def _and(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def arrivals(db: Session, user: models.User, choice: models.StreamingChoice, now: datetime,
             window: timedelta = ALERT_WINDOW) -> list[tuple[Entry, models.ServiceSighting]]:
    """Unfinished titles on the member's list that arrived on one of their services within the window."""
    picked = chosen(choice)
    if not picked:
        return []
    by_key: dict[str, Entry] = {}
    for entry in entries_for(db, user.id):
        by_key.setdefault(entry.key, entry)
    found = []
    for key, rows in _sightings(db, by_key, set(picked)).items():
        for row in rows:
            if not row.baseline and row.first_seen_at >= now - window:
                found.append((by_key[key], row))
    found.sort(key=lambda pair: (-pair[1].first_seen_at.timestamp(), pair[0].title.casefold()))
    return found


def _grouped(found: list[tuple[Entry, models.ServiceSighting]]) -> list[tuple[str, list[str]]]:
    titles: dict[str, tuple[str, list[str]]] = {}
    for entry, row in found:
        title, services = titles.setdefault(entry.key, (entry.title, []))
        if NAMES[row.service] not in services:
            services.append(NAMES[row.service])
    return list(titles.values())


def message_for(found: list[tuple[Entry, models.ServiceSighting]]) -> str:
    titles = _grouped(found)
    if len(titles) == 1:
        title, services = titles[0]
        return f"{title} is now streaming on {_and(services)}, and it's on your list."
    shown = [f"{title} ({_and(services)})" for title, services in titles[:NAMES_SHOWN]]
    rest = len(titles) - NAMES_SHOWN
    if rest > 0:
        return f"Now on your services: {', '.join(shown)} and {rest} more from your list."
    return f"Now on your services: {shown[0]} and {shown[1]}, both from your list."


def send_alerts(db: Session, now: Optional[datetime] = None) -> dict:
    """One bell note per member for titles that just arrived on their services. Each arrival is told once."""
    now = now or _now()
    stats = {"members": 0, "titles": 0}
    for choice in _members(db):
        if not choice.alerts:
            continue
        user = db.get(models.User, choice.user_id)
        if user is None or not user.is_active:
            continue
        picked = chosen(choice)
        found = [(entry, row) for entry, row in arrivals(db, user, choice, now)
                 # Picked the service, or added the title, after it arrived: the card already shows it.
                 if row.first_seen_at > picked[row.service]
                 and (entry.added_at is None or row.first_seen_at > entry.added_at)]
        if not found:
            continue
        keys = sorted({entry.key for entry, _ in found})
        told = {}
        for chunk in _chunks(keys):
            for alert in db.query(models.ServiceAlert).filter(models.ServiceAlert.user_id == user.id,
                                                              models.ServiceAlert.title_key.in_(chunk)).all():
                told[(alert.title_key, alert.service)] = alert
        fresh = []
        for entry, row in found:
            alert = told.get((entry.key, row.service))
            if alert is None or alert.created_at < row.first_seen_at:
                fresh.append((entry, row))
        if not fresh:
            continue
        try:
            for entry, row in fresh:
                alert = told.get((entry.key, row.service))
                if alert is None:
                    alert = models.ServiceAlert(user_id=user.id, title_key=entry.key, service=row.service,
                                                title=entry.title[:200], created_at=now)
                    db.add(alert)
                    told[(entry.key, row.service)] = alert
                else:
                    alert.created_at = now
            db.add(models.Notification(user_id=user.id, type=NOTIFICATION_TYPE, message=message_for(fresh)[:480],
                                       link=LINK))
            db.commit()
        except Exception:
            # Another process told this member first (unique constraint); skip them this run.
            db.rollback()
            continue
        stats["members"] += 1
        stats["titles"] += len(_grouped(fresh))
    if stats["members"]:
        count("alert_sent", stats["members"])
        count("alert_titles", stats["titles"])
    return stats


def digest_line(db: Session, user: models.User, now: datetime) -> list[dict]:
    """Arrivals of the last week for the weekly email: [{"title", "label", "services"}]."""
    choice = get_choice(db, user.id)
    if choice is None or not choice.alerts:
        return []  # unticking "Tell me when..." quiets the email section too
    found = arrivals(db, user, choice, now)
    lines, seen = [], set()
    for entry, _row in found:
        if entry.key in seen:
            continue
        seen.add(entry.key)
        services = [NAMES[row.service] for other, row in found if other.key == entry.key]
        lines.append({"title": entry.title, "label": CATEGORY_LABELS[entry.category],
                      "services": list(dict.fromkeys(services))})
        if len(lines) >= DIGEST_SHOWN:
            break
    return lines


# ---------------------------------------------------------------- background work

def _sync_and_alert(session_factory, user_id: Optional[int] = None, alerts: bool = True) -> dict:
    db = session_factory()
    try:
        synced = sync(db, member_keys(db, user_id))
        sent = send_alerts(db) if alerts else {"members": 0, "titles": 0}
        return {**synced, "told": sent["members"]}
    finally:
        db.close()


def sync_member(db: Session, user_id: int) -> dict:
    """Read what's already cached for one member's titles, right after they pick services."""
    try:
        return sync(db, member_keys(db, user_id))
    except Exception:
        db.rollback()
        logger.exception("Streaming services check failed for a member")
        return {}


async def after_save(app, user_id: int) -> None:
    """Look up a member's unchecked titles soon after they pick services, so the card fills in."""
    if not enabled_for_process():
        return
    from .database import SessionLocal
    try:
        client = getattr(app.state, "external_api_client", None)
        if client is not None:
            await warm(SessionLocal, client, limit=AFTER_SAVE_BATCH, user_id=user_id, pause=0.4)
        await asyncio.to_thread(_sync_and_alert, SessionLocal, user_id, False)
    except Exception:
        logger.exception("Streaming services lookups after saving failed")


async def run_once(session_factory, client) -> dict:
    fetched = await warm(session_factory, client) if client is not None else 0
    stats = await asyncio.to_thread(_sync_and_alert, session_factory)
    return {"fetched": fetched, **stats}


async def streaming_loop(app) -> None:
    """Background task started with the app; never raises."""
    from .database import SessionLocal
    await asyncio.sleep(FIRST_CHECK_DELAY_SECONDS)
    while True:
        try:
            stats = await run_once(SessionLocal, getattr(app.state, "external_api_client", None))
            if any(stats.values()):
                logger.info("Streaming services check: %s", stats)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Streaming services check failed")
        await asyncio.sleep(CHECK_EVERY_SECONDS)


# ---------------------------------------------------------------- Site stats

def stats(db: Session, days: int, now: datetime) -> dict:
    table = models.SiteTrafficDaily
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "stream", table.day >= (now - timedelta(days=days - 1)).date(),
    ).group_by(table.key).all())
    members = _members(db)
    by_service: dict[str, int] = {}
    for row in members:
        for service in chosen(row):
            by_service[service] = by_service.get(service, 0) + 1
    since = now - timedelta(days=days)
    sightings = models.ServiceSighting
    return {
        "counts": {key: int(counts.get(key) or 0) for key in COUNTERS},
        "labels": COUNTERS,
        "members_now": len(members),
        "alerts_on_now": sum(1 for row in members if row.alerts),
        "by_service": [{"name": NAMES[service], "count": by_service[service]}
                       for service in sorted(by_service, key=lambda s: (-by_service[s], ORDER[s]))],
        "titles_checked": int(db.query(func.count(models.ServiceTitleCheck.id)).scalar() or 0),
        "arrivals": int(db.query(func.count(sightings.id)).filter(
            sightings.baseline == False, sightings.first_seen_at >= since).scalar() or 0),  # noqa: E712
    }
