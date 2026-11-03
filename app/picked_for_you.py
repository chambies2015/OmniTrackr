"""Picks for one member, built from what other members track and rate (the "For you" tab).

Two signals, both read from libraries already in the database:

* Taste neighbours: members whose libraries overlap with yours and who rated the
  shared titles the way you did. What they liked and you haven't saved scores
  highest. A title needs two of them behind it before it can be suggested, so a
  pick never points at one person's library.
* Genres: titles that share genres with what you rated well, read from the genre
  fields members fill in and from cached title facts (title_metadata).

When both are thin (a new member, or a niche library), the most tracked titles in
the formats the member uses fill the gaps.

Private categories never feed anyone else's picks, and the editors account never
counts. The member's own library, private parts included, is only ever used for
their own picks. Nothing here calls an outside service.
"""
from __future__ import annotations

import hashlib
import math
import re
import threading
import time
from collections import Counter, defaultdict
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from . import models, title_pages
from .for_you import LIBRARY, _safe_image

KINDS = tuple(title_pages.KINDS)
KIND_TO_LIBRARY = {kind: library for kind, (_, _, library, _, _) in title_pages.KINDS.items()}
PLURAL = {"movie": "movies", "tv": "TV shows", "anime": "anime", "game": "games", "album": "albums",
          "book": "books", "manga": "manga", "podcast": "podcasts", "audiobook": "audiobooks"}
GENRE_COLUMN = {"game": "genres", "album": "genre", "book": "genre", "manga": "genre",
                "podcast": "genre", "audiobook": "genre"}

POOL_SECONDS = 600
RESULT_SECONDS = 600
SCAN_LIMIT = 60000
MIN_SUPPORTERS = 2        # A pick backed by one member would point straight at them.
MIN_POPULAR_MEMBERS = 2
NEIGHBOURS = 60
PICK_LIMIT = 48
ROW_LIMIT = 3
ROW_SIZE = 8
GUIDE_LIMIT = 3
DISMISS_LIMIT = 2000
ANCHOR_CANDIDATES = 160

_SPLIT = re.compile(r"\s*[,/;|]\s*")


def affinity(rating: Optional[float], done: bool, centre: float = 6.0) -> float:
    """How much a member seems to like a title, from -1 to 1.

    A rating counts most: one around the member's own usual score is neutral, three
    points above is a clear yes. Without a rating, finishing something is a mild
    yes and saving it a weaker one.
    """
    if rating is not None:
        try:
            value = float(rating)
        except (TypeError, ValueError):
            value = None
        if value is not None and 0 <= value <= 10:
            return max(-1.0, min(1.0, (value - centre) / 3.0))
    return 0.45 if done else 0.25


def rating_centre(ratings: Iterable[float]) -> float:
    """The neutral point for a member's ratings: a bit under their own average, kept between 5 and 7.5."""
    values = [float(r) for r in ratings if r is not None and 0 <= float(r) <= 10]
    if len(values) < 5:
        return 6.0
    return max(5.0, min(7.5, sum(values) / len(values) - 0.5))


def split_genres(value) -> list[str]:
    if not value or not isinstance(value, str):
        return []
    keys = []
    for part in _SPLIT.split(value):
        key = title_pages.genre_key(part)
        if key and len(key) <= 40 and key not in keys:
            keys.append(key)
    return keys[:8]


def pick_id(kind: str, slug: str, year: Optional[int]) -> str:
    return f"{kind}/{slug}-{year}" if year else f"{kind}/{slug}"


def parse_pick_id(value: str) -> Optional[tuple[str, str, Optional[int]]]:
    """(kind, title slug, year) from "movie/interstellar-2014"; the year is the trailing four digits, if any."""
    kind, _, rest = (value or "").partition("/")
    if kind not in title_pages.KINDS or not rest or len(rest) > 140 or not re.fullmatch(r"[a-z0-9-]+", rest):
        return None
    # Split off the year with plain string checks rather than a backtracking pattern.
    base, _, year = rest.rpartition("-")
    if base and len(year) == 4 and year.isdigit():
        return kind, base, int(year)
    return kind, rest, None


# ---------------------------------------------------------------- shared pool

