"""Year in Review: a member's year in media, built only from dates we actually recorded.

Sources, all private to the member until they choose to share:
- activity journal entries (finished, started, notes) by ``occurred_at``,
- completion moments (favorites and ratings at the moment of finishing),
- library ``added_at`` dates, which only exist for items added after add-date
  tracking began, so the first tracked year is labelled as partial.

A shared recap is a frozen snapshot: categories the member marked private are
left out, and notes, reviews and journal text are never included.
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from . import models

# Library category -> (model, plural label, done field, completion verb, privacy flag on the user)
CATEGORIES = {
    "movies": (models.Movie, "Movies", "watched", "watched", "movies_private"),
    "tv-shows": (models.TVShow, "TV shows", "watched", "watched", "tv_shows_private"),
    "anime": (models.Anime, "Anime", "watched", "watched", "anime_private"),
    "video-games": (models.VideoGame, "Games", "played", "played", "video_games_private"),
    "music": (models.Music, "Albums", "listened", "listened to", "music_private"),
    "books": (models.Book, "Books", "read", "read", "books_private"),
    "manga": (models.Manga, "Manga", "read", "read", "manga_private"),
    "podcasts": (models.Podcast, "Podcasts", "listened", "listened to", "podcasts_private"),
    "audiobooks": (models.Audiobook, "Audiobooks", "listened", "listened to", "audiobooks_private"),
}
# Add dates were first recorded in October 2026; earlier items have none.
ADD_DATES_FIRST_YEAR = 2026
TOP_FINISHES_LIMIT = 5
FAVORITES_LIMIT = 6
MIN_RATINGS = 3
PERSONA_MIN_FINISHES = 3
# Shelves with a creator field: category -> (model, field, what to call the person)
CREATORS = {
    "movies": (models.Movie, "director", "director"),
    "music": (models.Music, "artist", "artist"),
    "books": (models.Book, "author", "author"),
    "manga": (models.Manga, "author", "mangaka"),
    "podcasts": (models.Podcast, "host", "host"),
    "audiobooks": (models.Audiobook, "author", "author"),
}
# Library category -> title-page kind, for reading the shared title_metadata cache.
KINDS = {"movies": "movie", "tv-shows": "tv", "anime": "anime", "video-games": "game", "music": "album",
         "books": "book", "manga": "manga", "podcasts": "podcast", "audiobooks": "audiobook"}
# Shelves whose rows carry a genre the member typed or imported.
GENRE_FIELDS = {"video-games": "genres", "music": "genre", "books": "genre", "manga": "genre",
                "podcasts": "genre", "audiobooks": "genre"}
TOP_GENRES_LIMIT = 5
MAX_GENRE_LENGTH = 40
CLASSIC_AGE = 20          # a finish released this many years ago or more counts as a classic
MIN_RELEASE_YEAR = 1850
FRIENDS_LIMIT = 3         # friends shown on the private recap
FRIENDS_CHECKED_MAX = 40  # friends compared; two queries each
FRIEND_TITLES_LIMIT = 3
MIN_HOURS = 1
# Persona when one shelf is most of the year's finishes: (name, line with {n} finishes)
SHELF_PERSONAS = {
    "movies": ("The Movie Night Regular", "{n} movies finished. The couch knows your shape by now."),
    "tv-shows": ("The Binger", "{n} shows finished. One more episode was always the plan."),
    "anime": ("The Anime Marathoner", "{n} anime finished, openings unskipped."),
    "video-games": ("The Quest Finisher", "{n} games played through to the end."),
    "music": ("The Crate Digger", "{n} albums listened to, start to finish."),
    "books": ("The Bookworm", "{n} books read. Your bookmark worked overtime."),
    "manga": ("The Volume Hoarder", "{n} manga series read, right to left."),
    "podcasts": ("The Commuter", "{n} podcasts heard all the way through."),
    "audiobooks": ("The Long Drive", "{n} audiobooks finished, one chapter at a time."),
}


def season_year(today: Optional[date] = None) -> Optional[int]:
    """The recap year to promote in the app: December for this year, January for last year."""
    today = today or datetime.utcnow().date()
    if today.month == 12:
        return today.year
    if today.month == 1:
        return today.year - 1
    return None


def available_years(user: models.User, today: Optional[date] = None) -> list[int]:
    today = today or datetime.utcnow().date()
    first = max(user.created_at.year if user.created_at else today.year, 2020)
    return list(range(today.year, first - 1, -1))


def _visible(user: models.User, public: bool) -> list[str]:
    return [key for key, details in CATEGORIES.items() if not (public and getattr(user, details[4], False))]


def _title_key(category: str, item_id, title: str) -> tuple:
    # Deleting a title clears its journal item_id and gives its moment a negative one;
    # key both by title then so one finish still counts once.
    if item_id is not None and item_id > 0:
        return (category, item_id)
    return (category, " ".join((title or "").lower().split()))


def _year_bounds(year: int) -> tuple[datetime, datetime]:
    return datetime(year, 1, 1), datetime(year + 1, 1, 1)


def _finishes(db: Session, user_id: int, year: int, visible: list[str]) -> tuple[list, dict[tuple, dict]]:
    """(journal entries, finished titles) for the year; each title counts once, however many times it was logged."""
    start, end = _year_bounds(year)
    entries = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == user_id,
        models.ActivityEntry.occurred_at >= start,
        models.ActivityEntry.occurred_at < end,
        models.ActivityEntry.category.in_(visible),
    ).order_by(models.ActivityEntry.occurred_at.asc(), models.ActivityEntry.id.asc()).all()
    moments = db.query(models.CompletionMoment).filter(
        models.CompletionMoment.user_id == user_id,
        models.CompletionMoment.completed_at >= start,
        models.CompletionMoment.completed_at < end,
        models.CompletionMoment.category.in_(visible),
    ).order_by(models.CompletionMoment.completed_at.asc()).all()

    finished: dict[tuple, dict] = {}
    for entry in entries:
        if entry.action != "completed":
            continue
        key = _title_key(entry.category, entry.item_id, entry.title)
        finished.setdefault(key, {
            "category": entry.category, "title": entry.title, "rating": entry.rating,
            "finished_at": entry.occurred_at, "favorite": False, "item_id": entry.item_id,
        })
    for moment in moments:
        key = _title_key(moment.category, moment.item_id, moment.title)
        row = finished.setdefault(key, {
            "category": moment.category, "title": moment.title, "rating": moment.rating,
            "finished_at": moment.completed_at, "favorite": False, "item_id": moment.item_id,
        })
        row["favorite"] = row["favorite"] or bool(moment.favorite)
        if row.get("item_id") is None:
            row["item_id"] = moment.item_id
        if row["rating"] is None:
            row["rating"] = moment.rating
    return entries, finished


def finished_counts(db: Session, user_id: int, year: int) -> dict[str, int]:
    """Titles finished in the year per category, counted exactly as the recap counts them."""
    _, finished = _finishes(db, user_id, year, list(CATEGORIES))
    counts = {key: 0 for key in CATEGORIES}
    for row in finished.values():
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    return counts


def build(db: Session, user: models.User, year: int, *, public: bool = False) -> dict:
    """The recap for one calendar year (UTC). ``public`` drops categories the member keeps private."""
    start, end = _year_bounds(year)
    visible = _visible(user, public)
    entries, finished = _finishes(db, user.id, year, visible)
    moment_days = [row[0] for row in db.query(models.CompletionMoment.completed_at).filter(
        models.CompletionMoment.user_id == user.id,
        models.CompletionMoment.completed_at >= start,
        models.CompletionMoment.completed_at < end,
        models.CompletionMoment.category.in_(visible),
    ).all()]

    categories = []
    for key in visible:
        model, label, done_field, verb, _ = CATEGORIES[key]
        total, done, added = db.query(
            func.count(model.id),
            func.sum(case((getattr(model, done_field) == True, 1), else_=0)),
            func.sum(case(((model.added_at >= start) & (model.added_at < end), 1), else_=0)),
        ).filter(model.user_id == user.id).one()
        finished_count = sum(1 for row in finished.values() if row["category"] == key)
        if not (total or finished_count):
            continue
        categories.append({
            "category": key, "label": label, "verb": verb,
            "finished": finished_count, "added": int(added or 0),
            "library_total": int(total or 0), "library_finished": int(done or 0),
        })

    month_counts = [0] * 12
    for entry in entries:
        month_counts[entry.occurred_at.month - 1] += 1
    busiest = max(range(12), key=lambda m: month_counts[m]) if any(month_counts) else None

    ordered = sorted(finished.values(), key=lambda row: row["finished_at"])
    rated = sorted((row for row in ordered if row["rating"] is not None),
                   key=lambda row: (-row["rating"], row["finished_at"]))
    labels = {key: CATEGORIES[key][1] for key in CATEGORIES}

    def _public_row(row):
        return {"category": row["category"], "label": labels[row["category"]], "title": row["title"],
                "rating": row["rating"], "month": row["finished_at"].strftime("%B")}

    finished_total = len(finished)
    top_category = max(categories, key=lambda c: (c["finished"], c["library_total"])) if categories else None
    if top_category and not top_category["finished"]:
        top_category = None
    library_total = sum(c["library_total"] for c in categories)
    recap = {
        "year": year,
        "username": user.username,
        "finished_total": finished_total,
        "added_total": sum(c["added"] for c in categories),
        "added_partial": year == ADD_DATES_FIRST_YEAR,
        "added_since": "October" if year == ADD_DATES_FIRST_YEAR else None,
        "moments_total": len(entries),
        "categories": categories,
        "top_category": {"category": top_category["category"], "label": top_category["label"],
                         "finished": top_category["finished"]} if top_category else None,
        "busiest_month": {"month": date(year, busiest + 1, 1).strftime("%B"), "count": month_counts[busiest]}
        if busiest is not None else None,
        "months": month_counts,
        "first_finish": _public_row(ordered[0]) if ordered else None,
        "last_finish": _public_row(ordered[-1]) if len(ordered) > 1 else None,
        "top_rated": [_public_row(row) for row in rated[:TOP_FINISHES_LIMIT]],
        "favorites": [_public_row(row) for row in ordered if row["favorite"]][:FAVORITES_LIMIT],
        "library_total": library_total,
        "is_empty": not (finished_total or entries or library_total),
    }
    recap["goals"] = _goals(db, user, year, finished, public)
    days = {entry.occurred_at.date() for entry in entries} | {moment.date() for moment in moment_days if moment}
    recap["active_days"] = len(days)
    recap["longest_streak"] = _longest_streak(days)
    recap["ratings"] = _rating_style(ordered)
    recap["top_creator"] = _top_creator(db, user.id, ordered)
    recap["badges"] = _badges(db, user, year, public)
    items = _library_items(db, user.id, ordered)
    recap["genres"] = _genres(db, ordered, items)
    recap["releases"] = _release_mix(year, ordered, items)
    recap["time"] = _time(db, user, year, visible)
    recap["persona"] = persona(recap)
    if not public:
        recap["reflections_total"] = sum(1 for entry in entries if (entry.note or "").strip())
        recap["friends"] = _friends(db, user, year, finished, visible)
    return recap


def _goals(db: Session, user: models.User, year: int, finished: dict, public: bool) -> list[dict]:
    """The member's goals for the year, counted from the recap's own finishes. Optional: never breaks the recap."""
    from . import goals
    counts = {key: 0 for key in CATEGORIES}
    for row in finished.values():
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    try:
        return goals.progress(db, user, year, counts=counts,
                              categories=goals.public_categories(user) if public else None)
    except Exception:
        db.rollback()
        return []


def _longest_streak(days: set) -> int:
    """Most days in a row with at least one journal moment or finish."""
    best = 0
    for day in days:
        if day - timedelta(days=1) in days:
            continue
        run = 1
        while day + timedelta(days=run) in days:
            run += 1
        best = max(best, run)
    return best


def _rating_style(ordered: list[dict]) -> Optional[dict]:
    """How the member rated what they finished this year; None below MIN_RATINGS ratings."""
    ratings = [float(row["rating"]) for row in ordered if row["rating"] is not None]
    if len(ratings) < MIN_RATINGS:
        return None
    average = round(sum(ratings) / len(ratings), 1)
    if average >= 8.5:
        style, detail = "Easy to please", "Most of what you finished, you loved."
    elif average < 6.5:
        style, detail = "Tough critic", "A high score from you had to be earned."
    else:
        style, detail = "Fair judge", "You used the whole scale and meant it."
    return {"average": average, "count": len(ratings), "style": style, "detail": detail,
            "tens": sum(1 for value in ratings if value >= 10)}


def _top_creator(db: Session, user_id: int, ordered: list[dict]) -> Optional[dict]:
    """The director, artist or author behind the most finishes this year, when at least two share one."""
    tally: dict[str, dict] = {}
    for category, (model, field, noun) in CREATORS.items():
        ids = [row["item_id"] for row in ordered if row["category"] == category and (row.get("item_id") or 0) > 0]
        if not ids:
            continue
        for (name,) in db.query(getattr(model, field)).filter(model.user_id == user_id, model.id.in_(ids)).all():
            name = " ".join((name or "").split())
            if not name:
                continue
            row = tally.setdefault(f"{category}:{name.lower()}", {
                "name": name, "category": category, "label": CATEGORIES[category][1], "role": noun, "count": 0})
            row["count"] += 1
    best = max(tally.values(), key=lambda row: row["count"], default=None)
    return best if best and best["count"] >= 2 else None


def _badges(db: Session, user: models.User, year: int, public: bool) -> list[dict]:
    """Badge tiers reached during the year. Optional: never breaks the recap."""
    from . import badges
    try:
        public_keys = {row["key"] for row in badges.public_badges(db, user)} if public else None
        start, end = _year_bounds(year)
        rows = db.query(models.UserBadge).filter(
            models.UserBadge.user_id == user.id,
            models.UserBadge.earned_at >= start, models.UserBadge.earned_at < end,
        ).all()
    except Exception:
        db.rollback()
        return []
    out = []
    for row in rows:
        track = badges.BY_KEY.get(row.badge)
        if track is None or not 1 <= (row.tier or 0) <= len(badges.TIERS):
            continue
        if public_keys is not None and row.badge not in public_keys:
            continue
        out.append({"name": track["name"], "emoji": track["emoji"], "tier": row.tier,
                    "tier_name": badges.TIERS[row.tier - 1]})
    out.sort(key=lambda row: (-row["tier"], row["name"]))
    return out


def _library_items(db: Session, user_id: int, ordered: list[dict]) -> dict[tuple, object]:
    """The member's own library rows behind this year's finishes, keyed (category, item id). One query per shelf."""
    found: dict[tuple, object] = {}
    for category, (model, *_rest) in CATEGORIES.items():
        ids = [row["item_id"] for row in ordered if row["category"] == category and (row.get("item_id") or 0) > 0]
        if not ids:
            continue
        for item in db.query(model).filter(model.user_id == user_id, model.id.in_(ids)).all():
            found[(category, item.id)] = item
    return found


def _split_genres(value) -> list[str]:
    if not isinstance(value, str):
        return []
    out = []
    for part in value.replace("/", ",").replace(";", ",").replace("|", ",").split(","):
        name = " ".join(part.split()).strip(" .")
        if 1 < len(name) <= MAX_GENRE_LENGTH:
            out.append(name)
    return out


def _cached_genres(db: Session, keys: list[str]) -> dict[str, list[str]]:
    """Genres a title page already looked up, from the shared cache. Only read, never fetched."""
    import json

    keys = list(dict.fromkeys(keys))
    found: dict[str, list[str]] = {}
    for start in range(0, len(keys), 500):
        try:
            rows = db.query(models.TitleMetadata.key, models.TitleMetadata.data).filter(
                models.TitleMetadata.key.in_(keys[start:start + 500]),
                models.TitleMetadata.status == "ok",
            ).all()
        except Exception:
            db.rollback()
            return found
        for key, data in rows:
            try:
                parsed = json.loads(data) if data else None
            except ValueError:
                continue
            genres = (parsed or {}).get("genres") if isinstance(parsed, dict) else None
            if isinstance(genres, list):
                found[key] = [g for g in genres if isinstance(g, str) and 1 < len(g) <= MAX_GENRE_LENGTH]
    return found


def _genres(db: Session, ordered: list[dict], items: dict[tuple, object]) -> list[dict]:
    """The genres behind this year's finishes, each title counted once per genre. Empty when nothing is tagged."""
    from . import title_metadata, title_pages

    keys = {}
    for (category, item_id), item in items.items():
        kind = KINDS[category]
        keys[(category, item_id)] = title_metadata.cache_key(kind, title_pages.normalize(item.title or ""),
                                                             title_pages.item_year(kind, item))
    cached = _cached_genres(db, list(keys.values())) if keys else {}
    tally: dict[str, dict] = {}
    for row in ordered:
        key = (row["category"], row.get("item_id"))
        item = items.get(key)
        if item is None:
            continue
        names = _split_genres(getattr(item, GENRE_FIELDS.get(row["category"], ""), None))
        names += cached.get(keys[key], [])
        seen = set()
        for name in names:
            slug = name.casefold()
            if slug in seen:
                continue
            seen.add(slug)
            entry = tally.setdefault(slug, {"name": name, "count": 0})
            entry["count"] += 1
    ranked = sorted(tally.values(), key=lambda entry: (-entry["count"], entry["name"].casefold()))
    return ranked[:TOP_GENRES_LIMIT]


