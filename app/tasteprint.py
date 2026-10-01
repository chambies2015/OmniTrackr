"""Read-only, privacy-aware Tasteprint aggregation."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Any

from sqlalchemy.orm import Session

from . import models


CATEGORIES = (
    {"key": "movies", "label": "Movies", "model": models.Movie, "done": "watched", "year": "year", "creator": "director", "private": "movies_private", "visible": "movies_visible"},
    {"key": "tv-shows", "label": "TV Shows", "model": models.TVShow, "done": "watched", "year": "year", "creator": None, "private": "tv_shows_private", "visible": "tv_shows_visible"},
    {"key": "anime", "label": "Anime", "model": models.Anime, "done": "watched", "year": "year", "creator": None, "private": "anime_private", "visible": "anime_visible"},
    {"key": "video-games", "label": "Video Games", "model": models.VideoGame, "done": "played", "year": "release_date", "creator": None, "private": "video_games_private", "visible": "video_games_visible"},
    {"key": "music", "label": "Music", "model": models.Music, "done": "listened", "year": "year", "creator": "artist", "private": "music_private", "visible": "music_visible"},
    {"key": "books", "label": "Books", "model": models.Book, "done": "read", "year": "year", "creator": "author", "private": "books_private", "visible": "books_visible"},
)
CATEGORY_BY_KEY = {category["key"]: category for category in CATEGORIES}
MIN_ITEMS = 10
MIN_RATINGS = 5


def parse_categories(value: str | None, user: models.User) -> tuple[list[str], list[dict[str, Any]]]:
    """Resolve an explicit selection or privacy-safe defaults."""
    availability = []
    defaults = []
    for category in CATEGORIES:
        is_private = bool(getattr(user, category["private"], False))
        is_visible = bool(getattr(user, category["visible"], True))
        default_included = not is_private and is_visible
        if default_included:
            defaults.append(category["key"])
        availability.append({
            "key": category["key"], "label": category["label"],
            "private": is_private, "hidden": not is_visible,
            "default_included": default_included,
        })
    if value is None:
        return defaults, availability
    requested = [part.strip().lower() for part in value.split(",") if part.strip()]
    invalid = sorted(set(requested) - set(CATEGORY_BY_KEY))
    if invalid:
        raise ValueError(f"Unsupported Tasteprint categories: {', '.join(invalid)}")
    return list(dict.fromkeys(requested)), availability


def _year(item: Any, field: str) -> int | None:
    value = getattr(item, field, None)
    if isinstance(value, datetime):
        return value.year
    if isinstance(value, int) and value > 0:
        return value
    return None


def _insight(key: str, label: str, value: str, detail: str, evidence_count: int) -> dict[str, Any]:
    return {"key": key, "label": label, "value": value, "detail": detail, "evidence_count": evidence_count}


def build_tasteprint(db: Session, user: models.User, category_value: str | None) -> dict[str, Any]:
    selected, availability = parse_categories(category_value, user)
    records = []
    category_counts: Counter[str] = Counter()
    category_completed: Counter[str] = Counter()

    for key in selected:
        category = CATEGORY_BY_KEY[key]
        items = db.query(category["model"]).filter(category["model"].user_id == user.id).all()
        availability_item = next(item for item in availability if item["key"] == key)
        availability_item["total"] = len(items)
        for item in items:
            category_counts[key] += 1
            done = bool(getattr(item, category["done"], False))
            if done:
                category_completed[key] += 1
            creator = getattr(item, category["creator"], None) if category["creator"] else None
            records.append({
                "category": key, "label": category["label"], "rating": getattr(item, "rating", None),
                "done": done, "year": _year(item, category["year"]), "creator": creator,
            })

    for item in availability:
        if "total" not in item:
            model = CATEGORY_BY_KEY[item["key"]]["model"]
            item["total"] = db.query(model).filter(model.user_id == user.id).count()

    total = len(records)
    ratings = [float(record["rating"]) for record in records if record["rating"] is not None]
    completed = sum(record["done"] for record in records)
    insights: list[dict[str, Any]] = []

    active_categories = [key for key, count in category_counts.items() if count]
    if total >= 3:
        if len(active_categories) >= 4:
            breadth_value = "Cross-media explorer"
            breadth_detail = f"Your selected history stretches across {len(active_categories)} media categories."
        elif len(active_categories) >= 2:
            breadth_value = "A focused mix"
            breadth_detail = f"You move between {len(active_categories)} media categories without spreading the library too thin."
        else:
            breadth_value = "Deep diver"
            breadth_detail = "Your selected history goes deep in one media category."
        insights.append(_insight("breadth", "Media range", breadth_value, breadth_detail, total))

        anchor_key, anchor_count = category_counts.most_common(1)[0]
        anchor = CATEGORY_BY_KEY[anchor_key]
        share = round(anchor_count / total * 100)
        insights.append(_insight(
            "anchor", "Library anchor", anchor["label"],
            f"{anchor_count} selected records make up {share}% of this Tasteprint.", anchor_count,
        ))

    if total >= 5:
        completion = round(completed / total * 100)
        if completion >= 80:
            value = "Finisher energy"
            detail = f"You have completed {completion}% of the selected library."
        elif completion >= 45:
            value = "Active rotation"
            detail = f"You balance finished work with an open queue: {completion}% complete."
        else:
            value = "Possibility collector"
            detail = f"Your selected library leans toward what could be next, with {completion}% complete."
        insights.append(_insight("completion", "Completion style", value, detail, total))

    if len(ratings) >= MIN_RATINGS:
        average = mean(ratings)
        spread = pstdev(ratings) if len(ratings) > 1 else 0
        if spread >= 2.0:
            value = "Full-spectrum rater"
            detail = f"Your scores use the scale broadly, averaging {average:.1f}/10."
        elif average >= 8.2:
            value = "Enthusiastic curator"
            detail = f"Your rated picks average {average:.1f}/10—you tend to keep what works for you."
        elif average < 6.8:
            value = "Discerning rater"
            detail = f"Your {len(ratings)} ratings average {average:.1f}/10, with praise earned carefully."
        else:
            value = "Measured rater"
            detail = f"Your ratings cluster around a considered {average:.1f}/10 average."
        insights.append(_insight("rating", "Rating personality", value, detail, len(ratings)))

    decade_records: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["year"] and 1880 <= record["year"] <= datetime.utcnow().year + 5:
            decade_records[(record["year"] // 10) * 10].append(record)
    if sum(map(len, decade_records.values())) >= 5:
        decade, decade_items = max(decade_records.items(), key=lambda pair: (len(pair[1]), pair[0]))
        decade_ratings = [float(item["rating"]) for item in decade_items if item["rating"] is not None]
        rating_note = f" Their average rating is {mean(decade_ratings):.1f}/10." if decade_ratings else ""
        insights.append(_insight(
            "era", "Home decade", f"The {decade}s",
            f"This is the most represented era, with {len(decade_items)} selected records.{rating_note}", len(decade_items),
        ))

    creators = Counter()
    display_names: dict[str, str] = {}
    for record in records:
        creator = str(record["creator"] or "").strip()
        normalized = creator.casefold()
        if creator and not normalized.startswith("unknown"):
            creators[normalized] += 1
            display_names.setdefault(normalized, creator)
    if creators:
        creator_key, creator_count = creators.most_common(1)[0]
        if creator_count >= 2:
            insights.append(_insight(
                "creator", "Recurring voice", display_names[creator_key],
                f"This name appears {creator_count} times across the selected movie, music, and book history.", creator_count,
            ))

    now = datetime.utcnow()
    activities = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == user.id,
        models.ActivityEntry.category.in_(selected) if selected else False,
    ).all() if selected else []
    recent = [entry for entry in activities if entry.occurred_at >= now - timedelta(days=90)]
    revisits = [entry for entry in recent if entry.action == "revisited"]
    if len(recent) >= 2:
        if revisits:
            value = "Memory keeper"
            detail = f"You logged {len(recent)} moments in 90 days, including {len(revisits)} revisit{'s' if len(revisits) != 1 else ''}."
        else:
            value = "In motion"
            detail = f"You logged {len(recent)} media moments during the last 90 days."
        insights.append(_insight("momentum", "Recent rhythm", value, detail, len(recent)))

    ready = total >= MIN_ITEMS and len(ratings) >= MIN_RATINGS
    return {
        "display_name": user.username,
        "ready": ready,
        "minimum_items": MIN_ITEMS,
        "minimum_ratings": MIN_RATINGS,
        "needed_items": max(MIN_ITEMS - total, 0),
        "needed_ratings": max(MIN_RATINGS - len(ratings), 0),
        "total_items": total,
        "rated_items": len(ratings),
        "selected_categories": selected,
        "available_categories": availability,
        "insights": insights,
        "generated_at": now.isoformat(),
        "privacy": "Private aggregate. No titles or reviews are included in this response.",
    }