class Pool:
    """Every shareable library row, grouped by title, plus each member's likes. Rebuilt every POOL_SECONDS."""

    def __init__(self):
        self.titles: dict[tuple, dict] = {}            # (kind, slug, year) -> title facts
        self.likes: dict[int, dict[tuple, float]] = {}  # member id -> {title key: affinity}
        self.norms: dict[int, float] = {}
        self.by_kind_slug: dict[tuple, list[tuple]] = defaultdict(list)


def _rows(db: Session, kind: str):
    model = title_pages.KINDS[kind][0]
    year_column = model.release_date if kind == "game" else model.year
    done_column = getattr(model, title_pages.COMPLETE_FIELD[kind])
    image_column = getattr(model, title_pages.IMAGE_FIELD[kind])
    creator_field = title_pages.KINDS[kind][4]
    columns = [model.user_id, model.title, year_column, model.rating, done_column, image_column,
               getattr(model, creator_field) if creator_field else model.id,
               getattr(model, GENRE_COLUMN[kind]) if kind in GENRE_COLUMN else model.id]
    return (db.query(model).with_entities(*columns)
            .filter(model.user_id.in_(title_pages._shareable_ids(db, kind)),
                    ~model.user_id.in_(title_pages._editor_ids(db)))
            .order_by(model.id).limit(SCAN_LIMIT).all())


def _year(kind: str, value) -> Optional[int]:
    if kind == "game":
        return value.year if value else None
    return value or None


def build_pool(db: Session) -> Pool:
    pool = Pool()
    raw: dict[int, dict[tuple, tuple]] = defaultdict(dict)
    for kind in KINDS:
        creator_field = title_pages.KINDS[kind][4]
        for user_id, title, year_value, rating, done, image, creator, genres in _rows(db, kind):
            title = (title or "").strip()
            if not title:
                continue
            slug = title_pages.slugify(title)
            key = (kind, slug, _year(kind, year_value))
            entry = pool.titles.get(key)
            if entry is None:
                entry = pool.titles[key] = {"names": Counter(), "members": set(), "ratings": {}, "image": None,
                                            "creators": Counter(), "genres": Counter()}
                pool.by_kind_slug[(kind, slug)].append(key)
            entry["names"][title] += 1
            entry["members"].add(user_id)
            if rating is not None:
                entry["ratings"][user_id] = float(rating)
            if entry["image"] is None:
                entry["image"] = _safe_image(image)
            if creator_field and isinstance(creator, str) and creator.strip():
                entry["creators"][creator.strip()] += 1
            if kind in GENRE_COLUMN:
                for genre in split_genres(genres):
                    entry["genres"][genre] += 1
            raw[user_id][key] = (rating, bool(done))
    # Cached public facts add genres for films, shows and anime, which have no genre field.
    for kind in KINDS:
        try:
            facts = title_pages._genre_pool(db, kind)
        except Exception:
            db.rollback()
            facts = []
        for fact in facts:
            key = (kind, title_pages.slugify(fact["normalized"]), fact["year"])
            entry = pool.titles.get(key)
            if entry is not None:
                for genre in fact["genres"]:
                    entry["genres"][genre] += 2
    for user_id, rows in raw.items():
        centre = rating_centre(rating for rating, _ in rows.values())
        likes = {key: affinity(rating, done, centre) for key, (rating, done) in rows.items()}
        pool.likes[user_id] = likes
        pool.norms[user_id] = math.sqrt(sum(value * value for value in likes.values())) or 1.0
    for entry in pool.titles.values():
        entry["display"] = entry["names"].most_common(1)[0][0]
        entry["creator"] = entry["creators"].most_common(1)[0][0] if entry["creators"] else None
        # A genre only one member typed is too thin to match on, unless the title has nothing else.
        counted = [genre for genre, count in entry["genres"].most_common(8)]
        entry["genre_set"] = set(counted)
        entry["genre_order"] = counted
    return pool


_pool_lock = threading.Lock()
_pool_build_lock = threading.Lock()
_pool_cache: dict = {}
_result_lock = threading.Lock()
_result_cache: dict = {}


