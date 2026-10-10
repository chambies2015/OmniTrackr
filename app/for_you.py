"""Personal suggestions built from data OmniTrackr already has.

* Starter picks: titles already saved by two or more members, plus popular
  upcoming Release Radar titles, for members with an empty or tiny library.
* Coming up for you: Release Radar titles that continue or match something in
  the member's own library (new seasons, sequels, the show itself premiering).

Nothing here calls an outside service; Release Radar data is read from its
cache only.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from . import release_radar as radar
from .editorial_collections import EDITOR_USERNAME

# Library category key -> (model, fields copied from a representative entry)
LIBRARY = {
    "movies": (models.Movie, ("title", "director", "year", "poster_url")),
    "tv-shows": (models.TVShow, ("title", "year", "seasons", "episodes", "poster_url")),
    "anime": (models.Anime, ("title", "year", "seasons", "episodes", "poster_url")),
    "video-games": (models.VideoGame, ("title", "release_date", "genres", "cover_art_url", "rawg_link")),
    "music": (models.Music, ("title", "artist", "year", "genre", "cover_art_url")),
    "books": (models.Book, ("title", "author", "year", "genre", "cover_art_url")),
}
LABELS = {"movies": "Movie", "tv-shows": "TV show", "anime": "Anime", "video-games": "Game", "music": "Album", "books": "Book"}
IMAGE_FIELD = {"movies": "poster_url", "tv-shows": "poster_url", "anime": "poster_url",
               "video-games": "cover_art_url", "music": "cover_art_url", "books": "cover_art_url"}
CREATOR_FIELD = {"movies": "director", "music": "artist", "books": "author"}
RADAR_TO_LIBRARY = {"movies": "movies", "tv": "tv-shows", "anime": "anime", "games": "video-games"}
RADAR_LABELS = {"movies": "Movie", "tv": "TV", "anime": "Anime", "games": "Game"}
POPULAR_MIN_MEMBERS = 2
STARTER_GOAL = 5
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_title(value: Optional[str]) -> str:
    text = _PUNCTUATION.sub(" ", (value or "").casefold())
    words = text.split()
    if words and words[0] in ("the", "a", "an") and len(words) > 1:
        words = words[1:]
    return " ".join(words)


def _safe_image(url) -> Optional[str]:
    if isinstance(url, str) and url.startswith(("https://", "http://")) and len(url) <= 1000:
        return url
    return None


def _normalized_column(model):
    return func.lower(func.trim(model.title))


def owned_titles(db: Session, user_id: int, categories: Iterable[str] = LIBRARY) -> dict[str, list[str]]:
    """Every title the member has, by library category."""
    result = {}
    for key in categories:
        model = LIBRARY[key][0]
        result[key] = [title for title, in db.query(model.title).filter(model.user_id == user_id).all() if title]
    return result


# ---------------------------------------------------------------- starter picks

PRIVATE_FLAG = {"movies": "movies_private", "tv-shows": "tv_shows_private", "anime": "anime_private",
                "video-games": "video_games_private", "music": "music_private", "books": "books_private"}


def _shareable_ids(db: Session, category: str):
    """Active members who haven't made this category private (private shelves never feed suggestions)."""
    flag = getattr(models.User, PRIVATE_FLAG[category])
    return db.query(models.User.id).filter(models.User.is_active == True, flag == False)


def _title_page(category: str, entry) -> Optional[str]:
    """The public title page for a popular pick (it exists because 2+ members track it)."""
    try:
        from . import title_pages
        return title_pages.path_for_item(title_pages.LIBRARY_TO_KIND[category], entry)
    except Exception:
        return None


