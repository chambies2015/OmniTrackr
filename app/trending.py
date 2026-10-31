"""Trending: the titles members are adding, starting and finishing right now (/trending, Oct 2026).

Member charts (/titles/<kind>) rank all-time ratings and /titles lists all-time
tracking. Trending looks only at the last 7 or 30 days, and compares them with the
7 or 30 days before, so the pages change every week.

A title earns points from each member who, inside the window, added it to their
library (1), logged a start or progress in their journal (1), or finished it (2).
Counts and averages follow the same rules as the weekly roundup and title pages:

* only members who keep that category shareable count, never the editors account;
* a title is named only once at least two members touched it in the window;
* an average rating is shown only from three ratings or more;
* journal entries brought in by an import never count, and a member who adds a
  pile of titles at once (an import, say) is scaled down so their whole batch counts
  as much as FULL_WEIGHT_TITLES titles would.

Nothing here names a member or shows what one member did.
"""
from __future__ import annotations

import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import models, title_pages

WINDOWS = {"week": 7, "month": 30}
WINDOW_WORDS = {"week": ("this week", "last week", "7 days"), "month": ("this month", "the month before", "30 days")}
MIN_MEMBERS = title_pages.RECENT_MIN_MEMBERS
RATING_MIN = title_pages.MIN_RATINGS_SHOWN
TOTALS_MIN_MEMBERS = 3  # Site-wide totals from one or two people would describe them, so wait for three.
FULL_WEIGHT_TITLES = 12
POINTS = {"added": 1.0, "active": 1.0, "finished": 2.0}
ACTIVE_ACTIONS = ("started", "progressed")
FINISH_ACTIONS = ("completed", "revisited")
KIND_LIMIT = 20
OVERALL_LIMIT = 25
LIST_LIMIT = 8
LEADERS_PER_KIND = 3
# Fewer named titles than this is a thin page: noindex, kept out of the sitemap.
INDEX_MIN_OVERALL = 8
INDEX_MIN_KIND = 5
CACHE_SECONDS = 600
SCAN_LIMIT = 60000

_lock = threading.Lock()
_build_lock = threading.Lock()
_cache: dict = {}


def path(kind: Optional[str] = None, window: str = "week") -> str:
    base = "/trending" + (f"/{kind}" if kind else "")
    return base + ("/month" if window == "month" else "")


# ---------------------------------------------------------------- scan

def _members(db: Session) -> set[int]:
    return {row[0] for row in db.query(models.User.id).filter(
        models.User.is_active == True, models.User.username != title_pages.EDITOR_USERNAME)}  # noqa: E712


def _year(kind: str, value) -> Optional[int]:
    if kind == "game":
        return value.year if value else None
    return value or None


def _columns(kind: str):
    model = title_pages.KINDS[kind][0]
    creator_field = title_pages.KINDS[kind][4]
    return model, [model.id, model.user_id, model.title, model.release_date if kind == "game" else model.year,
                   getattr(model, title_pages.IMAGE_FIELD[kind]),
                   getattr(model, creator_field) if creator_field else model.id]


def _period(moment: datetime, now: datetime, days: int) -> Optional[str]:
    if moment is None or moment > now:
        return None
    if moment >= now - timedelta(days=days):
        return "now"
    if moment >= now - timedelta(days=2 * days):
        return "before"
    return None