def pool(db: Session) -> Pool:
    """The shared pool, rebuilt by one request at a time once it is POOL_SECONDS old."""
    with _pool_lock:
        cached = _pool_cache.get("pool")
        if cached and time.monotonic() - cached[0] < POOL_SECONDS:
            return cached[1]
    if not _pool_build_lock.acquire(blocking=cached is None):
        return cached[1]
    try:
        with _pool_lock:
            current = _pool_cache.get("pool")
            if current and current is not cached and time.monotonic() - current[0] < POOL_SECONDS:
                return current[1]
        built = build_pool(db)
        with _pool_lock:
            _pool_cache["pool"] = (time.monotonic(), built)
        return built
    finally:
        _pool_build_lock.release()


def clear_cache() -> None:
    with _pool_lock:
        _pool_cache.clear()
    with _result_lock:
        _result_cache.clear()


def forget_member(user_id: int) -> None:
    with _result_lock:
        _result_cache.pop(user_id, None)


# ---------------------------------------------------------------- one member

def own_library(db: Session, user_id: int) -> dict[tuple, dict]:
    """The member's own titles (every category, private ones too), keyed like the pool."""
    mine: dict[tuple, dict] = {}
    for kind in KINDS:
        model = title_pages.KINDS[kind][0]
        year_column = model.release_date if kind == "game" else model.year
        done_column = getattr(model, title_pages.COMPLETE_FIELD[kind])
        genre_column = getattr(model, GENRE_COLUMN[kind]) if kind in GENRE_COLUMN else model.id
        for title, year_value, rating, done, genres in (
                db.query(model).with_entities(model.title, year_column, model.rating, done_column, genre_column)
                .filter(model.user_id == user_id).order_by(model.id)):
            title = (title or "").strip()
            if not title:
                continue
            key = (kind, title_pages.slugify(title), _year(kind, year_value))
            mine[key] = {"title": title, "rating": float(rating) if rating is not None else None, "done": bool(done),
                         "genres": split_genres(genres) if kind in GENRE_COLUMN else []}
    centre = rating_centre(entry["rating"] for entry in mine.values())
    for entry in mine.values():
        entry["like"] = affinity(entry["rating"], entry["done"], centre)
    return mine


def dismissed_ids(db: Session, user_id: int) -> set[str]:
    return {key for key, in db.query(models.ForYouDismissal.title_key)
            .filter(models.ForYouDismissal.user_id == user_id).limit(DISMISS_LIMIT)}


def _fingerprint(mine: dict, dismissed: set) -> str:
    digest = hashlib.sha1()
    for key in sorted(mine, key=repr):
        entry = mine[key]
        digest.update(repr((key, entry["rating"], entry["done"])).encode())
    for key in sorted(dismissed):
        digest.update(key.encode())
    return digest.hexdigest()


def _anchor_phrase(entry: dict) -> str:
    if entry["rating"] is not None:
        rating = entry["rating"]
        text = f"{rating:.1f}".rstrip("0").rstrip(".")
        return f"Because you rated {entry['title']} {text}/10"
    if entry["done"]:
        return f"Because you finished {entry['title']}"
    return f"Because you saved {entry['title']}"


def _neighbours(shared_pool: Pool, user_id: int, mine: dict) -> dict[int, float]:
    dot: Counter = Counter()
    overlap: Counter = Counter()
    for key, entry in mine.items():
        title = shared_pool.titles.get(key)
        if title is None:
            continue
        for other in title["members"]:
            if other == user_id:
                continue
            dot[other] += entry["like"] * shared_pool.likes[other][key]
            overlap[other] += 1
    if not dot:
        return {}
    my_norm = math.sqrt(sum(entry["like"] ** 2 for entry in mine.values())) or 1.0
    scores = {}
    for other, value in dot.items():
        if value <= 0:
            continue
        # Shrink matches that rest on one or two shared titles.
        shrink = overlap[other] / (overlap[other] + 2.0)
        scores[other] = value / (my_norm * shared_pool.norms[other]) * shrink
    best = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))[:NEIGHBOURS]
    return dict(best)