def popular_titles(db: Session, category: str, exclude_user_id: int | None = None, limit: int = 8) -> list[dict]:
    """Titles saved by at least two members, with metadata from the most complete entry."""
    model, fields = LIBRARY[category]
    normalized = _normalized_column(model)
    members = func.count(func.distinct(model.user_id))
    # The editors account curates collections; it isn't a member, so it never makes a title "popular".
    editors = db.query(models.User.id).filter(models.User.username == EDITOR_USERNAME)
    shareable = _shareable_ids(db, category)
    query = (db.query(normalized, members).filter(~model.user_id.in_(editors), model.user_id.in_(shareable))
             .group_by(normalized).having(members >= POPULAR_MIN_MEMBERS))
    rows = query.order_by(members.desc(), normalized).limit(limit * 3).all()
    if not rows:
        return []
    owned = set()
    if exclude_user_id is not None:
        owned = {name for name, in db.query(normalized).filter(model.user_id == exclude_user_id).all()}
    counts = {name: int(count) for name, count in rows if name and name not in owned}
    if not counts:
        return []
    candidates = db.query(model).filter(normalized.in_(list(counts)), model.user_id.in_(_shareable_ids(db, category))).all()
    best: dict[str, object] = {}
    image_field = IMAGE_FIELD[category]
    for entry in candidates:
        key = (entry.title or "").strip().lower()
        score = (bool(_safe_image(getattr(entry, image_field, None))), sum(bool(getattr(entry, f, None)) for f in fields))
        current = best.get(key)
        if current is None or score > current[0]:
            best[key] = (score, entry)
    picks = []
    for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
        if name not in best:
            continue
        entry = best[name][1]
        year = getattr(entry, "year", None)
        if year is None and getattr(entry, "release_date", None):
            year = entry.release_date.year
        picks.append({
            "category": category,
            "label": LABELS[category],
            "title": entry.title.strip(),
            "year": year,
            "creator": getattr(entry, CREATOR_FIELD.get(category, ""), None) if category in CREATOR_FIELD else None,
            "image": _safe_image(getattr(entry, image_field, None)),
            "members": count,
            "source": "popular",
            "url": _title_page(category, entry),
        })
        if len(picks) >= limit:
            break
    return picks


def popular_entry_payload(db: Session, category: str, title: str) -> Optional[dict]:
    """Public metadata for a popular title, or None when it isn't popular."""
    picks = {pick["title"].strip().lower(): pick for pick in popular_titles(db, category, limit=200)}
    if title.strip().lower() not in picks:
        return None
    model, fields = LIBRARY[category]
    normalized = _normalized_column(model)
    entries = db.query(model).filter(normalized == title.strip().lower(), model.user_id.in_(_shareable_ids(db, category))).all()
    if not entries:
        return None
    image_field = IMAGE_FIELD[category]
    entries.sort(key=lambda entry: (bool(_safe_image(getattr(entry, image_field, None))),
                                    sum(bool(getattr(entry, f, None)) for f in fields)), reverse=True)
    source = entries[0]
    payload = {field: getattr(source, field, None) for field in fields}
    payload[image_field] = _safe_image(payload.get(image_field))
    if category == "video-games" and payload.get("rawg_link"):
        payload["rawg_link"] = _safe_image(payload["rawg_link"])
    return payload


def radar_pool(today: Optional[date] = None, client=None) -> list[dict]:
    """Cached Release Radar items for the current and next period of every category."""
    today = today or radar.today_utc()
    pool: list[dict] = []
    for category in radar.CATEGORY_ORDER:
        current = radar.current_window(category, today)
        windows = radar.allowed_windows(category, today)
        index = windows.index(current) if current in windows else 0
        for window in windows[index:index + 2]:
            entry = radar.CACHE.peek(window)
            if entry is None:
                if client is not None:
                    radar.CACHE.warm(client, window)
                continue
            for item in entry.get("items", []):
                pool.append({**item, "window": item.get("window") or window.slug})
    unique = {}
    for item in pool:
        unique.setdefault((item["category"], item["key"]), item)
    return list(unique.values())


def _radar_card(item: dict, reason: str = "") -> dict:
    return {
        "category": item["category"],
        "library_category": RADAR_TO_LIBRARY[item["category"]],
        "label": RADAR_LABELS[item["category"]],
        "title": item["title"],
        "date": item.get("date"),
        "date_note": item.get("date_note") or "",
        "image": _safe_image(item.get("image")),
        "details": item.get("details", [])[:2],
        "window": item.get("window"),
        "key": item["key"],
        "url": f"/release-radar/{item['category']}#item-{item['key']}",
        "reason": reason,
        "source": "radar",
    }


def upcoming_popular(pool: list[dict], today: date, owned: dict[str, list[str]], days: int = 30,
                     limit: int = 8, exclude_keys: set | None = None) -> list[dict]:
    owned_norm = {normalize_title(title) for titles in owned.values() for title in titles}
    exclude_keys = exclude_keys or set()
    chosen = []
    for item in sorted(radar.upcoming_within(pool, today, days), key=lambda i: -i.get("popularity", 0)):
        if (item["category"], item["key"]) in exclude_keys or normalize_title(item["title"]) in owned_norm:
            continue
        if not (item.get("save") or {}).get("title"):
            continue
        chosen.append(_radar_card(item))
        if len(chosen) >= limit:
            break
    return chosen