def scan(db: Session, now: Optional[datetime] = None) -> list[dict]:
    """Every signal from the last 60 days: one dict per (kind, title, member, signal, moment)."""
    now = now or datetime.utcnow()
    since = now - timedelta(days=2 * max(WINDOWS.values()))
    members = _members(db)
    shareable = {kind: {row[0] for row in title_pages._shareable_ids(db, kind)} & members for kind in title_pages.KINDS}
    signals: list[dict] = []
    titles: dict[tuple[str, int], tuple] = {}  # (kind, row id) -> (title, year, image, creator)

    def remember(kind, row):
        row_id, _, title, year_value, image, creator = row
        creator = creator if title_pages.KINDS[kind][4] and isinstance(creator, str) else None
        titles[(kind, row_id)] = ((title or "").strip(), _year(kind, year_value), title_pages._safe_image(image),
                                  creator.strip() if creator and creator.strip() else None)

    for kind in title_pages.KINDS:
        if not shareable[kind]:
            continue
        model, columns = _columns(kind)
        rows = (db.query(model).with_entities(*columns, model.added_at)
                .filter(model.added_at >= since, model.added_at <= now)
                .order_by(model.id).limit(SCAN_LIMIT).all())
        for row in rows:
            if row[1] not in shareable[kind]:
                continue
            remember(kind, row[:6])
            signals.append({"kind": kind, "row": row[0], "user": row[1], "signal": "added", "at": row[6], "rating": None})

    entry = models.ActivityEntry
    wanted: dict[str, set[int]] = defaultdict(set)
    journal = (db.query(entry.category, entry.item_id, entry.title, entry.user_id, entry.action, entry.rating, entry.occurred_at)
               .filter(entry.occurred_at >= since, entry.occurred_at <= now,
                       entry.action.in_(ACTIVE_ACTIONS + FINISH_ACTIONS), entry.source != "import")
               .order_by(entry.id).limit(SCAN_LIMIT).all())
    for category, item_id, title, user_id, action, rating, occurred_at in journal:
        kind = title_pages.LIBRARY_TO_KIND.get(category)
        if kind is None or user_id not in shareable[kind]:
            continue
        signals.append({"kind": kind, "row": item_id, "title": (title or "").strip(), "user": user_id,
                        "signal": "finished" if action in FINISH_ACTIONS else "active", "at": occurred_at,
                        "rating": float(rating) if rating is not None and action in FINISH_ACTIONS else None})
        if item_id and (kind, item_id) not in titles:
            wanted[kind].add(item_id)
    for kind, ids in wanted.items():
        model, columns = _columns(kind)
        ordered = sorted(ids)
        for start in range(0, len(ordered), 900):
            for row in db.query(model).with_entities(*columns).filter(model.id.in_(ordered[start:start + 900])):
                remember(kind, row)
    for signal in signals:
        found = titles.get((signal["kind"], signal["row"])) if signal["row"] else None
        if found and found[0]:
            signal["title"], signal["year"], signal["image"], signal["creator"] = found
        else:
            # The library row is gone or the entry was typed by hand: keep the journal's title, year unknown.
            signal.setdefault("title", "")
            signal["year"], signal["image"], signal["creator"] = None, None, None
    return [signal for signal in signals if signal["title"]]


# ---------------------------------------------------------------- ranking

def _group(signals: list[dict], window: str, now: datetime) -> dict:
    days = WINDOWS[window]
    groups: dict[tuple, dict] = {}
    by_slug: dict[tuple[str, str], tuple] = {}
    # Rows with a known year go first so a hand-typed journal entry joins its title instead of starting a new one.
    for signal in sorted(signals, key=lambda s: s["year"] is None):
        period = _period(signal["at"], now, days)
        if period is None:
            continue
        kind, slug = signal["kind"], title_pages.slugify(signal["title"])
        if not slug:
            continue
        key = (kind, slug, signal["year"])
        if signal["year"] is None and (kind, slug) in by_slug:
            key = by_slug[(kind, slug)]
        by_slug.setdefault((kind, slug), key)
        group = groups.setdefault(key, {"kind": kind, "year": key[2], "names": Counter(), "images": Counter(),
                                        "creators": Counter(), "now": defaultdict(set), "before": defaultdict(set),
                                        "ratings": {}})
        group["names"][signal["title"]] += 1
        if signal.get("image"):
            group["images"][signal["image"]] += 1
        if signal.get("creator"):
            group["creators"][signal["creator"]] += 1
        group[period][signal["user"]].add(signal["signal"])
        if period == "now" and signal["rating"] is not None:
            group["ratings"][signal["user"]] = signal["rating"]  # Signals arrive in id order: the latest wins.
    return groups