def _release_mix(year: int, ordered: list[dict], items: dict[tuple, object]) -> Optional[dict]:
    """How many finishes came out this year, how many are classics, and the oldest one. None without release years."""
    from . import title_pages

    dated = []
    for row in ordered:
        item = items.get((row["category"], row.get("item_id")))
        if item is None:
            continue
        released = title_pages.item_year(KINDS[row["category"]], item)
        if isinstance(released, int) and MIN_RELEASE_YEAR <= released <= year + 1:
            dated.append((released, row))
    if not dated:
        return None
    labels = {key: CATEGORIES[key][1] for key in CATEGORIES}
    oldest_year, oldest = min(dated, key=lambda pair: (pair[0], pair[1]["finished_at"]))
    return {
        "dated": len(dated),
        "new": sum(1 for released, _ in dated if released >= year),
        "classics": sum(1 for released, _ in dated if year - released >= CLASSIC_AGE),
        "oldest": {"title": oldest["title"], "year": oldest_year, "label": labels[oldest["category"]],
                   "age": year - oldest_year},
        "average_age": round(sum(year - released for released, _ in dated) / len(dated)),
    }


def _time(db: Session, user: models.User, year: int, visible: list[str]) -> Optional[dict]:
    """Estimated hours behind this year's finishes, from Time Spent. Optional: never breaks the recap."""
    from . import time_spent
    try:
        estimate = time_spent.estimate(db, user, categories=visible, year=year)
    except Exception:
        db.rollback()
        return None
    minutes = estimate.get("year_minutes") or 0
    if minutes < MIN_HOURS * 60:
        return None
    shelves = sorted((row for row in estimate.get("categories", []) if row.get("year_minutes")),
                     key=lambda row: -row["year_minutes"])
    return {
        "hours": int(round(minutes / 60)),
        "days": round(minutes / 60 / 24, 1),
        "line": time_spent.comparison(minutes),
        "shelves": [{"category": row["category"], "label": row["label"], "verb": row["verb"],
                     "hours": round(row["year_minutes"] / 60, 1)} for row in shelves],
        "estimated": True,
    }


