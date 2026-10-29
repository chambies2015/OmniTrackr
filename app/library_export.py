"""Library exports in formats other services and spreadsheets read (Oct 2026).

The JSON backup at /export/ is still the one file OmniTrackr can restore in full.
These builders sit beside it:

* spreadsheet: a ZIP of plain CSV files (library, journal, collections, progress and
  one file per custom tab). library.csv uses the Import Studio's generic columns, so
  it can be brought back in as a spreadsheet import.
* letterboxd / letterboxd-watchlist: Letterboxd's import layout for films.
* goodreads: the Goodreads export layout, which Goodreads and The StoryGraph import.

Everything here only reads. Nothing a member has stored is changed.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy.orm import Session

from . import models

FORMATS = ("spreadsheet", "letterboxd", "letterboxd-watchlist", "goodreads")
CATEGORY_MODELS = {
    "movies": models.Movie, "tv-shows": models.TVShow, "anime": models.Anime,
    "video-games": models.VideoGame, "music": models.Music, "books": models.Book,
    "manga": models.Manga, "podcasts": models.Podcast,
}
# The column that says a title is finished, and the column holding its creator.
COMPLETED_FIELD = {
    "movies": "watched", "tv-shows": "watched", "anime": "watched", "video-games": "played",
    "music": "listened", "books": "read", "manga": "read", "podcasts": "listened",
}
CREATOR_FIELD = {"movies": "director", "music": "artist", "books": "author", "manga": "author", "podcasts": "host"}
# Placeholders the importers write when a source has no creator.
UNKNOWN_CREATORS = {"unknown director", "unknown artist", "unknown author"}
LIBRARY_COLUMNS = [
    "category", "title", "creator", "year", "release_date", "genre", "seasons", "episodes",
    "volumes", "chapters", "rating", "completed", "review", "review_public", "added_at",
]
DIARY_ACTIONS = ("completed", "revisited")
# Spreadsheet apps run a cell that starts with one of these as a formula.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _date(value: Any) -> str:
    return value.strftime("%Y-%m-%d") if isinstance(value, datetime) else ""


def _timestamp(value: Any) -> str:
    return value.replace(microsecond=0).isoformat(sep=" ") if isinstance(value, datetime) else ""


def _number(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{round(value, 1):g}"
    return str(value)


def _creator(media: Any, category: str) -> str:
    field = CREATOR_FIELD.get(category)
    value = (getattr(media, field, None) or "").strip() if field else ""
    return "" if value.lower() in UNKNOWN_CREATORS else value


def _safe_cell(value: Any) -> Any:
    """Keep a spreadsheet from running stored text as a formula when the file is opened."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def _csv(columns: list[str], rows: Iterable[dict[str, Any]], *, spreadsheet: bool = False) -> str:
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _safe_cell(value) if spreadsheet else value for key, value in row.items()})
    return handle.getvalue()


def _sort_key(media: Any) -> tuple[str, int]:
    return ((media.title or "").casefold(), media.id)


def load_library(db: Session, user_id: int, categories: Iterable[str] = tuple(CATEGORY_MODELS)) -> dict[str, list[Any]]:
    return {
        category: sorted(db.query(CATEGORY_MODELS[category]).filter(CATEGORY_MODELS[category].user_id == user_id).all(), key=_sort_key)
        for category in categories
    }


def _title_key(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().casefold())


def _diary_visits(db: Session, user_id: int, category: str) -> dict[Any, list[models.ActivityEntry]]:
    """Finishes and revisits per title, oldest first, keyed by library id and by title."""
    entries = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == user_id,
        models.ActivityEntry.category == category,
        models.ActivityEntry.action.in_(DIARY_ACTIONS),
    ).order_by(models.ActivityEntry.occurred_at.asc(), models.ActivityEntry.id.asc()).all()
    visits: dict[Any, list[models.ActivityEntry]] = {}
    for entry in entries:
        key = entry.item_id if entry.item_id is not None else _title_key(entry.title)
        visits.setdefault(key, []).append(entry)
    return visits


def _visits_for(visits: dict[Any, list[models.ActivityEntry]], media: Any) -> list[models.ActivityEntry]:
    by_id = visits.get(media.id, [])
    by_title = visits.get(_title_key(media.title), [])
    return sorted(by_id + by_title, key=lambda entry: (entry.occurred_at, entry.id))


# ---------------------------------------------------------------- spreadsheet ZIP