def _weights(groups: dict, period: str) -> dict[tuple[str, int], float]:
    """Per (kind, member): full weight up to FULL_WEIGHT_TITLES titles, then the batch shares that much."""
    touched: Counter = Counter()
    for group in groups.values():
        for user in group[period]:
            touched[(group["kind"], user)] += 1
    return {key: min(1.0, FULL_WEIGHT_TITLES / count) for key, count in touched.items()}


def _score(group: dict, period: str, weights: dict) -> float:
    return sum(weights[(group["kind"], user)] * sum(POINTS[s] for s in kinds) for user, kinds in group[period].items())


def _ranked(groups: dict, period: str) -> list[tuple]:
    weights = _weights(groups, period)
    scored = [(key, _score(group, period, weights)) for key, group in groups.items() if len(group[period]) >= MIN_MEMBERS]
    title = lambda key: groups[key]["names"].most_common(1)[0][0].casefold()
    scored.sort(key=lambda pair: (-pair[1], -len(groups[pair[0]][period]), title(pair[0])))
    return scored


def _entry(group: dict, score: float) -> dict:
    kind = group["kind"]
    display = group["names"].most_common(1)[0][0]
    now = group["now"]
    ratings = list(group["ratings"].values())
    return {
        "kind": kind, "title": display, "year": group["year"], "url": title_pages.title_path(kind, display, group["year"]),
        "image": group["images"].most_common(1)[0][0] if group["images"] else None,
        "creator": group["creators"].most_common(1)[0][0] if group["creators"] else None,
        "members": len(now),
        "added": sum("added" in s for s in now.values()),
        "active": sum("active" in s for s in now.values()),
        "finished": sum("finished" in s for s in now.values()),
        "rated": len(ratings),
        "average": round(sum(ratings) / len(ratings), 1) if len(ratings) >= RATING_MIN else None,
        "score": round(score, 2),
    }


def _with_movement(entries: list[dict], previous: dict) -> list[dict]:
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank
        before = previous.get(entry["url"])
        entry["previous_rank"] = before
        if before is None:
            entry["movement"], entry["change"] = "new", 0
        elif before > rank:
            entry["movement"], entry["change"] = "up", before - rank
        elif before < rank:
            entry["movement"], entry["change"] = "down", rank - before
        else:
            entry["movement"], entry["change"] = "same", 0
    return entries


def _totals(groups: dict, kinds) -> dict:
    users, adds, finishes = set(), 0, 0
    for group in groups.values():
        if group["kind"] not in kinds:
            continue
        users.update(group["now"])
        adds += sum("added" in s for s in group["now"].values())
        finishes += sum("finished" in s for s in group["now"].values())
    if len(users) < TOTALS_MIN_MEMBERS:
        return {"members": 0, "added": 0, "finished": 0}
    return {"members": len(users), "added": adds, "finished": finishes}


def _chart(groups: dict, keys: list, limit: int) -> list[dict]:
    """Entries for `keys` ranked now, with their place in the same chart one window earlier."""
    wanted = set(keys)
    subset = {key: group for key, group in groups.items() if key in wanted}
    now_ranked = _ranked(subset, "now")[:limit]
    before_ranked = _ranked(subset, "before")
    previous = {}
    for rank, (key, _) in enumerate(before_ranked, start=1):
        group = subset[key]
        previous[title_pages.title_path(group["kind"], group["names"].most_common(1)[0][0], group["year"])] = rank
    return _with_movement([_entry(subset[key], score) for key, score in now_ranked], previous)


