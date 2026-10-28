"""New this week: a weekly roundup of releases plus what OmniTrackr members finished (Oct 2026).

Each week (Monday to Sunday, UTC) gets a permanent page at /new-this-week/<monday>.
Releases come from Release Radar's cache, so building a roundup never calls an
outside service on its own. Member activity is counted from the journal ("completed"
entries) and library add dates, only for members who keep that category shareable,
never the editors account, and only as totals: a title is named only once at least
two members finished or added it that week.

A roundup is saved to ``weekly_roundups`` and rebuilt while its week is live. A few
days after the week ends it is marked final and never changes again, so the archive
still shows what came out in a week after Release Radar has moved past it.

The write-up on each page is generated from the saved data when the page is shown,
so improving the wording improves every week in the archive.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, title_pages
from . import release_radar as radar

BASE_PATH = "/new-this-week"
ARCHIVE_PATH = BASE_PATH + "/archive"
PAYLOAD_VERSION = 1
REBUILD_SECONDS = 6 * 3600
FINAL_AFTER_DAYS = 2  # Late schedule changes and late journal entries settle first.
# A week with fewer releases than this, or fewer formats, is a thin page: noindex, not in the sitemap.
MIN_INDEX_RELEASES = 12
MIN_INDEX_CATEGORIES = 3
MIN_INDEX_WORDS = 220
# Release lists carry no ads (see release_radar.RADAR_ADS); the roundups follow the same rule.
ROUNDUP_ADS = False
PER_CATEGORY = {"movies": 24, "tv": 30, "anime": 20, "games": 20}
MEMBER_MIN = title_pages.RECENT_MIN_MEMBERS  # Never name a title only one member finished.
RATING_MIN = title_pages.MIN_RATINGS_SHOWN
TOTALS_MIN_MEMBERS = 3
MEMBER_TITLES = 8
RADAR_KIND = {"movies": "movie", "tv": "tv", "anime": "anime", "games": "game"}
KIND_LABELS = {"movie": "movie", "tv": "TV show", "anime": "anime", "game": "game", "album": "album", "book": "book"}
HEADINGS = {"movies": "New movies", "tv": "TV premieres", "anime": "Anime premieres", "games": "New games"}
NOUNS = {"movies": ("new film", "new films"), "tv": ("TV premiere", "TV premieres"),
         "anime": ("anime premiere", "anime premieres"), "games": ("new game", "new games")}
SAVE_FIELDS = ("title", "year", "director", "release_date", "episodes", "poster_url", "cover_art_url", "genres", "rawg_link", "imdb")


# ---------------------------------------------------------------- weeks

def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def current_monday(today: Optional[date] = None) -> date:
    return monday_of(today or radar.today_utc())


def parse_slug(slug: str) -> Optional[date]:
    """A week's Monday from its URL segment ("2026-10-26"); anything else is None."""
    if not isinstance(slug, str) or len(slug) != 10:
        return None
    try:
        day = date.fromisoformat(slug)
    except ValueError:
        return None
    return day if day.weekday() == 0 and day.isoformat() == slug else None


def path(monday: date) -> str:
    return f"{BASE_PATH}/{monday.isoformat()}"


def _day(day: date) -> str:
    return f"{day.strftime('%B')} {day.day}"


def label(monday: date) -> str:
    """"October 26 to November 1, 2026" (both years when the week crosses New Year)."""
    sunday = monday + timedelta(days=6)
    if monday.year != sunday.year:
        return f"{_day(monday)}, {monday.year} to {_day(sunday)}, {sunday.year}"
    if monday.month == sunday.month:
        return f"{_day(monday)} to {sunday.day}, {sunday.year}"
    return f"{_day(monday)} to {_day(sunday)}, {sunday.year}"


def short_label(monday: date) -> str:
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return f"{monday.strftime('%b')} {monday.day}–{sunday.day}"
    return f"{monday.strftime('%b')} {monday.day} – {sunday.strftime('%b')} {sunday.day}"


def status(monday: date, today: Optional[date] = None) -> str:
    """"future", "current" or "past"."""
    this_week = current_monday(today)
    if monday > this_week:
        return "future"
    return "current" if monday == this_week else "past"


def windows_for_week(category: str, monday: date, today: Optional[date] = None) -> Optional[list[radar.Window]]:
    """The Release Radar periods covering this week, or None when one is outside the radar's range."""
    end = monday + timedelta(days=7)
    allowed = radar.allowed_windows(category, today)
    covering = [w for w in allowed if w.start < end and monday < w.end]
    covered_days = sum((min(w.end, end) - max(w.start, monday)).days for w in covering)
    return covering if covered_days >= 7 else None