def starter_picks(db: Session, user_id: int, today: Optional[date] = None, client=None) -> dict:
    today = today or radar.today_utc()
    owned = owned_titles(db, user_id)
    total = sum(len(titles) for titles in owned.values())
    popular = []
    for category in LIBRARY:
        popular.extend(popular_titles(db, category, exclude_user_id=user_id, limit=6))
    popular.sort(key=lambda pick: (-pick["members"], pick["title"].lower()))
    upcoming = upcoming_popular(radar_pool(today, client), today, owned, days=45, limit=8)
    return {"library_total": total, "goal": STARTER_GOAL, "popular": popular[:18], "upcoming": upcoming}


# ---------------------------------------------------------------- coming up for you

def _matches(library_title: str, radar_title: str) -> bool:
    mine = normalize_title(library_title)
    theirs = normalize_title(radar_title)
    if len(mine) < 4 or not theirs:
        return False
    if theirs == mine:
        return True
    # Sequels and new seasons: the radar title continues the library title.
    return theirs.startswith(mine + " ")


def coming_up(db: Session, user_id: int, today: Optional[date] = None, client=None,
              pool: Optional[list[dict]] = None) -> dict:
    today = today or radar.today_utc()
    pool = radar_pool(today, client) if pool is None else pool
    owned = owned_titles(db, user_id, ("movies", "tv-shows", "anime", "video-games"))
    library = [(category, title) for category, titles in owned.items() for title in titles]
    start, end = today - timedelta(days=7), today + timedelta(days=60)
    matches = []
    matched_keys = set()
    for item in pool:
        try:
            day = date.fromisoformat(item.get("date") or "")
        except ValueError:
            continue
        if not (start <= day <= end):
            continue
        names = [item["title"]] + ([item["alt_title"]] if item.get("alt_title") else [])
        hit = next(((cat, title) for cat, title in library if any(_matches(title, name) for name in names)), None)
        if hit is None:
            continue
        same = normalize_title(hit[1]) == normalize_title(item["title"])
        reason = f"In your library: {hit[1]}" if same else f"Because you track {hit[1]}"
        matches.append(_radar_card(item, reason))
        matched_keys.add((item["category"], item["key"]))
    matches.sort(key=lambda card: (card["date"] or "", card["title"].lower()))
    popular = upcoming_popular(pool, today, owned, days=30, limit=6, exclude_keys=matched_keys)
    return {
        "generated_for": today.isoformat(),
        "library_total": len(library),
        "matches": matches[:12],
        "popular": popular,
    }


# ---------------------------------------------------------------- first weeks

NEW_MEMBER_DAYS = 30


def _review_target(db: Session, user_id: int) -> Optional[dict]:
    """A title from the member's library that has a public title page to review on, finished ones first."""
    from . import title_pages
    candidates = []
    for kind, (model, *_rest) in title_pages.KINDS.items():
        finished = getattr(model, title_pages.COMPLETE_FIELD[kind])
        rows = (db.query(model).filter(model.user_id == user_id, model.title.isnot(None))
                .order_by(finished.desc(), model.id.desc()).limit(3).all())
        candidates += [(bool(getattr(row, title_pages.COMPLETE_FIELD[kind])), row.id, kind, row) for row in rows]
    candidates.sort(key=lambda c: (not c[0], -c[1]))
    for _, _, kind, item in candidates[:8]:
        if not (item.title or "").strip():
            continue
        path = title_pages.path_for_item(kind, item)
        if title_pages.find(db, kind, path.rsplit("/", 1)[1]) is not None:
            return {"title": item.title.strip(), "path": path}
    return None


def first_week(db: Session, user, now: Optional[datetime] = None) -> dict:
    """The social steps of the library launchpad, for members who joined in the last NEW_MEMBER_DAYS days."""
    from . import digest
    now = now or datetime.utcnow()
    if not user.created_at or user.created_at < now - timedelta(days=NEW_MEMBER_DAYS):
        return {"show": False}
    friend = (db.query(models.Friendship.id).filter((models.Friendship.user1_id == user.id)
                                                     | (models.Friendship.user2_id == user.id)).first() is not None
              or db.query(models.FriendRequest.id).filter(models.FriendRequest.sender_id == user.id,
                                                          models.FriendRequest.status == "pending").first() is not None)
    public_review = any(
        db.query(model.id).filter(model.user_id == user.id, model.review_public.is_(True),
                                  func.length(func.trim(model.review)) > 0).first() is not None
        for model, _ in LIBRARY.values())
    return {
        "show": True,
        "friend": friend,
        "public_review": public_review,
        "review_target": None if public_review else _review_target(db, user.id),
        "weekly_email": digest.subscription_for(db, user.id) is not None,
        "email_available": digest.mail_configured(),
        "verified": bool(user.is_verified),
    }