def build_window(signals: list[dict], window: str, now: datetime) -> dict:
    groups = _group(signals, window, now)
    weights_now = _weights(groups, "now")
    named = [key for key, group in groups.items() if len(group["now"]) >= MIN_MEMBERS]
    kinds = {}
    for kind in title_pages.KINDS:
        keys = [key for key in groups if groups[key]["kind"] == kind]
        chart = _chart(groups, keys, KIND_LIMIT)
        own = [_entry(groups[key], _score(groups[key], "now", weights_now)) for key in named if groups[key]["kind"] == kind]
        finished = sorted((e for e in own if e["finished"] >= MIN_MEMBERS),
                          key=lambda e: (-e["finished"], -(e["average"] or 0), e["title"].casefold()))[:LIST_LIMIT]
        rated = sorted((e for e in own if e["average"] is not None),
                       key=lambda e: (-e["average"], -e["rated"], e["title"].casefold()))[:LIST_LIMIT]
        kinds[kind] = {"chart": chart, "finished": finished, "rated": rated, "totals": _totals(groups, {kind}),
                       "indexable": len(chart) >= INDEX_MIN_KIND}
    overall = _chart(groups, list(groups), OVERALL_LIMIT)
    every = [_entry(groups[key], _score(groups[key], "now", weights_now)) for key in named]
    finished = sorted((e for e in every if e["finished"] >= MIN_MEMBERS),
                      key=lambda e: (-e["finished"], -(e["average"] or 0), e["title"].casefold()))[:LIST_LIMIT]
    rated = sorted((e for e in every if e["average"] is not None),
                   key=lambda e: (-e["average"], -e["rated"], e["title"].casefold()))[:LIST_LIMIT]
    return {
        "window": window,
        "built_at": now.replace(microsecond=0).isoformat() + "Z",
        "overall": overall,
        "finished": finished,
        "rated": rated,
        "leaders": {kind: data["chart"][:LEADERS_PER_KIND] for kind, data in kinds.items() if data["chart"]},
        "kinds": kinds,
        "totals": _totals(groups, set(title_pages.KINDS)),
        "indexable": len(overall) >= INDEX_MIN_OVERALL,
    }


def build(db: Session, now: Optional[datetime] = None) -> dict:
    now = now or datetime.utcnow()
    signals = scan(db, now)
    return {window: build_window(signals, window, now) for window in WINDOWS}


def data(db: Session, window: str = "week") -> dict:
    """The cached trending data for one window (both windows rebuild together, at most every CACHE_SECONDS)."""
    if window not in WINDOWS:
        raise KeyError(window)
    with _lock:
        cached = _cache.get("all")
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1][window]
    if not _build_lock.acquire(blocking=cached is None):
        return cached[1][window]  # Another request is rebuilding; the previous data is fine meanwhile.
    try:
        with _lock:
            current = _cache.get("all")
            if current and current is not cached and time.monotonic() - current[0] < CACHE_SECONDS:
                return current[1][window]
        built = build(db)
        with _lock:
            _cache["all"] = (time.monotonic(), built)
        return built[window]
    finally:
        _build_lock.release()


def rank_of(db: Session, kind: str, url: str) -> Optional[dict]:
    """{"rank", "of", "window"} when the title at `url` is on its kind's weekly trending chart; never raises."""
    try:
        chart = data(db, "week")["kinds"][kind]["chart"]
    except Exception:
        db.rollback()
        return None
    for entry in chart:
        if entry["url"] == url:
            return {"rank": entry["rank"], "of": len(chart), "window": "week"}
    return None


def indexable_paths(db: Session) -> list[str]:
    paths = []
    for window in WINDOWS:
        try:
            found = data(db, window)
        except Exception:
            db.rollback()
            continue
        if found["indexable"]:
            paths.append(path(None, window))
        paths += [path(kind, window) for kind, info in found["kinds"].items() if info["indexable"]]
    return paths


def clear_cache() -> None:
    with _lock:
        _cache.clear()


# ---------------------------------------------------------------- write-up