def _taste_scores(shared_pool: Pool, mine: dict, neighbours: dict[int, float], skip) -> dict[tuple, dict]:
    scores: dict[tuple, dict] = {}
    for other, similarity in neighbours.items():
        for key, like in shared_pool.likes[other].items():
            if skip(key):
                continue
            found = scores.setdefault(key, {"score": 0.0, "supporters": set()})
            found["score"] += similarity * like
            if like > 0:
                found["supporters"].add(other)
    kept = [(found["score"], key) for key, found in scores.items()
            if found["score"] > 0 and len(found["supporters"]) >= MIN_SUPPORTERS]
    kept.sort(key=lambda pair: (-pair[0], repr(pair[1])))
    liked_mine = {key: entry for key, entry in mine.items() if entry["like"] >= 0.4}
    results = {}
    for position, (score, key) in enumerate(kept):
        found = scores[key]
        anchor = None
        # Only the picks that can make the list get a reason; a big library would otherwise
        # compare every candidate with every favourite.
        if position < ANCHOR_CANDIDATES:
            # Which of the member's own favourites do these supporters share most?
            anchors: Counter = Counter()
            for other in found["supporters"]:
                anchors.update(liked_mine.keys() & {k for k, like in shared_pool.likes[other].items() if like > 0})
            eligible = [k for k, count in anchors.items() if count >= MIN_SUPPORTERS]
            if eligible:
                # Prefer the title that says the most: one of the same format, liked strongly, and not
                # simply something every neighbour tracks (that would explain every pick the same way).
                def strength(k):
                    spread = len(shared_pool.titles[k]["members"]) if k in shared_pool.titles else 1
                    same = 2.5 if k[0] == key[0] else 1.0
                    return (anchors[k] * same * (0.5 + liked_mine[k]["like"]) / math.sqrt(spread), repr(k))
                anchor = max(eligible, key=strength)
        results[key] = {"score": score, "supporters": len(found["supporters"]), "anchor": anchor}
    return results


def _genre_profile(shared_pool: Pool, mine: dict) -> dict[str, Counter]:
    profile: dict[str, Counter] = defaultdict(Counter)
    for key, entry in mine.items():
        if entry["like"] <= 0:
            continue
        genres = set(entry["genres"])
        title = shared_pool.titles.get(key)
        if title is not None:
            genres |= title["genre_set"]
        entry["genre_set"] = genres
        for genre in genres:
            profile[key[0]][genre] += entry["like"]
    return profile


def _genre_scores(shared_pool: Pool, mine: dict, skip) -> dict[tuple, dict]:
    profile = _genre_profile(shared_pool, mine)
    if not profile:
        return {}
    results = {}
    for key, title in shared_pool.titles.items():
        kind = key[0]
        weights = profile.get(kind)
        if not weights or not title["genre_set"] or len(title["members"]) < MIN_POPULAR_MEMBERS or skip(key):
            continue
        shared = [genre for genre in title["genre_order"] if weights.get(genre)]
        if len(shared) < min(2, len(title["genre_set"])):
            continue
        score = sum(weights[genre] for genre in shared) / math.sqrt(len(title["genre_set"]))
        score *= 1 + math.log(len(title["members"])) / 4
        results[key] = {"score": score, "shared": shared[:2], "anchor": None}
    # The member's own title that shares the most genres explains each of the best picks.
    favourites: dict[str, list] = defaultdict(list)
    for mine_key, entry in mine.items():
        if entry["like"] >= 0.4 and entry.get("genre_set"):
            favourites[mine_key[0]].append((mine_key, entry["genre_set"], entry["like"]))
    best_keys = sorted(results, key=lambda k: (-results[k]["score"], repr(k)))[:ANCHOR_CANDIDATES]
    for key in best_keys:
        genres = set(shared_pool.titles[key]["genre_set"]) & set(profile[key[0]])
        anchor, best, common = None, (0, 0.0), set()
        for mine_key, mine_genres, like in favourites.get(key[0], ()):
            overlap = mine_genres & genres
            if len(overlap) >= 2 and (len(overlap), like) > best:
                anchor, best, common = mine_key, (len(overlap), like), overlap
        if anchor is not None:
            results[key]["anchor"] = anchor
            results[key]["shared"] = [genre for genre in shared_pool.titles[key]["genre_order"] if genre in common][:2]
    return results


def _popular(shared_pool: Pool, mine: dict, skip, limit: int) -> dict[tuple, dict]:
    used = Counter(key[0] for key in mine)
    results = []
    for key, title in shared_pool.titles.items():
        members = len(title["members"])
        if members < MIN_POPULAR_MEMBERS + 1 or skip(key):
            continue
        # Formats the member already uses come first; a new member sees every format.
        weight = members * (1.5 if used.get(key[0]) else (1.0 if not used else 0.6))
        results.append((weight, key))
    results.sort(key=lambda pair: (-pair[0], repr(pair[1])))
    return {key: {"score": weight} for weight, key in results[:limit]}


