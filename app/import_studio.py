"""Safe, preview-first CSV migration helpers for the Import Studio."""
from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from pydantic import ValidationError
from sqlalchemy.orm import Session

from . import models, schemas


MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 5000
SUPPORTED_SOURCES = {"auto", "letterboxd", "goodreads", "myanimelist", "generic"}
CATEGORY_ALIASES = {
    "movie": "movies", "movies": "movies", "film": "movies", "films": "movies",
    "tv": "tv-shows", "show": "tv-shows", "shows": "tv-shows", "tv show": "tv-shows",
    "tv shows": "tv-shows", "tv-show": "tv-shows", "tv-shows": "tv-shows",
    "anime": "anime",
    "game": "video-games", "games": "video-games", "video game": "video-games",
    "video games": "video-games", "video-game": "video-games", "video-games": "video-games",
    "music": "music", "album": "music", "albums": "music",
    "book": "books", "books": "books",
}
CATEGORY_LABELS = {
    "movies": "Movies", "tv-shows": "TV Shows", "anime": "Anime",
    "video-games": "Video Games", "music": "Music", "books": "Books",
}
MODEL_BY_CATEGORY = {
    "movies": models.Movie, "tv-shows": models.TVShow, "anime": models.Anime,
    "video-games": models.VideoGame, "music": models.Music, "books": models.Book,
}
SCHEMA_BY_CATEGORY = {
    "movies": schemas.MovieCreate, "tv-shows": schemas.TVShowCreate,
    "anime": schemas.AnimeCreate, "video-games": schemas.VideoGameCreate,
    "music": schemas.MusicCreate, "books": schemas.BookCreate,
}


@dataclass
class ParsedRow:
    row: int
    category: str | None
    title: str
    data: dict[str, Any] | None
    error: str | None = None


def fingerprint(content: bytes, source: str = "", category: str = "", mapping_json: str = "") -> str:
    """Bind confirmation to both the file bytes and the selected interpretation."""
    options = f"\0{source}\0{category}\0{mapping_json}".encode("utf-8")
    return hashlib.sha256(content + options).hexdigest()