def library_rows(library: dict[str, list[Any]]) -> list[dict[str, Any]]:
    rows = []
    for category, items in library.items():
        for media in items:
            release = getattr(media, "release_date", None)
            rows.append({
                "category": category,
                "title": media.title or "",
                "creator": _creator(media, category),
                "year": _number(getattr(media, "year", None)) or (str(release.year) if release else ""),
                "release_date": _date(release),
                "genre": getattr(media, "genre", None) or getattr(media, "genres", None) or "",
                "seasons": _number(getattr(media, "seasons", None)),
                "episodes": _number(getattr(media, "episodes", None)),
                "volumes": _number(getattr(media, "volumes", None)),
                "chapters": _number(getattr(media, "chapters", None)),
                "rating": _number(media.rating),
                "completed": "yes" if getattr(media, COMPLETED_FIELD[category], False) else "no",
                "review": media.review or "",
                "review_public": "yes" if media.review_public else "no",
                "added_at": _timestamp(media.added_at),
            })
    return rows


def _custom_tab_files(custom_tabs: list[dict]) -> dict[str, str]:
    files: dict[str, str] = {}
    for tab in custom_tabs:
        fields = sorted(tab.get("fields") or [], key=lambda field: field.get("order") or 0)
        keys = [field["key"] for field in fields if field.get("key")]
        # Labels become the header row, which _csv() writes as typed.
        labels = {field["key"]: _safe_cell(field.get("label") or field["key"]) for field in fields if field.get("key")}
        columns = ["title", *(labels[key] for key in keys), "poster_url"]
        # Two fields can share a label; the CSV header must stay unique.
        seen: dict[str, int] = {}
        for index, column in enumerate(columns):
            count = seen.get(column, 0)
            seen[column] = count + 1
            if count:
                columns[index] = f"{column} ({count + 1})"
        rows = []
        for item in tab.get("items") or []:
            values = item.get("field_values") or {}
            row = {"title": item.get("title") or "", "poster_url": item.get("poster_url") or ""}
            for key, column in zip(keys, columns[1:-1]):
                value = values.get(key, "")
                row[column] = json.dumps(value) if isinstance(value, (list, dict)) else ("" if value is None else str(value))
            rows.append(row)
        slug = re.sub(r"[^a-z0-9]+", "-", (tab.get("name") or "tab").lower()).strip("-")[:40] or "tab"
        name = f"custom-tabs/{slug}.csv"
        number = 2
        while name in files:
            name = f"custom-tabs/{slug}-{number}.csv"
            number += 1
        files[name] = _csv(columns, rows, spreadsheet=True)
    return files


README = """Your OmniTrackr library, exported {when} UTC

library.csv       Every title in your library, one row each, all categories together.
                  Ratings are out of 10. "completed" means watched, read, played or listened.
journal.csv       Your journal: every start, finish, revisit and note, newest first.
collections.csv   The titles in each of your collections, in the order you set.
progress.csv      Where you stopped in shows, anime, books, manga and podcasts.
tags.csv          Your private tags, one row per tag on a title.
custom-tabs/      One file for each custom tab, with its own columns.

library.csv uses the same columns as the Import Studio's spreadsheet option, so you can
bring it back into OmniTrackr (or into another account) from Account Settings.
A cell that begins with = + - or @ starts with an apostrophe here, so spreadsheet
apps show it as text instead of running it.

For a complete restore, including private settings, use the JSON backup instead.
These files hold your private notes and reviews. Keep them somewhere private.
"""


def tag_rows(db: Session, user_id: int, library: dict[str, list[Any]]) -> list[dict[str, str]]:
    titles = {(category, media.id): media.title or "" for category, items in library.items() for media in items}
    rows = []
    for category, item_id, label in db.query(
            models.LibraryTag.category, models.LibraryTag.item_id, models.LibraryTag.label,
    ).filter(models.LibraryTag.user_id == user_id).order_by(models.LibraryTag.category, models.LibraryTag.label_key):
        if (category, item_id) in titles:
            rows.append({"category": category, "title": titles[(category, item_id)], "tag": label})
    return rows