def _normalised(found: dict) -> dict:
    top = max((entry["score"] for entry in found.values()), default=0) or 1.0
    return {key: entry["score"] / top for key, entry in found.items()}


def _card(shared_pool: Pool, key: tuple, mine: dict, taste: Optional[dict], genre: Optional[dict]) -> dict:
    kind, slug, year = key
    title = shared_pool.titles[key]
    ratings = list(title["ratings"].values())
    average = round(sum(ratings) / len(ratings), 1) if len(ratings) >= title_pages.MIN_RATINGS_SHOWN else None
    members = len(title["members"])
    anchor = None
    if taste and taste.get("anchor"):
        anchor = taste["anchor"]
        reason = _anchor_phrase(mine[anchor])
        detail = f"Saved by {taste['supporters']} members with similar taste"
        source = "taste"
    elif genre and genre.get("anchor"):
        anchor = genre["anchor"]
        shared = [name.capitalize() for name in genre["shared"]]
        reason = f"Shares {' and '.join(shared)} with {mine[anchor]['title']}"
        detail = f"Tracked by {members} members"
        source = "genre"
    elif taste:
        reason = "Popular with members who share your taste"
        detail = f"Saved by {taste['supporters']} of them"
        source = "taste"
    elif genre:
        shared = [name.capitalize() for name in genre["shared"]]
        reason = f"More {' and '.join(shared).lower() if shared else PLURAL[kind]}, which you rate well"
        detail = f"Tracked by {members} members"
        source = "genre"
    else:
        reason = f"One of the most tracked {PLURAL[kind]} on OmniTrackr"
        detail = f"Tracked by {members} members"
        source = "popular"
    return {
        "id": pick_id(kind, slug, year),
        "kind": kind,
        "category": KIND_TO_LIBRARY[kind],
        "label": title_pages.KINDS[kind][3],
        "title": title["display"],
        "year": year,
        "creator": title["creator"],
        "image": title["image"],
        "url": title_pages.title_path(kind, title["display"], year),
        "members": members,
        "average": average,
        "reason": reason,
        "detail": detail,
        "source": source,
        "anchor": pick_id(*anchor) if anchor else None,
        "anchor_title": mine[anchor]["title"] if anchor else None,
    }


def _diverse(ranked: list[tuple], limit: int) -> list[tuple]:
    """Best first, but each further pick of the same format counts for a little less."""
    chosen, seen = [], Counter()
    remaining = list(ranked)
    while remaining and len(chosen) < limit:
        best_index = max(range(len(remaining)), key=lambda i: (remaining[i][0] * 0.88 ** seen[remaining[i][1][0]], -i))
        score, key = remaining.pop(best_index)
        chosen.append((score, key))
        seen[key[0]] += 1
    return chosen


def _guides(mine: dict) -> list[dict]:
    """Our hand-written "If you liked" guides for the member's best-rated titles."""
    from . import if_you_liked
    best = sorted(((entry["like"], key) for key, entry in mine.items() if entry["like"] >= 0.4),
                  key=lambda pair: (-pair[0], repr(pair[1])))
    guides, seen = [], set()
    for _, key in best:
        slug = if_you_liked.for_title(key[0], mine[key]["title"])
        if slug and slug not in seen:
            seen.add(slug)
            guide = if_you_liked.guide(slug)
            guides.append({"title": f"If you liked {guide['anchor']['title']}", "url": if_you_liked.path(slug),
                           "anchor": mine[key]["title"]})
        if len(guides) >= GUIDE_LIMIT:
            break
    return guides


def picks_for(db: Session, user_id: int) -> dict:
    mine = own_library(db, user_id)
    dismissed = dismissed_ids(db, user_id)
    fingerprint = _fingerprint(mine, dismissed)
    with _result_lock:
        hit = _result_cache.get(user_id)
    if hit and hit[1] == fingerprint and time.monotonic() - hit[0] < RESULT_SECONDS:
        return hit[2]
    result = build_picks(pool(db), user_id, mine, dismissed)
    with _result_lock:
        if len(_result_cache) > 2000:
            _result_cache.clear()
        _result_cache[user_id] = (time.monotonic(), fingerprint, result)
    return result


