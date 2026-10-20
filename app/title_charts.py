"""Member charts: the highest-rated and most-tracked titles of each kind (/titles/<kind>).

Charts rank titles by OmniTrackr members' own ratings, grouped exactly like title
pages (slug and year). Only members who keep that category shareable count, the
editors account never counts, and each member's rating counts once per title.

The ranking uses a weighted average: a title's member average is pulled toward
the average of every rated title of that kind until enough members have rated
it, so a handful of 10/10 ratings doesn't automatically outrank dozens of high ones.
"""
from __future__ import annotations

import threading
import time
from collections import Counter
from typing import Optional

from sqlalchemy.orm import Session

from . import title_pages

CHART_MIN_RATINGS = title_pages.MIN_RATINGS_SHOWN  # Same floor as the average on a title page.
CHART_LIMIT = 50
CHART_INDEX_MIN = 10  # Fewer ranked titles than this is a thin page: noindex, not in the sitemap.
TRACKED_LIMIT = 18
QUOTE_CHARS = 220
CACHE_SECONDS = 600
SCAN_LIMIT = 60000

_lock = threading.Lock()
_cache: dict = {}
_build_locks: dict = {}


def _scan(db: Session, kind: str) -> list[dict]:
    """Every shareable library row of one kind, grouped by title page identity."""
    model = title_pages.KINDS[kind][0]
    year_column = model.release_date if kind == "game" else model.year
    done_column = getattr(model, title_pages.COMPLETE_FIELD[kind])
    image_column = getattr(model, title_pages.IMAGE_FIELD[kind])
    creator_field = title_pages.KINDS[kind][4]
    creator_column = getattr(model, creator_field) if creator_field else None
    columns = [model.id, model.user_id, model.title, year_column, model.rating, done_column, image_column]
    if creator_column is not None:
        columns.append(creator_column)
    rows = (db.query(model).with_entities(*columns)
            .filter(model.user_id.in_(title_pages._shareable_ids(db, kind)),
                    ~model.user_id.in_(title_pages._editor_ids(db)))
            .order_by(model.id).limit(SCAN_LIMIT).all())
    groups: dict = {}
    for row in rows:
        row_id, user_id, title, year_value, rating, done, image = row[:7]
        creator = row[7] if creator_column is not None else None
        title = (title or "").strip()
        if not title:
            continue
        year = (year_value.year if year_value else None) if kind == "game" else (year_value or None)
        key = (title_pages.slugify(title), year)
        group = groups.setdefault(key, {"names": Counter(), "members": set(), "finished": set(), "ratings": {},
                                        "image": None, "creators": Counter(), "ids": []})
        group["names"][title] += 1
        group["members"].add(user_id)
        group["ids"].append(row_id)
        if done:
            group["finished"].add(user_id)
        if rating is not None:
            group["ratings"][user_id] = float(rating)  # Rows come in id order: a member's latest entry wins.
        if group["image"] is None:
            group["image"] = title_pages._safe_image(image)
        if creator and creator.strip():
            group["creators"][creator.strip()] += 1
    entries = []
    for (_, year), group in groups.items():
        display = group["names"].most_common(1)[0][0]
        ratings = list(group["ratings"].values())
        entries.append({
            "kind": kind, "title": display, "year": year, "url": title_pages.title_path(kind, display, year),
            "members": len(group["members"]), "finished": len(group["finished"]), "rated": len(ratings),
            "average": round(sum(ratings) / len(ratings), 1) if ratings else None, "_sum": sum(ratings),
            "image": group["image"], "creator": group["creators"].most_common(1)[0][0] if group["creators"] else None,
            "_ids": group["ids"],
        })
    return entries