def _header(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _normalized_row(row: dict[str, Any]) -> dict[str, str]:
    return {_header(key): _clean(value) for key, value in row.items() if key is not None}


def _first(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(_header(name), "")
        if value:
            return value
    return ""


def _integer(value: str, default: int = 0) -> int:
    match = re.search(r"\d{4}", value or "")
    if match:
        return int(match.group(0))
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return default


def _optional_integer(value: str) -> int | None:
    if not value:
        return None
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return None


def _rating(value: str, five_point: bool = False) -> float | None:
    if not value:
        return None
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    if five_point:
        rating *= 2
    return round(min(10.0, max(0.0, rating)), 1)


def _truthy(value: str) -> bool:
    return _clean(value).lower() in {"1", "true", "yes", "y", "watched", "read", "played", "completed", "complete", "finished"}


def _date(value: str) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%Y"):
        try:
            return datetime.strptime(cleaned[:10] if fmt != "%Y" else cleaned[:4], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _completed_status(value: str) -> bool:
    return _clean(value).lower() in {"read", "watched", "completed", "complete", "finished"}


def _detect_source(headers: set[str]) -> str:
    if {"name", "letterboxd_uri"}.issubset(headers) or {"position", "name", "url"}.issubset(headers):
        return "letterboxd"
    if {"title", "author", "exclusive_shelf"}.issubset(headers):
        return "goodreads"
    if "series_title" in headers and ({"my_score", "my_status"} & headers):
        return "myanimelist"
    if "title" in headers or "name" in headers:
        return "generic"
    raise ValueError("Could not find a title column or recognize this export format.")


def _read_csv(content: bytes) -> tuple[list[dict[str, str]], set[str]]:
    if len(content) > MAX_IMPORT_BYTES:
        raise ValueError("CSV files must be 5 MB or smaller.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV files must use UTF-8 text encoding.") from exc
    if "\x00" in text:
        raise ValueError("The selected file is not a plain-text CSV file.")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("The CSV file does not contain a header row.")
    rows = [_normalized_row(row) for row in reader]
    if len(rows) > MAX_IMPORT_ROWS:
        raise ValueError(f"Imports are limited to {MAX_IMPORT_ROWS:,} rows at a time.")
    return rows, {_header(name) for name in reader.fieldnames}


def _base_data(row: dict[str, str]) -> tuple[str, int, float | None, str | None]:
    title = _first(row, "title", "name")
    year = _integer(_first(row, "year", "release year", "release_year", "year published", "original publication year"))
    rating = _rating(_first(row, "rating", "score", "my rating"))
    review = _first(row, "review", "notes", "note", "my review") or None
    return title, year, rating, review


def _generic_row(row: dict[str, str], category_override: str | None) -> tuple[str, dict[str, Any]]:
    raw_category = category_override or _first(row, "category", "type", "media type", "media_type")
    category = CATEGORY_ALIASES.get(_clean(raw_category).lower())
    if not category:
        raise ValueError("Choose a media category or add a category column to the CSV.")
    title, year, rating, review = _base_data(row)
    if not title:
        raise ValueError("Title is required.")
    completed = _truthy(_first(row, "completed", "watched", "read", "played", "finished", "status"))
    common = {"title": title, "rating": rating, "review": review, "review_public": False}
    if category == "movies":
        data = {**common, "director": _first(row, "director", "creator") or "Unknown director", "year": year, "watched": completed}
    elif category in {"tv-shows", "anime"}:
        data = {**common, "year": year, "seasons": _optional_integer(_first(row, "seasons")), "episodes": _optional_integer(_first(row, "episodes")), "watched": completed}
    elif category == "video-games":
        data = {**common, "release_date": _date(_first(row, "release date", "release_date", "date", "year")), "genres": _first(row, "genres", "genre") or None, "played": completed}
    elif category == "music":
        data = {**common, "artist": _first(row, "artist", "creator") or "Unknown artist", "year": year, "genre": _first(row, "genre", "genres") or None, "listened": completed}
    else:
        data = {**common, "author": _first(row, "author", "creator") or "Unknown author", "year": year, "genre": _first(row, "genre", "genres") or None, "read": completed}
    return category, data


def _source_row(source: str, row: dict[str, str], category_override: str | None) -> tuple[str, dict[str, Any]]:
    if source == "generic":
        return _generic_row(row, category_override)
    if source == "letterboxd":
        title = _first(row, "name")
        if not title:
            raise ValueError("Name is required.")
        return "movies", {
            "title": title, "director": "Unknown director", "year": _integer(_first(row, "year")),
            "rating": _rating(_first(row, "rating"), five_point=True),
            "watched": False if _first(row, "position") and not _first(row, "date", "watched date") else True,
            "review": None, "review_public": False,
        }
    if source == "goodreads":
        title = _first(row, "title")
        if not title:
            raise ValueError("Title is required.")
        return "books", {
            "title": title, "author": _first(row, "author", "author l-f") or "Unknown author",
            "year": _integer(_first(row, "year published", "original publication year")),
            "genre": None, "rating": _rating(_first(row, "my rating"), five_point=True),
            "read": _completed_status(_first(row, "exclusive shelf")) or bool(_first(row, "date read")),
            "review": _first(row, "my review") or None, "review_public": False,
        }
    title = _first(row, "series title")
    if not title:
        raise ValueError("Series title is required.")
    start = _first(row, "series start")
    return "anime", {
        "title": title, "year": _integer(start), "seasons": None,
        "episodes": _optional_integer(_first(row, "series episodes")),
        "rating": _rating(_first(row, "my score")),
        "watched": _completed_status(_first(row, "my status")),
        "review": _first(row, "my comments", "comments") or None,
        "review_public": False,
    }


def parse_csv(
    content: bytes,
    requested_source: str = "auto",
    generic_category: str | None = None,
    column_mapping: dict[str, str] | None = None,
) -> tuple[str, list[ParsedRow]]:
    source = _clean(requested_source).lower() or "auto"
    if source not in SUPPORTED_SOURCES:
        raise ValueError("Unsupported import source.")
    category_override = None
    if generic_category:
        category_override = CATEGORY_ALIASES.get(_clean(generic_category).lower())
        if not category_override:
            raise ValueError("Unsupported generic media category.")
    rows, headers = _read_csv(content)
    if column_mapping:
        allowed_targets = {
            "category", "title", "year", "creator", "rating", "status", "review",
            "genre", "seasons", "episodes", "release_date",
        }
        normalized_mapping = {
            _header(target): _header(source_name)
            for target, source_name in column_mapping.items()
            if _header(target) in allowed_targets and _header(source_name)
        }
        for row in rows:
            for target, source_name in normalized_mapping.items():
                if source_name in row:
                    row[target] = row[source_name]
        headers.update(normalized_mapping.keys())
    detected = _detect_source(headers) if source == "auto" else source
    parsed: list[ParsedRow] = []
    for number, row in enumerate(rows, start=2):
        try:
            category, data = _source_row(detected, row, category_override)
            validated = SCHEMA_BY_CATEGORY[category](**data)
            parsed.append(ParsedRow(number, category, validated.title, validated.model_dump()))
        except (ValueError, ValidationError) as exc:
            title = _first(row, "title", "name", "series title") or f"Row {number}"
            message = str(exc).split("\n", 1)[0]
            parsed.append(ParsedRow(number, None, title, None, message))
    return detected, parsed


def _identity(category: str, data: dict[str, Any]) -> tuple[Any, ...]:
    title = re.sub(r"\s+", " ", data["title"].strip().casefold())
    if category == "movies":
        return title, int(data.get("year") or 0)
    if category in {"tv-shows", "anime"}:
        return title, int(data.get("year") or 0)
    if category == "video-games":
        release = data.get("release_date")
        return title, release.year if release else 0
    if category == "music":
        return title, _clean(data.get("artist")).casefold()
    return title, _clean(data.get("author")).casefold()


def _existing_identities(db: Session, user_id: int) -> dict[str, set[tuple[Any, ...]]]:
    existing: dict[str, set[tuple[Any, ...]]] = {category: set() for category in MODEL_BY_CATEGORY}
    for category, model in MODEL_BY_CATEGORY.items():
        for item in db.query(model).filter(model.user_id == user_id).all():
            data = {column.name: getattr(item, column.name) for column in model.__table__.columns}
            existing[category].add(_identity(category, data))
    return existing


def classify_rows(db: Session, user_id: int, rows: Iterable[ParsedRow]) -> list[dict[str, Any]]:
    identities = _existing_identities(db, user_id)
    classified: list[dict[str, Any]] = []
    for row in rows:
        if row.error or not row.category or not row.data:
            classified.append({"row": row.row, "category": None, "title": row.title, "status": "invalid", "reason": row.error})
            continue
        identity = _identity(row.category, row.data)
        if identity in identities[row.category]:
            classified.append({"row": row.row, "category": row.category, "title": row.title, "status": "duplicate", "reason": "Already in this library or repeated in the file."})
            continue
        identities[row.category].add(identity)
        classified.append({"row": row.row, "category": row.category, "title": row.title, "status": "ready", "reason": None, "data": row.data})
    return classified


def summarize(source: str, digest: str, classified: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"ready": 0, "duplicate": 0, "invalid": 0}
    by_category = {category: 0 for category in MODEL_BY_CATEGORY}
    for item in classified:
        counts[item["status"]] += 1
        if item["status"] == "ready" and item["category"]:
            by_category[item["category"]] += 1
    preview = [{key: value for key, value in item.items() if key != "data"} for item in classified[:100]]
    return {
        "fingerprint": digest, "detected_source": source, "total_rows": len(classified),
        "ready_count": counts["ready"], "duplicate_count": counts["duplicate"],
        "invalid_count": counts["invalid"], "by_category": by_category,
        "preview": preview, "preview_truncated": len(classified) > 100,
    }


def apply_classified(db: Session, user_id: int, classified: list[dict[str, Any]]) -> dict[str, Any]:
    created = {category: 0 for category in MODEL_BY_CATEGORY}
    ready = [item for item in classified if item["status"] == "ready"]
    try:
        for item in ready:
            db.add(MODEL_BY_CATEGORY[item["category"]](**item["data"], user_id=user_id))
            created[item["category"]] += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "created_count": len(ready), "duplicate_count": sum(item["status"] == "duplicate" for item in classified),
        "invalid_count": sum(item["status"] == "invalid" for item in classified), "by_category": created,
    }