def build_picks(shared_pool: Pool, user_id: int, mine: dict, dismissed: set[str]) -> dict:
    owned = {(kind, slug) for kind, slug, _ in mine}

    def skip(key: tuple) -> bool:
        return (key[0], key[1]) in owned or pick_id(*key) in dismissed or key not in shared_pool.titles

    neighbours = _neighbours(shared_pool, user_id, mine)
    taste = _taste_scores(shared_pool, mine, neighbours, skip)
    genre = _genre_scores(shared_pool, mine, skip)
    combined: Counter = Counter()
    for key, value in _normalised(taste).items():
        combined[key] += value
    for key, value in _normalised(genre).items():
        combined[key] += 0.6 * value
    ranked = sorted(((score, key) for key, score in combined.items()), key=lambda pair: (-pair[0], repr(pair[1])))
    chosen = _diverse(ranked, PICK_LIMIT)
    if len(chosen) < PICK_LIMIT // 2:
        # Popular titles only fill in after the personal picks, never ahead of them.
        popular = _popular(shared_pool, mine, lambda key: skip(key) or key in combined, PICK_LIMIT - len(chosen))
        ranked = sorted(((score, key) for key, score in _normalised(popular).items()),
                        key=lambda pair: (-pair[0], repr(pair[1])))
        chosen += _diverse(ranked, PICK_LIMIT - len(chosen))
    picks = [_card(shared_pool, key, mine, taste.get(key), genre.get(key)) for _, key in chosen]

    # "Because you liked X" rows: the anchors behind the most picks.
    by_anchor: dict[str, list[str]] = defaultdict(list)
    for pick in picks:
        if pick["anchor"]:
            by_anchor[pick["anchor"]].append(pick["id"])
    rows = []
    for anchor, ids in sorted(by_anchor.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        if len(ids) < 3 or len(rows) >= ROW_LIMIT:
            continue
        anchor_key = parse_pick_id(anchor)
        entry = mine.get(anchor_key) if anchor_key else None
        if entry is None:
            continue
        rows.append({"anchor": anchor, "title": entry["title"], "kind": anchor_key[0],
                     "label": title_pages.KINDS[anchor_key[0]][3], "rating": entry["rating"], "picks": ids[:ROW_SIZE]})
    rated = sum(1 for entry in mine.values() if entry["rating"] is not None)
    if not mine:
        state = "empty"
    elif not taste and not genre:
        state = "thin"
    else:
        state = "ready"
    return {
        "state": state,
        "library_total": len(mine),
        "rated": rated,
        "neighbours": len(neighbours),
        "picks": picks,
        "rows": rows,
        "guides": _guides(mine),
        "dismissed": len(dismissed),
    }


# ---------------------------------------------------------------- saving a pick

def entry_payload(db: Session, kind: str, slug: str, year: Optional[int]) -> Optional[dict]:
    """Public details for a pick from the most complete shareable entry (never ratings, notes or reviews)."""
    shared_pool = pool(db)
    key = (kind, slug, year)
    title = shared_pool.titles.get(key)
    if title is None or len(title["members"]) < MIN_POPULAR_MEMBERS:
        return None
    category = KIND_TO_LIBRARY[kind]
    model, fields = LIBRARY[category]
    names = list(title["names"])
    rows = (db.query(model).filter(model.title.in_(names), model.user_id.in_(title_pages._shareable_ids(db, kind)),
                                   ~model.user_id.in_(title_pages._editor_ids(db))).limit(200).all())
    rows = [row for row in rows if title_pages.slugify((row.title or "").strip()) == slug
            and title_pages.item_year(kind, row) == year]
    if not rows:
        return None
    image_field = title_pages.IMAGE_FIELD[kind]
    rows.sort(key=lambda row: (bool(_safe_image(getattr(row, image_field, None))),
                               sum(bool(getattr(row, field, None)) for field in fields), -row.id), reverse=True)
    source = rows[0]
    payload = {field: getattr(source, field, None) for field in fields}
    payload["title"] = (payload.get("title") or "").strip()
    payload[image_field] = _safe_image(payload.get(image_field))
    if "rawg_link" in payload:
        payload["rawg_link"] = _safe_image(payload["rawg_link"])
    return payload