def _friends(db: Session, user: models.User, year: int, finished: dict, visible: list[str]) -> Optional[dict]:
    """Friends who finished the same titles this year. Private to the member; shelves a friend keeps private are skipped."""
    from .crud import friends as friend_crud
    try:
        friends = [f for f in friend_crud.get_friends(db, user.id) if f.id != user.id][:FRIENDS_CHECKED_MAX]
    except Exception:
        db.rollback()
        return None
    if not friends:
        return None
    mine: dict[tuple, dict] = {}
    for row in sorted(finished.values(), key=lambda row: row["finished_at"]):
        mine.setdefault((row["category"], " ".join((row["title"] or "").casefold().split())), row)
    matches = []
    for friend in friends:
        shared = [key for key in visible if not getattr(friend, CATEGORIES[key][4], False)]
        if not shared:
            continue
        _, theirs = _finishes(db, friend.id, year, shared)
        common = [mine[key] for key in (
            (row["category"], " ".join((row["title"] or "").casefold().split())) for row in theirs.values()
        ) if key in mine]
        if not common:
            continue
        common.sort(key=lambda row: row["finished_at"])
        matches.append({"username": friend.username, "count": len(common),
                        "titles": [row["title"] for row in common[:FRIEND_TITLES_LIMIT]]})
    matches.sort(key=lambda match: (-match["count"], match["username"].casefold()))
    return {"checked": len(friends), "matches": matches[:FRIENDS_LIMIT]}