def _quotes(db: Session, kind: str, ranked: list[dict]) -> None:
    """A short excerpt of the best public review for each ranked title that has one."""
    model = title_pages.KINDS[kind][0]
    wanted = {row_id: entry for entry in ranked for row_id in entry["_ids"]}
    if not wanted:
        return
    candidates: dict = {}
    ids = list(wanted)
    for start in range(0, len(ids), 900):
        for item in db.query(model).filter(model.id.in_(ids[start:start + 900]), model.review_public == True,
                                           model.review.isnot(None)):
            if len((item.review or "").strip()) >= title_pages.REVIEW_MIN_CHARS:
                candidates.setdefault(wanted[item.id]["url"], []).append(item)
    for entry in ranked:
        items = candidates.get(entry["url"])
        if not items:
            continue
        # A chart quote is a teaser, so a review marked as containing spoilers never supplies it.
        reviews = [review for review in title_pages._public_reviews(db, kind, items) if not review.get("spoilers")]
        if reviews:
            review = reviews[0]
            text = " ".join(review["review"].split())
            if len(text) > QUOTE_CHARS:
                text = text[:QUOTE_CHARS].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
            entry["quote"] = {"text": text, "username": review["username"], "url": review["url"],
                              "profile_url": review.get("profile_url"), "rating": review["rating"]}


def build(db: Session, kind: str) -> dict:
    entries = _scan(db, kind)
    rated = [entry for entry in entries if entry["rated"]]
    total = sum(entry["rated"] for entry in rated)
    mean = sum(entry["_sum"] for entry in rated) / total if total else 0.0
    weight = CHART_MIN_RATINGS
    for entry in rated:
        entry["score"] = (entry["_sum"] + weight * mean) / (entry["rated"] + weight)
    ranked = sorted((entry for entry in rated if entry["rated"] >= CHART_MIN_RATINGS),
                    key=lambda entry: (-entry["score"], -entry["rated"], entry["title"].casefold()))[:CHART_LIMIT]
    for position, entry in enumerate(ranked, start=1):
        entry["rank"] = position
    _quotes(db, kind, ranked)
    tracked = sorted((entry for entry in entries if entry["members"] >= 2),
                     key=lambda entry: (-entry["members"], entry["title"].casefold()))[:TRACKED_LIMIT]
    for entry in entries:
        entry.pop("_sum", None)
    clean = lambda items: [{k: v for k, v in entry.items() if k != "_ids"} for entry in items]
    return {
        "kind": kind,
        "ranked": clean(ranked),
        "tracked": clean(tracked),
        "titles": len(entries),
        "ratings": total,
        "mean": round(mean, 1) if total else None,
        "indexable": len(ranked) >= CHART_INDEX_MIN,
    }


def chart(db: Session, kind: str) -> dict:
    """The cached chart for one kind (rebuilt at most every CACHE_SECONDS).

    Every title page asks for its kind's chart, so only one request rebuilds an
    expired chart; the others keep using the previous one meanwhile (or, before the
    first build, wait for it rather than starting their own).
    """
    if kind not in title_pages.KINDS:
        raise KeyError(kind)
    with _lock:
        cached = _cache.get(kind)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        builder = _build_locks.setdefault(kind, threading.Lock())
    if not builder.acquire(blocking=cached is None):
        return cached[1]  # Another request is already rebuilding this chart.
    try:
        with _lock:
            current = _cache.get(kind)
            if current and current is not cached and time.monotonic() - current[0] < CACHE_SECONDS:
                return current[1]  # Built while this request waited.
        data = build(db, kind)
        with _lock:
            _cache[kind] = (time.monotonic(), data)
        return data
    finally:
        builder.release()


def rank_of(db: Session, kind: str, path: str) -> Optional[dict]:
    """{"rank", "of"} when the title at `path` is on its kind's chart; never raises."""
    try:
        data = chart(db, kind)
    except Exception:
        db.rollback()
        return None
    for entry in data["ranked"]:
        if entry["url"] == path:
            return {"rank": entry["rank"], "of": len(data["ranked"])}
    return None


def indexable_paths(db: Session) -> list[str]:
    paths = []
    for kind in title_pages.KINDS:
        try:
            if chart(db, kind)["indexable"]:
                paths.append(f"/titles/{kind}")
        except Exception:
            db.rollback()
    return paths


def clear_cache() -> None:
    with _lock:
        _cache.clear()