def spreadsheet_zip(library: dict[str, list[Any]], journal: list[models.ActivityEntry], collections: list[dict],
                    progress: list[dict], custom_tabs: list[dict], now: datetime,
                    tags: Iterable[dict[str, str]] = ()) -> bytes:
    files = {
        "README.txt": README.format(when=now.strftime("%Y-%m-%d %H:%M")),
        "library.csv": _csv(LIBRARY_COLUMNS, library_rows(library), spreadsheet=True),
        "journal.csv": _csv(
            ["date", "category", "title", "action", "rating", "note", "source"],
            ({"date": _timestamp(entry.occurred_at), "category": entry.category, "title": entry.title,
              "action": entry.action, "rating": _number(entry.rating), "note": entry.note or "",
              "source": entry.source or ""} for entry in journal),
            spreadsheet=True,
        ),
        "collections.csv": _csv(
            ["collection", "description", "position", "category", "title", "note"],
            ({"collection": collection["name"], "description": collection.get("description") or "",
              "position": index + 1, "category": item["category"], "title": item["title"],
              "note": item.get("curator_note") or ""}
             for collection in collections for index, item in enumerate(collection["items"])),
            spreadsheet=True,
        ),
        "progress.csv": _csv(
            ["category", "title", "unit", "season", "position", "note", "updated_at"],
            ({"category": entry["category"], "title": entry["title"], **entry["checkpoint"],
              "updated_at": entry["updated_at"]} for entry in progress),
            spreadsheet=True,
        ),
        "tags.csv": _csv(["category", "title", "tag"], tags, spreadsheet=True),
        **_custom_tab_files(custom_tabs),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, text in files.items():
            # A byte order mark tells Excel the file is UTF-8, so accents survive.
            archive.writestr(name, ("﻿" + text if name.endswith(".csv") else text).encode("utf-8"))
    return buffer.getvalue()


# ---------------------------------------------------------------- Letterboxd

LETTERBOXD_COLUMNS = ["Title", "Year", "Directors", "Rating", "WatchedDate", "Rewatch", "Review"]


def _five_star(rating: float | None, step: float) -> str:
    """A rating out of 10 on a five-star scale in the given steps, or blank when unrated."""
    if rating is None or rating <= 0:
        return ""
    stars = max(step, round(rating / 2 / step) * step)
    return f"{min(stars, 5):g}"


def letterboxd_csv(db: Session, user_id: int, movies: list[models.Movie], watchlist: bool = False) -> str:
    """Watched films (one row per diary visit), or the films not yet watched."""
    if watchlist:
        rows = [{"Title": movie.title, "Year": _number(movie.year), "Directors": _creator(movie, "movies")}
                for movie in movies if not movie.watched]
        return _csv(["Title", "Year", "Directors"], rows)
    visits = _diary_visits(db, user_id, "movies")
    rows = []
    for movie in movies:
        dated = _visits_for(visits, movie)
        if not movie.watched and not dated:
            continue
        base = {"Title": movie.title, "Year": _number(movie.year), "Directors": _creator(movie, "movies")}
        if not dated:
            rows.append({**base, "Rating": _five_star(movie.rating, 0.5), "Review": movie.review or ""})
            continue
        for index, entry in enumerate(dated):
            latest = index == len(dated) - 1
            rows.append({
                **base,
                "WatchedDate": _date(entry.occurred_at),
                "Rewatch": "Yes" if index else "",
                # Rating and review once, on the latest watch, so Letterboxd doesn't post repeats.
                "Rating": _five_star(movie.rating, 0.5) if latest else "",
                "Review": (movie.review or "") if latest else "",
            })
    return _csv(LETTERBOXD_COLUMNS, rows)


# ---------------------------------------------------------------- Goodreads / StoryGraph

GOODREADS_COLUMNS = [
    "Book Id", "Title", "Author", "Author l-f", "Additional Authors", "ISBN", "ISBN13", "My Rating",
    "Average Rating", "Publisher", "Binding", "Number of Pages", "Year Published",
    "Original Publication Year", "Date Read", "Date Added", "Bookshelves", "Bookshelves with positions",
    "Exclusive Shelf", "My Review", "Spoiler", "Private Notes", "Read Count", "Owned Copies",
]


def _last_first(name: str) -> str:
    parts = name.split()
    return f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) > 1 else name


def goodreads_csv(db: Session, user_id: int, books: list[models.Book]) -> str:
    visits = _diary_visits(db, user_id, "books")
    rows = []
    for book in books:
        author = _creator(book, "books")
        dated = _visits_for(visits, book)
        rating = _five_star(book.rating, 1)
        rows.append({
            "Title": book.title, "Author": author, "Author l-f": _last_first(author),
            "My Rating": rating or "0", "Year Published": _number(book.year),
            "Original Publication Year": _number(book.year),
            "Date Read": dated[-1].occurred_at.strftime("%Y/%m/%d") if dated and book.read else "",
            "Date Added": book.added_at.strftime("%Y/%m/%d") if book.added_at else "",
            "Exclusive Shelf": "read" if book.read else "to-read",
            "My Review": book.review or "",
            "Read Count": str(max(len(dated), 1)) if book.read else "0",
            "Owned Copies": "0",
        })
    return _csv(GOODREADS_COLUMNS, rows)