def persona(recap: dict) -> Optional[dict]:
    """A one-line label for the year, picked from the recap's own numbers. None for a quiet year."""
    finished = recap.get("finished_total") or 0
    if finished < PERSONA_MIN_FINISHES:
        return None
    shelves = [c for c in recap.get("categories", []) if c.get("finished")]
    if len(shelves) >= 4:
        name, line = "The Omnivore", f"You finished something in {len(shelves)} different shelves. Nothing was off the menu."
        return {"key": "omnivore", "name": name, "line": line}
    top = recap.get("top_category")
    if top and top["finished"] / finished >= 0.6:
        name, line = SHELF_PERSONAS[top["category"]]
        return {"key": top["category"], "name": name, "line": line.format(n=top["finished"])}
    releases = recap.get("releases") or {}
    if releases.get("dated", 0) >= PERSONA_MIN_FINISHES and releases["classics"] / releases["dated"] >= 0.5:
        return {"key": "time-traveler", "name": "The Time Traveler",
                "line": f"{releases['classics']} of your {releases['dated']} dated finishes came out {CLASSIC_AGE} or more years ago. New releases can wait."}
    if (recap.get("longest_streak") or 0) >= 7:
        return {"key": "regular", "name": "The Regular",
                "line": f"Your longest run was {recap['longest_streak']} days in a row with something logged."}
    ratings = recap.get("ratings") or {}
    if ratings.get("style") == "Tough critic":
        return {"key": "critic", "name": "The Critic", "line": f"Your finishes averaged {ratings['average']:g}/10. You don't hand out tens."}
    return {"key": "mixer", "name": "The Mixtape", "line": f"You split your year between {len(shelves)} shelves and kept it moving."}


