"""Estimated time spent on a member's library, from fields we already store.

Almost nothing here is measured: games imported from Steam count the minutes
Steam reported (``game_playtime``), played or not. Every other title gets a
length, then the member's own status and progress decide how much of it counts:

* finished titles count in full,
* unfinished shows, anime, books, manga, podcasts and audiobooks count up to
  the member's saved checkpoint (episode, page or chapter),
* anything else counts as zero.

A title's length comes from the shared ``title_metadata`` cache when a title page
has already looked it up (running time, episode length, page count, RAWG's
average playtime, album length), from the member's own episode and chapter
counts, an audiobook's own length, and otherwise from a typical length for that kind of title. The result
says how many titles fell back to a typical length so the page can be honest
about it. The cache is only read, never fetched, so this stays one batch of
queries however large the library is.

"This year" counts only titles finished this year according to the journal or a
completion moment (the same dates Year in Review uses), in full.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import episodes, game_playtime, models, title_metadata, title_pages, year_in_review

# Library category -> (URL kind, plural label, privacy flag on the user)
CATEGORIES = {
    "movies": ("movie", "Movies", "movies_private"),
    "tv-shows": ("tv", "TV shows", "tv_shows_private"),
    "anime": ("anime", "Anime", "anime_private"),
    "video-games": ("game", "Games", "video_games_private"),
    "music": ("album", "Albums", "music_private"),
    "books": ("book", "Books", "books_private"),
    "manga": ("manga", "Manga", "manga_private"),
    "podcasts": ("podcast", "Podcasts", "podcasts_private"),
    "audiobooks": ("audiobook", "Audiobooks", "audiobooks_private"),
}
VERBS = {"movies": "watching", "tv-shows": "watching", "anime": "watching", "video-games": "playing",
         "music": "listening", "books": "reading", "manga": "reading", "podcasts": "listening",
         "audiobooks": "listening"}

# Typical lengths used when neither the cache nor the member's own counts say.
MOVIE_MINUTES = 115
TV_EPISODE_MINUTES = 42
TV_EPISODES = 10          # a typical season when the member left episodes blank
ANIME_EPISODE_MINUTES = 24
ANIME_EPISODES = 12       # one cour
GAME_HOURS = 20
ALBUM_MINUTES = 45
BOOK_PAGES = 320
MINUTES_PER_PAGE = 1.5    # about 40 pages an hour
MANGA_CHAPTER_MINUTES = 5
MANGA_CHAPTERS_PER_VOLUME = 9
MANGA_CHAPTERS = 50
PODCAST_EPISODE_MINUTES = 45
PODCAST_EPISODES = 10     # a podcast marked listened with no episode count
AUDIOBOOK_HOURS = 10
AUDIOBOOK_CHAPTER_MINUTES = 25
# A typo like 30000 episodes shouldn't swamp the total.
MAX_ITEM_MINUTES = 2000 * 60
MAX_COUNT = 5000

DEFAULTS = {
    "movies": f"{MOVIE_MINUTES} minutes per movie",
    "tv-shows": f"{TV_EPISODE_MINUTES} minutes per episode, {TV_EPISODES} episodes a season if you left episodes blank",
    "anime": f"{ANIME_EPISODE_MINUTES} minutes per episode, {ANIME_EPISODES} episodes if you left episodes blank",
    "video-games": f"{GAME_HOURS} hours per game",
    "music": f"{ALBUM_MINUTES} minutes per album",
    "books": f"{BOOK_PAGES} pages per book at about {round(60 / MINUTES_PER_PAGE)} pages an hour",
    "manga": f"{MANGA_CHAPTER_MINUTES} minutes per chapter, {MANGA_CHAPTERS} chapters if you left chapters blank",
    "podcasts": f"{PODCAST_EPISODE_MINUTES} minutes per episode",
    "audiobooks": f"{AUDIOBOOK_HOURS} hours per audiobook if you left the length blank",
}
SOURCES_NOTE = ("Running times, episode lengths and page counts come from Wikidata, TVmaze, MyAnimeList and "
                "Open Library, and game lengths from RAWG's average playtime, once a title page has looked them up.")

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_HOURS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:hr|hour|h\b)", re.IGNORECASE)
_MINUTES = re.compile(r"(\d+(?:\.\d+)?)\s*(?:min|m\b)", re.IGNORECASE)


# ---------------------------------------------------------------- parsing cached facts

def parse_minutes(value) -> Optional[float]:
    """Minutes from strings like "142 min", "24 min per ep", "1 hr 30 min" or "2 hours"."""
    if not isinstance(value, str):
        return None
    first = value.split(",")[0]
    hours, minutes = _HOURS.search(first), _MINUTES.search(first)
    if not hours and not minutes:
        return None
    total = (float(hours.group(1)) * 60 if hours else 0) + (float(minutes.group(1)) if minutes else 0)
    return total if 0 < total <= MAX_ITEM_MINUTES else None


def parse_count(value) -> Optional[int]:
    if not isinstance(value, str):
        return None
    match = _NUMBER.search(value.split(",")[0].replace(" ", ""))
    if not match:
        return None
    number = int(float(match.group(0)))
    return number if 0 < number <= MAX_COUNT else None


def _facts(data: Optional[dict]) -> dict[str, str]:
    return {fact.get("label"): fact.get("value") for fact in (data or {}).get("facts") or [] if isinstance(fact, dict)}


def _cached_facts(db: Session, keys: list[str]) -> dict[str, dict]:
    keys = list(dict.fromkeys(keys))
    found = {}
    for start in range(0, len(keys), 500):
        rows = db.query(models.TitleMetadata.key, models.TitleMetadata.data).filter(
            models.TitleMetadata.key.in_(keys[start:start + 500]),
            models.TitleMetadata.status == "ok",
        ).all()
        for key, data in rows:
            try:
                facts = _facts(json.loads(data) if data else None)
            except ValueError:
                continue
            if facts:
                found[key] = facts
    return found


# ---------------------------------------------------------------- per-title lengths

def _clamp_count(value) -> Optional[int]:
    return value if type(value) is int and 0 < value <= MAX_COUNT else None


def full_minutes(category: str, item, facts: dict, layout_total: Optional[int] = None) -> tuple[float, bool]:
    """(minutes for the whole title, used a typical length)."""
    if category == "movies":
        minutes = parse_minutes(facts.get("Running time"))
        return (minutes, False) if minutes else (MOVIE_MINUTES, True)
    if category in ("tv-shows", "anime"):
        per_episode = parse_minutes(facts.get("Episode length"))
        default_minutes = TV_EPISODE_MINUTES if category == "tv-shows" else ANIME_EPISODE_MINUTES
        count = layout_total or _clamp_count(getattr(item, "episodes", None)) or parse_count(facts.get("Episodes"))
        guessed = per_episode is None or count is None
        if count is None:
            seasons = _clamp_count(getattr(item, "seasons", None))
            count = (seasons or 1) * TV_EPISODES if category == "tv-shows" else ANIME_EPISODES
        return min(count * (per_episode or default_minutes), MAX_ITEM_MINUTES), guessed
    if category == "video-games":
        hours = parse_minutes(facts.get("Average playtime"))
        return (hours, False) if hours else (GAME_HOURS * 60, True)
    if category == "music":
        minutes = parse_minutes(facts.get("Length"))
        return (minutes, False) if minutes else (ALBUM_MINUTES, True)
    if category == "books":
        pages = parse_count(facts.get("Pages"))
        return ((pages or BOOK_PAGES) * MINUTES_PER_PAGE, pages is None)
    if category == "manga":
        chapters = _clamp_count(getattr(item, "chapters", None)) or parse_count(facts.get("Chapters"))
        guessed = chapters is None
        if chapters is None:
            volumes = _clamp_count(getattr(item, "volumes", None))
            chapters = volumes * MANGA_CHAPTERS_PER_VOLUME if volumes else MANGA_CHAPTERS
        return min(chapters * MANGA_CHAPTER_MINUTES, MAX_ITEM_MINUTES), guessed
    if category == "podcasts":
        count = _clamp_count(getattr(item, "episodes", None))
        return min((count or PODCAST_EPISODES) * PODCAST_EPISODE_MINUTES, MAX_ITEM_MINUTES), True
    if category == "audiobooks":
        hours = getattr(item, "length_hours", None)
        if hours and hours > 0:
            return min(hours * 60, MAX_ITEM_MINUTES), False
        return AUDIOBOOK_HOURS * 60, True
    return 0.0, True


def partial_minutes(category: str, item, facts: dict, watched_episodes: Optional[int],
                    checkpoint) -> tuple[float, bool]:
    """(minutes up to the member's checkpoint on an unfinished title, used a typical length)."""
    if category in ("tv-shows", "anime"):
        if not watched_episodes:
            return 0.0, False
        per_episode = parse_minutes(facts.get("Episode length"))
        default_minutes = TV_EPISODE_MINUTES if category == "tv-shows" else ANIME_EPISODE_MINUTES
        return min(watched_episodes * (per_episode or default_minutes), MAX_ITEM_MINUTES), per_episode is None
    if checkpoint is None or not checkpoint.position:
        return 0.0, False
    position = min(checkpoint.position, MAX_COUNT)
    if category == "books" and checkpoint.unit == "page":
        return position * MINUTES_PER_PAGE, False
    if category == "manga" and checkpoint.unit == "chapter":
        return position * MANGA_CHAPTER_MINUTES, False
    if category == "podcasts" and checkpoint.unit == "episode":
        return position * PODCAST_EPISODE_MINUTES, True
    if category == "audiobooks" and checkpoint.unit == "chapter":
        full, _ = full_minutes(category, item, facts)
        return min(position * AUDIOBOOK_CHAPTER_MINUTES, full), True
    return 0.0, False


# ---------------------------------------------------------------- the whole library

def _done(category: str, item) -> bool:
    kind = CATEGORIES[category][0]
    return bool(getattr(item, title_pages.COMPLETE_FIELD[kind], False))


def visible_categories(user: models.User) -> list[str]:
    return [category for category, (_, _, flag) in CATEGORIES.items() if not getattr(user, flag, False)]


def estimate(db: Session, user: models.User, categories: Optional[list[str]] = None,
             today: Optional[date] = None) -> dict:
    """Minutes per category, all time and this year, with how many titles used typical lengths."""
    categories = [c for c in (categories if categories is not None else list(CATEGORIES)) if c in CATEGORIES]
    year = (today or date.today()).year
    _, finished = year_in_review._finishes(db, user.id, year, categories)
    finished_this_year = {(row["category"], row["item_id"]) for row in finished.values() if row.get("item_id")}

    checkpoints = {}
    for entry in db.query(models.ProgressCheckpoint).filter(
        models.ProgressCheckpoint.user_id == user.id,
        models.ProgressCheckpoint.unit.is_not(None),
    ):
        checkpoints[(entry.category, entry.item_id)] = entry

    rows = []
    for category in categories:
        kind, label, _ = CATEGORIES[category]
        model = title_pages.KINDS[kind][0]
        items = db.query(model).filter(model.user_id == user.id).all()
        if not items:
            continue
        keys = {item.id: title_metadata.cache_key(kind, title_pages.normalize(item.title or ""),
                                                  title_pages.item_year(kind, item)) for item in items}
        facts = _cached_facts(db, list(keys.values()))
        progress = episodes.progress_map(db, user.id, category, items) if category in episodes.KINDS else {}
        played = game_playtime.minutes_by_game(db, user.id) if category == "video-games" else {}

        minutes = year_minutes = 0.0
        counted = guessed = finished_count = measured = 0
        for item in items:
            item_facts = facts.get(keys[item.id], {})
            item_progress = progress.get(item.id) or {}
            if played.get(item.id):
                value, typical = float(played[item.id]), False
                measured += 1
                if _done(category, item):
                    finished_count += 1
                    if (category, item.id) in finished_this_year:
                        year_minutes += value
            elif _done(category, item):
                value, typical = full_minutes(category, item, item_facts, item_progress.get("total"))
                finished_count += 1
                if (category, item.id) in finished_this_year:
                    year_minutes += value
            else:
                value, typical = partial_minutes(category, item, item_facts, item_progress.get("watched"),
                                                 checkpoints.get((category, item.id)))
            if value <= 0:
                continue
            minutes += value
            counted += 1
            guessed += 1 if typical else 0
        rows.append({
            "category": category, "label": label, "verb": VERBS[category],
            "minutes": round(minutes), "hours": round(minutes / 60, 1),
            "year_minutes": round(year_minutes), "year_hours": round(year_minutes / 60, 1),
            "titles": counted, "finished": finished_count, "typical": guessed, "measured": measured,
            "default_note": DEFAULTS[category],
        })

    total = sum(row["minutes"] for row in rows)
    year_total = sum(row["year_minutes"] for row in rows)
    rows.sort(key=lambda row: -row["minutes"])
    for row in rows:
        row["share"] = round(100 * row["minutes"] / total) if total else 0
    titles = sum(row["titles"] for row in rows)
    return {
        "year": year,
        "minutes": total,
        "hours": round(total / 60),
        "days": round(total / 60 / 24, 1),
        "year_minutes": year_total,
        "year_hours": round(year_total / 60),
        "titles": titles,
        "typical": sum(row["typical"] for row in rows),
        "measured": sum(row["measured"] for row in rows),
        "categories": rows,
        "comparison": comparison(total),
        "sources_note": SOURCES_NOTE,
    }


# Profile views reuse an estimate for a few minutes. The shelves counted are part of the key,
# so making a shelf private takes effect on the next view; a new finish shows up within the TTL.
PUBLIC_HOURS_SECONDS = 600
PUBLIC_HOURS_SIZE = 4096
_public_hours: dict[tuple, tuple[float, int]] = {}
_public_hours_lock = threading.Lock()


def _public_hours_cache_enabled() -> bool:
    # Tests change data between requests and expect the page to follow at once.
    return os.getenv("TESTING", "").lower() != "true"


def clear_public_hours_cache() -> None:
    with _public_hours_lock:
        _public_hours.clear()


def public_hours(db: Session, user: models.User) -> int:
    """Hours for the public profile, from the shelves the member hasn't made private."""
    categories = visible_categories(user)
    if not _public_hours_cache_enabled():
        return estimate(db, user, categories)["hours"]
    key = (user.id, tuple(categories))
    now = time.monotonic()
    with _public_hours_lock:
        hit = _public_hours.get(key)
    if hit is not None and now - hit[0] < PUBLIC_HOURS_SECONDS:
        return hit[1]
    hours = estimate(db, user, categories)["hours"]
    with _public_hours_lock:
        if len(_public_hours) >= PUBLIC_HOURS_SIZE:
            _public_hours.clear()
        _public_hours[key] = (now, hours)
    return hours


# ---------------------------------------------------------------- plain-language comparisons

def comparison(minutes: float) -> str:
    """A plain sentence that gives a large number of minutes some scale."""
    hours = minutes / 60
    if hours < 1:
        return ""
    if hours < 24:
        return f"About {round(hours)} hour{'s' if round(hours) != 1 else ''}, or a long weekend of sofa time."
    days = hours / 24
    shown = f"{days:.1f}".rstrip("0").rstrip(".") if days < 10 else f"{round(days):,}"
    if days < 60:
        return f"About {shown} days without stopping. Spread over evenings, that's {round(hours / 2):,} two-hour nights."
    years = hours / (24 * 365)
    if years < 1:
        return f"About {shown} days without stopping, or {round(hours / 40):,} full-time work weeks."
    return f"About {shown} days without stopping, which is {years:.1f} years of round-the-clock time."


# ---------------------------------------------------------------- binge calculator

def binge_plan(total_minutes: float, minutes_per_day: float, start: date) -> dict:
    """Days needed and the finish date for a fixed daily budget. The start day counts as day one."""
    if total_minutes <= 0 or minutes_per_day <= 0:
        raise ValueError("Both the length and the daily time must be above zero.")
    days = int(-(-total_minutes // minutes_per_day))  # rounded up
    return {"days": days, "finish": (start + timedelta(days=days - 1)).isoformat(),
            "hours": round(total_minutes / 60, 1)}