def _plural(count: int, singular: str, plural: Optional[str] = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _join(words: list[str]) -> str:
    if len(words) <= 2:
        return " and ".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


NOUNS = {"movie": ("movie", "movies"), "tv": ("TV show", "TV shows"), "anime": ("anime", "anime"),
         "game": ("game", "games"), "album": ("album", "albums"), "book": ("book", "books"),
         "manga": ("manga", "manga"), "podcast": ("podcast", "podcasts"), "audiobook": ("audiobook", "audiobooks")}
FORMAT_NAMES = {"movie": "Movies", "tv": "TV shows", "anime": "Anime", "game": "Games", "album": "Albums", "book": "Books",
                "manga": "Manga", "podcast": "Podcasts", "audiobook": "Audiobooks"}
FINISH_VERBS = {"movie": "watched", "tv": "finished", "anime": "finished", "game": "beat or finished",
                "album": "listened to", "book": "finished", "manga": "finished", "podcast": "caught up on",
                "audiobook": "finished"}


def _what_members_did(entry: dict) -> str:
    parts = []
    if entry["added"]:
        parts.append(f"{entry['added']} added it")
    if entry["active"]:
        parts.append(f"{entry['active']} logged progress")
    if entry["finished"]:
        parts.append(f"{entry['finished']} {FINISH_VERBS[entry['kind']]} it")
    return _join(parts)


def paragraphs(found: dict, kind: Optional[str]) -> list[str]:
    """A short write-up of the chart, worked out from the numbers on the page."""
    window = found["window"]
    now_words, before_words, _ = WINDOW_WORDS[window]
    if kind:
        chart, finished, rated, totals = (found["kinds"][kind][key] for key in ("chart", "finished", "rated", "totals"))
        singular, plural = NOUNS[kind]
    else:
        chart, finished, rated, totals = found["overall"], found["finished"], found["rated"], found["totals"]
        singular, plural = "title", "titles"
    if not chart:
        return []
    out = []
    lead = chart[0]
    chart_name = f"{singular} chart" if kind else "trending chart"
    first = (f"{lead['title']} tops the {chart_name} {now_words}, with activity from "
             f"{_plural(lead['members'], 'member')}: {_what_members_did(lead)}.")
    if len(chart) > 1:
        runner = chart[1]
        first += f" {runner['title']} is close behind with {_plural(runner['members'], 'member')}."
    out.append(first)

    climbers = sorted((e for e in chart if e["movement"] == "up" and e["change"] >= 2), key=lambda e: (-e["change"], e["rank"]))
    newcomers = [e for e in chart[:10] if e["movement"] == "new"]
    moves = []
    if climbers:
        top = climbers[0]
        moves.append(f"The biggest climb belongs to {top['title']}, up {_plural(top['change'], 'place')} from {before_words} "
                     f"to number {top['rank']}.")
    if newcomers:
        names = [e["title"] for e in newcomers[:3]]
        verb = "is new to the chart" if len(names) == 1 else "are new to the chart"
        moves.append(f"{_join(names)} {verb} {now_words}.")
    if moves:
        out.append(" ".join(moves))

    if finished:
        top = finished[0]
        sentence = (f"More members finished {top['title']} than any other {singular if kind else 'title'}: "
                    f"{_plural(top['finished'], 'member')} {FINISH_VERBS[top['kind']]} it {now_words}")
        if top["average"] is not None:
            sentence += f", and they rated it {top['average']} out of 10 on average"
        out.append(sentence + ".")
    if rated:
        best = rated[0]
        if not finished or best["url"] != finished[0]["url"]:
            out.append(f"Among {plural} with at least {RATING_MIN} new ratings, {best['title']} scored highest at "
                       f"{best['average']} out of 10 from {_plural(best['rated'], 'member')}.")
    if not kind:
        spread = Counter(e["kind"] for e in chart[:10])
        busiest, count = spread.most_common(1)[0] if spread else (None, 0)
        if len(spread) >= 2 and count >= 3:
            out.append(f"{FORMAT_NAMES[busiest]} hold {count} of the top {min(10, len(chart))} spots, more than any other format.")
    if totals["members"]:
        where = f"Across {plural}" if kind else "Across every format"
        out.append(f"{where}, {_plural(totals['members'], 'member')} added {_plural(totals['added'], singular, plural)} and "
                   f"logged {_plural(totals['finished'], 'finish', 'finishes')} {now_words}.")
    return out


def word_count(found: dict, kind: Optional[str]) -> int:
    return sum(len(text.split()) for text in paragraphs(found, kind))