# ---------------------------------------------------------------- sharing

def get_share(db: Session, user_id: int, year: int) -> Optional[models.YearInReviewShare]:
    return db.query(models.YearInReviewShare).filter(
        models.YearInReviewShare.user_id == user_id, models.YearInReviewShare.year == year,
    ).first()


def find_share(db: Session, token: str) -> Optional[models.YearInReviewShare]:
    if not token or len(token) > 64:
        return None
    share = db.query(models.YearInReviewShare).filter(models.YearInReviewShare.token == token).first()
    if share is None or share.owner is None or not share.owner.is_active:
        return None
    return share


def share_path(share: models.YearInReviewShare) -> str:
    return f"/recap/{share.token}"


def save_share(db: Session, user: models.User, year: int) -> models.YearInReviewShare:
    """Create or refresh the member's public snapshot for this year. The link stays the same."""
    import json

    snapshot = json.dumps(build(db, user, year, public=True), default=str)
    share = get_share(db, user.id, year)
    if share is None:
        share = models.YearInReviewShare(user_id=user.id, year=year, token=secrets.token_urlsafe(12))
        db.add(share)
    share.snapshot = snapshot
    share.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(share)
    return share


def delete_share(db: Session, user_id: int, year: int) -> bool:
    share = get_share(db, user_id, year)
    if share is None:
        return False
    db.delete(share)
    db.commit()
    return True


def snapshot(share: models.YearInReviewShare) -> dict:
    import json

    try:
        data = json.loads(share.snapshot or "{}")
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}