# ---------------------------------------------------------------- building a payload

def _slim(item: dict) -> dict:
    save = item.get("save") or {}
    return {
        "category": item["category"], "key": item["key"], "title": item["title"],
        "alt_title": item.get("alt_title") or "", "date": item.get("date"), "date_note": item.get("date_note") or "",
        "image": item.get("image"), "source_url": item.get("source_url"),
        "genres": list(item.get("genres") or []), "platforms": list(item.get("platforms") or []),
        "details": list(item.get("details") or []), "badges": list(item.get("badges") or []),
        "popularity": float(item.get("popularity") or 0), "window": item.get("window") or "",
        "save": {key: save[key] for key in SAVE_FIELDS if save.get(key) is not None},
    }


def week_items(category: str, entries: Iterable[Optional[dict]], monday: date) -> list[dict]:
    """This category's releases dated inside the week, most followed first within each day."""
    start, end = monday.isoformat(), (monday + timedelta(days=7)).isoformat()
    found: dict[str, dict] = {}
    for entry in entries:
        for item in (entry or {}).get("items", []):
            if item.get("category") != category or not (item.get("title") or "").strip():
                continue
            if not item.get("date") or not (start <= item["date"] < end):
                continue
            current = found.get(item["key"])
            if current is None or item.get("popularity", 0) > current.get("popularity", 0):
                found[item["key"]] = item
    ranked = sorted(found.values(), key=lambda i: -float(i.get("popularity") or 0))[:PER_CATEGORY[category]]
    ranked.sort(key=lambda i: (i["date"], -float(i.get("popularity") or 0), i["title"].lower()))
    return [_slim(item) for item in ranked]


def _member_ids(db: Session):
    """Active members other than the editors account."""
    return (db.query(models.User.id)
            .filter(models.User.is_active == True, models.User.username != title_pages.EDITOR_USERNAME))  # noqa: E712


def _shareable(db: Session, kind: str) -> set[int]:
    return {row[0] for row in title_pages._shareable_ids(db, kind)}


def _year_of(kind: str, value) -> Optional[int]:
    if kind == "game":
        return value.year if value else None
    return value or None


def member_activity(db: Session, monday: date) -> dict:
    """Anonymous totals for the week: titles members finished and added (see module docstring)."""
    start = datetime.combine(monday, datetime.min.time())
    end = start + timedelta(days=7)
    members = {row[0] for row in _member_ids(db)}
    shareable = {kind: _shareable(db, kind) & members for kind in title_pages.KINDS}
    entry = models.ActivityEntry
    rows = (db.query(entry.category, entry.title, entry.item_id, entry.user_id, entry.rating)
            .filter(entry.action == "completed", entry.occurred_at >= start, entry.occurred_at < end)
            .all())
    finishers: set[int] = set()
    by_kind_items: dict[str, set[int]] = {}
    finished: dict[tuple[str, str], dict] = {}
    for category, title, item_id, user_id, rating in rows:
        kind = title_pages.LIBRARY_TO_KIND.get(category)
        title = (title or "").strip()
        if kind is None or not title or user_id not in shareable[kind]:
            continue
        finishers.add(user_id)
        group = finished.setdefault((kind, title_pages.normalize(title)), {
            "kind": kind, "names": Counter(), "users": set(), "ratings": {}, "item_ids": set()})
        group["names"][title] += 1
        group["users"].add(user_id)
        if rating is not None:
            group["ratings"][user_id] = float(rating)
        if item_id:
            group["item_ids"].add(item_id)
            by_kind_items.setdefault(kind, set()).add(item_id)

    # Years come from the library rows, so the title page link matches.
    years: dict[tuple[str, int], Optional[int]] = {}
    for kind, ids in by_kind_items.items():
        model = title_pages.KINDS[kind][0]
        year_column = model.release_date if kind == "game" else model.year
        for row_id, value in db.query(model.id, year_column).filter(model.id.in_(sorted(ids))).all():
            years[(kind, row_id)] = _year_of(kind, value)

    finished_rows = []
    for group in finished.values():
        if len(group["users"]) < MEMBER_MIN:
            continue
        kind = group["kind"]
        year_votes = Counter(years.get((kind, item_id)) for item_id in group["item_ids"])
        year_votes.pop(None, None)
        year = year_votes.most_common(1)[0][0] if year_votes else None
        ratings = list(group["ratings"].values())
        finished_rows.append({
            "kind": kind, "title": group["names"].most_common(1)[0][0], "year": year,
            "members": len(group["users"]),
            "ratings": len(ratings),
            "average": round(sum(ratings) / len(ratings), 1) if len(ratings) >= RATING_MIN else None,
        })
    finished_rows.sort(key=lambda r: (-r["members"], -(r["average"] or 0), r["title"].lower()))

    added_rows = []
    for kind, (model, _, _, _, _) in title_pages.KINDS.items():
        year_column = model.release_date if kind == "game" else model.year
        groups: dict[tuple[str, Optional[int]], dict] = {}
        for title, value, user_id in (db.query(model.title, year_column, model.user_id)
                                      .filter(model.added_at >= start, model.added_at < end).all()):
            title = (title or "").strip()
            if not title or user_id not in shareable[kind]:
                continue
            year = _year_of(kind, value)
            group = groups.setdefault((title_pages.slugify(title), year), {"names": Counter(), "users": set()})
            group["names"][title] += 1
            group["users"].add(user_id)
        for (_, year), group in groups.items():
            if len(group["users"]) >= MEMBER_MIN:
                added_rows.append({"kind": kind, "title": group["names"].most_common(1)[0][0], "year": year,
                                   "members": len(group["users"])})
    added_rows.sort(key=lambda r: (-r["members"], r["title"].lower()))

    return {
        "finishers": len(finishers) if len(finishers) >= TOTALS_MIN_MEMBERS else 0,
        "finished": finished_rows[:MEMBER_TITLES],
        "added": added_rows[:MEMBER_TITLES],
    }


def build_payload(db: Session, monday: date, items: dict[str, list[dict]], complete: bool) -> dict:
    from .routers.release_radar import library_counts
    counts = {}
    for category in radar.CATEGORY_ORDER:
        found = library_counts(db, category, items.get(category, [])) if items.get(category) else {}
        counts[category] = {key: int(value) for key, value in found.items() if value}
    return {
        "version": PAYLOAD_VERSION,
        "week_start": monday.isoformat(),
        "built_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "complete": bool(complete),
        "releases": {category: items.get(category, []) for category in radar.CATEGORY_ORDER},
        "counts": counts,
        "members": member_activity(db, monday),
    }


# ---------------------------------------------------------------- storage

def load(db: Session, monday: date) -> Optional[models.WeeklyRoundup]:
    return db.query(models.WeeklyRoundup).filter_by(week_start=monday).first()


def payload_of(row: Optional[models.WeeklyRoundup]) -> Optional[dict]:
    if row is None:
        return None
    try:
        payload = json.loads(row.payload)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) and isinstance(payload.get("releases"), dict) else None


def save(db: Session, monday: date, payload: dict, final: bool) -> Optional[models.WeeklyRoundup]:
    """Insert or update a week's row. A final row is never overwritten."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    now = datetime.utcnow()
    for _ in range(2):
        row = load(db, monday)
        try:
            if row is None:
                row = models.WeeklyRoundup(week_start=monday, payload=text, final=final, built_at=now, created_at=now)
                db.add(row)
            elif row.final:
                return row
            else:
                row.payload, row.final, row.built_at = text, final, now
            db.commit()
            return row
        except IntegrityError:
            db.rollback()  # Another process saved the same week first; update that row instead.
        except Exception:
            db.rollback()
            return load(db, monday)
    return load(db, monday)


def weeks(db: Session) -> list[tuple[date, dict, bool]]:
    """Every saved week, newest first: (monday, payload, final)."""
    found = []
    for row in db.query(models.WeeklyRoundup).order_by(models.WeeklyRoundup.week_start.desc()).all():
        payload = payload_of(row)
        if payload is not None:
            found.append((row.week_start, payload, bool(row.final)))
    return found


def needs_build(row: Optional[models.WeeklyRoundup], monday: date, today: date, now: Optional[datetime] = None) -> bool:
    if row is None:
        return True
    if row.final:
        return False
    now = now or datetime.utcnow()
    if today >= monday + timedelta(days=7 + FINAL_AFTER_DAYS):
        return True  # Time to make it final.
    return (now - row.built_at).total_seconds() >= REBUILD_SECONDS


async def ensure(client, session_or_db, monday: date, *, today: Optional[date] = None, wait: Optional[float] = None,
                 run=None) -> Optional[dict]:
    """The week's payload, building or refreshing it from Release Radar's cache when due.

    ``session_or_db`` is a Session; ``run`` runs a blocking callable off the event loop
    (run_in_threadpool in requests). Returns None when the week has never been saved and
    its releases are not cached yet.
    """
    import asyncio

    today = today or radar.today_utc()
    db = session_or_db

    async def call(fn, *args):
        return await run(fn, *args) if run is not None else fn(*args)

    row = await call(load, db, monday)
    if status(monday, today) == "future" or not needs_build(row, monday, today):
        return payload_of(row)
    windows = {category: windows_for_week(category, monday, today) for category in radar.CATEGORY_ORDER}
    if any(found is None for found in windows.values()):
        return payload_of(row)  # Release Radar no longer holds this week; keep what was saved.
    flat = [(category, window) for category, found in windows.items() for window in found]
    if client is None:
        entries = [radar.CACHE.peek(window) for _, window in flat]
    else:
        entries = await asyncio.gather(*(radar.CACHE.get(client, window, wait=wait) for _, window in flat))
    if any(entry is None or not entry.get("fetched_at") for entry in entries):
        return payload_of(row)  # Still warming up, or the source has never answered.
    complete = all(not entry.get("error") for entry in entries)
    by_category: dict[str, list[Optional[dict]]] = {}
    for (category, _), entry in zip(flat, entries):
        by_category.setdefault(category, []).append(entry)
    items = {category: week_items(category, by_category.get(category, []), monday) for category in radar.CATEGORY_ORDER}
    previous = payload_of(row)
    if not complete and previous and total_releases(previous) > sum(len(v) for v in items.values()):
        return previous  # A failed refresh never shrinks a saved week.
    final = complete and today >= monday + timedelta(days=7 + FINAL_AFTER_DAYS)

    def build_and_save():
        payload = build_payload(db, monday, items, complete)
        saved = save(db, monday, payload, final)
        return payload_of(saved) or payload

    return await call(build_and_save)


# ---------------------------------------------------------------- reading a payload

def releases(payload: dict, category: str) -> list[dict]:
    return list((payload.get("releases") or {}).get(category) or [])


def total_releases(payload: dict) -> int:
    return sum(len(releases(payload, c)) for c in radar.CATEGORY_ORDER)


def category_count(payload: dict) -> int:
    return sum(1 for c in radar.CATEGORY_ORDER if releases(payload, c))


def counts_of(payload: dict, category: str) -> dict[str, int]:
    return dict((payload.get("counts") or {}).get(category) or {})


def headline_titles(payload: dict, limit: int = 3) -> list[str]:
    """The most followed release of each format, then the next ones, for titles and snippets."""
    ranked = {c: sorted(releases(payload, c), key=lambda i: -i["popularity"]) for c in radar.CATEGORY_ORDER}
    picked = []
    for depth in range(3):
        for category in radar.CATEGORY_ORDER:
            if depth < len(ranked[category]) and len(picked) < limit:
                picked.append(ranked[category][depth]["title"])
    return picked


# ---------------------------------------------------------------- the write-up

def _plural(count: int, singular: str, plural: Optional[str] = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _join(words: list[str]) -> str:
    words = [w for w in words if w]
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def _weekday(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{day.strftime('%A')}, {_day(day)}"


def _top(items: list[dict], n: int) -> list[dict]:
    return sorted(items, key=lambda i: (-i["popularity"], i["title"].lower()))[:n]


def _detail(item: dict, prefix: str) -> str:
    return next((d[len(prefix):] for d in item.get("details", []) if d.startswith(prefix)), "")


def _network(item: dict) -> str:
    return next((d.split(" on ", 1)[1] for d in item.get("details", []) if " on " in d), "")


def lead_paragraphs(payload: dict, previous: Optional[dict], when: str) -> list[str]:
    """The opening of the page: what the week holds, its busiest day, and how it compares."""
    monday = date.fromisoformat(payload["week_start"])
    total = total_releases(payload)
    if not total:
        return []
    past = when == "past"
    parts = []
    for category in radar.CATEGORY_ORDER:
        n = len(releases(payload, category))
        if not n:
            continue
        text = _plural(n, *NOUNS[category])
        if category == "tv":
            new = sum(1 for i in releases(payload, "tv") if "New series" in i["badges"])
            if new and new < n:
                text += f" ({new} of them new series)"
        parts.append(text)
    verb = "brought" if past else "brings"
    first = (f"The week of {label(monday)} {verb} {_join(parts)}: {_plural(total, 'release')} on Release Radar in all.")
    every = [i for c in radar.CATEGORY_ORDER for i in releases(payload, c)]
    days = Counter(i["date"] for i in every)
    busiest, busiest_count = days.most_common(1)[0]
    leaders = [i["title"] for i in _top([i for i in every if i["date"] == busiest], 2)]
    second = ""
    if busiest_count >= 2:
        second = (f"{_weekday(busiest)} {'was' if past else 'is'} the busiest day, with {busiest_count} releases"
                  + (f" led by {_join(leaders)}" if leaders else "") + ".")
    weekend = sum(count for iso, count in days.items() if date.fromisoformat(iso).weekday() >= 4)
    if weekend and weekend != total:
        second += f" {weekend} of the {total} land{'ed' if past else ''} between Friday and Sunday."
    paragraphs = [first + (" " + second.strip() if second else "")]

    extra = []
    if previous and total_releases(previous):
        before = total_releases(previous)
        prev_monday = date.fromisoformat(previous["week_start"])
        if total > before:
            extra.append(f"That is {total - before} more than the week of {_day(prev_monday)}, which had {before}.")
        elif total < before:
            extra.append(f"That is a quieter week than the one before (the week of {_day(prev_monday)} had {before}).")
        else:
            extra.append(f"That matches the week of {_day(prev_monday)}, which also had {before}.")
    genres = Counter(g for i in every for g in i["genres"])
    common = [g for g, n in genres.most_common(3) if n >= 3]
    if common:
        lead_genre, lead_count = genres.most_common(1)[0]
        extra.append(f"Across every format, {lead_genre.lower()} is the most common genre ({lead_count} titles)"
                     + (f", ahead of {_join([g.lower() for g in common[1:]])}." if len(common) > 1 else "."))
    if extra:
        paragraphs.append(" ".join(extra))
    return paragraphs


def category_paragraphs(category: str, items: list[dict], counts: dict[str, int], when: str) -> list[str]:
    """A short, specific write-up for one format: what leads, what kind of week it is, what members already track."""
    if not items:
        return []
    past = when == "past"
    is_, are, out = ("was", "were", "came out") if past else ("is", "are", "is out")
    top = _top(items, 3)
    lead = top[0]
    sentences = []
    if category == "movies":
        director = _detail(lead, "Directed by ")
        sentences.append(f"The most followed new film {is_} {lead['title']}"
                         + (f", directed by {director}" if director else "")
                         + f". It {'opened' if past else 'opens'} {_weekday(lead['date'])}.")
        others = [f"{i['title']}" + (f" ({_detail(i, 'Directed by ')})" if _detail(i, "Directed by ") else "") for i in top[1:]]
        if others:
            sentences.append(f"Also on the list: {_join(others)}.")
        undirected = sum(1 for i in items if not _detail(i, "Directed by "))
        if undirected and len(items) >= 4:
            sentences.append(f"{undirected} of the {len(items)} {'do' if undirected != 1 else 'does'} not have a director "
                             "listed yet. Those are usually small or limited releases, so check local listings.")
    elif category == "tv":
        new = [i for i in items if "New series" in i["badges"]]
        returning = [i for i in items if "New series" not in i["badges"]]
        if new:
            first_new = _top(new, 1)[0]
            where = _network(first_new)
            sentences.append(f"The most followed new series {is_} {first_new['title']}"
                             + (f" on {where}" if where else "") + f", starting {_weekday(first_new['date'])}.")
        if returning:
            back = _top(returning, 2)
            sentences.append(f"Back for another season: {_join([i['title'] + (' (' + _network(i) + ')' if _network(i) else '') for i in back])}.")
        channels = Counter(_network(i) for i in items if _network(i))
        busy = [f"{name} ({n})" for name, n in channels.most_common(3) if n >= 2]
        if busy:
            sentences.append(f"The busiest {'channels and services' if len(busy) > 1 else 'service'} this week: {_join(busy)}.")
        foreign = sum(1 for i in items if any(d.endswith(" language") for d in i["details"]))
        if foreign >= 2:
            sentences.append(f"{foreign} of the premieres {are} not in English.")
    elif category == "anime":
        sequels = [i for i in items if "Sequel" in i["badges"]]
        fresh = [i for i in items if "Sequel" not in i["badges"]]
        sentences.append(f"{lead['title']} {is_} the most anticipated premiere on AniList this week"
                         + (f", from {_detail(lead, 'Made by ')}" if _detail(lead, "Made by ") else "") + ".")
        if sequels and fresh:
            sentences.append(f"{_plural(len(sequels), 'show continues', 'shows continue')} an existing story and "
                             f"{_plural(len(fresh), 'is a new start', 'are new starts')}"
                             + (f", led by {_top(fresh, 1)[0]['title']}" if _top(fresh, 1)[0] is not lead else "") + ".")
        elif sequels:
            sentences.append("Every premiere this week continues a story that is already running.")
        else:
            sentences.append("Every premiere this week is a new story, with no earlier season to catch up on first.")
        sources = Counter(_detail(i, "Adapted from ") for i in items if _detail(i, "Adapted from "))
        if sources:
            kind, n = sources.most_common(1)[0]
            sentences.append(f"{n} of the {len(items)} {'is' if n == 1 else 'are'} adapted from {kind}"
                             + (", and the rest are original stories or other sources." if n < len(items) else "."))
    elif category == "games":
        platforms = ", ".join(lead["platforms"][:3])
        sentences.append(f"The most followed game on RAWG {is_} {lead['title']}, out {_weekday(lead['date'])}"
                         + (f" on {platforms}" if platforms else "") + ".")
        if len(top) > 1:
            sentences.append(f"Also {'arrived' if past else 'arriving'}: {_join([i['title'] for i in top[1:]])}.")
        spread = Counter(p for i in items for p in set(i["platforms"]))
        if spread:
            leaders = [f"{name} ({n})" for name, n in spread.most_common(3)]
            sentences.append(f"By platform: {_join(leaders)}.")
        multi = sum(1 for i in items if len(i["platforms"]) >= 3)
        if multi >= 2:
            sentences.append(f"{multi} of them {'launched' if past else 'launch'} on three or more platforms at once.")
    genres = Counter(g for i in items for g in i["genres"])
    common = [g.lower() for g, n in genres.most_common(2) if n >= 2]
    if common:
        sentences.append(f"The most common genres are {_join(common)}.")
    paragraphs = [" ".join(sentences)]

    tracked = sorted(((counts.get(i["key"], 0), i) for i in items if counts.get(i["key"])),
                     key=lambda pair: (-pair[0], pair[1]["title"].lower()))[:3]
    if tracked:
        named = [f"{i['title']} ({_plural(n, 'library', 'libraries')})" for n, i in tracked]
        paragraphs.append(f"Already on OmniTrackr shelves: {_join(named)}.")
    return paragraphs


def member_paragraphs(members: dict, when: str) -> list[str]:
    finished = members.get("finished") or []
    added = members.get("added") or []
    past = when == "past"
    paragraphs = []
    if members.get("finishers"):
        paragraphs.append(f"{_plural(members['finishers'], 'member')} logged at least one finish "
                          f"{'that' if past else 'this'} week. The titles below were finished by at least two of them.")
    if finished:
        lead = finished[0]
        text = (f"The most finished title {'was' if past else 'is'} {lead['title']}, a {KIND_LABELS[lead['kind']]} "
                f"{_plural(lead['members'], 'member')} finished")
        if lead.get("average") is not None:
            text += f", rated {lead['average']:g} out of 10 on average across {lead['ratings']} ratings"
        paragraphs.append(text + ".")
    if added:
        paragraphs.append(f"The title added to the most libraries {'was' if past else 'is'} {added[0]['title']} "
                          f"({_plural(added[0]['members'], 'member')}).")
    return paragraphs


def word_count(paragraphs: Iterable[str]) -> int:
    return sum(len(p.split()) for p in paragraphs)


def writeup_words(payload: dict, previous: Optional[dict] = None, when: str = "past") -> int:
    words = word_count(lead_paragraphs(payload, previous, when))
    for category in radar.CATEGORY_ORDER:
        words += word_count(category_paragraphs(category, releases(payload, category), counts_of(payload, category), when))
    return words + word_count(member_paragraphs(payload.get("members") or {}, when))


def is_indexable(payload: Optional[dict], monday: date, today: Optional[date] = None, previous: Optional[dict] = None) -> bool:
    if not payload or status(monday, today) == "future":
        return False
    return (total_releases(payload) >= MIN_INDEX_RELEASES
            and category_count(payload) >= MIN_INDEX_CATEGORIES
            and writeup_words(payload, previous, status(monday, today)) >= MIN_INDEX_WORDS)
