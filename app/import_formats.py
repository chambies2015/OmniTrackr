"""Readers for the export files services hand out as ZIP, XML or JSON rather than one CSV.

Each reader turns an export into rows in the Import Studio's generic layout (category,
title, year, creator, rating out of 10, completed, review, ...), so the same validation,
duplicate detection and additive save apply to every source.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import posixpath
import re
import zipfile
from typing import Any
from xml.etree import ElementTree


MAX_EXPANDED_BYTES = 40 * 1024 * 1024
STRUCTURED_EXTENSIONS = (".zip", ".xml", ".gz", ".json")
LETTERBOXD_FILES = ("watched.csv", "diary.csv", "ratings.csv", "reviews.csv", "watchlist.csv")
# Archive folders holding entries the member removed, or lists and likes that are not history.
LETTERBOXD_SKIPPED_FOLDERS = {"deleted", "orphaned", "lists", "likes"}
MAL_FINISHED = {"completed", "2"}
ANILIST_FINISHED = {"COMPLETED", "REPEATING"}
ANILIST_BOOK_FORMATS = {"MANGA", "NOVEL", "ONE_SHOT"}

Row = dict[str, str]


def is_structured(content: bytes, filename: str) -> bool:
    name = (filename or "").lower()
    if name.endswith(STRUCTURED_EXTENSIONS):
        return True
    head = content[:64].lstrip(b"\xef\xbb\xbf \t\r\n")
    return content[:4] == b"PK\x03\x04" or content[:2] == b"\x1f\x8b" or head.startswith((b"<?xml", b"<myanimelist"))


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _score(value: Any, scale: float = 1.0) -> str:
    """Return a rating out of 10 as text, or blank when the member never rated it."""
    number = _number(value)
    if number is None or number <= 0:
        return ""
    return f"{round(number * scale, 1):g}"


def _row(category: str, title: str, *, year: Any = "", creator: str = "", rating: str = "",
         completed: bool = False, review: str = "", episodes: Any = "") -> Row:
    return {
        "category": category, "title": title.strip(), "year": _text(year), "creator": creator,
        "rating": rating, "completed": "yes" if completed else "no", "review": review.strip(),
        "episodes": _text(episodes) if _number(episodes) else "",
    }


def _gunzip(content: bytes) -> bytes:
    with gzip.GzipFile(fileobj=io.BytesIO(content)) as handle:
        data = handle.read(MAX_EXPANDED_BYTES + 1)
    if len(data) > MAX_EXPANDED_BYTES:
        raise ValueError("The compressed file expands beyond what one import can read.")
    return data


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Export files must use UTF-8 text encoding.") from exc


# ---------------------------------------------------------------------------
# Letterboxd: the account export ZIP, or one of its CSV files on its own.

def _letterboxd_key(row: dict[str, str]) -> tuple[str, str]:
    return re.sub(r"\s+", " ", (row.get("Name") or "").strip().casefold()), (row.get("Year") or "").strip()


def _letterboxd_rows(files: dict[str, str]) -> list[Row]:
    films: dict[tuple[str, str], dict[str, Any]] = {}

    def film(row: dict[str, str]) -> dict[str, Any] | None:
        key = _letterboxd_key(row)
        if not key[0]:
            return None
        return films.setdefault(key, {"title": row["Name"].strip(), "year": key[1], "watched": False,
                                      "rating": "", "review": ""})

    def rows(name: str) -> list[dict[str, str]]:
        text = files.get(name)
        if not text:
            return []
        # Oldest first, so later diary entries and reviews win.
        return sorted(csv.DictReader(io.StringIO(text)), key=lambda r: (r.get("Watched Date") or r.get("Date") or ""))

    for name in ("watched.csv", "diary.csv", "reviews.csv", "ratings.csv"):
        for row in rows(name):
            entry = film(row)
            if entry is None:
                continue
            entry["watched"] = True
            if row.get("Rating"):
                # ratings.csv is read last, so the member's current rating wins over diary ones.
                entry["rating"] = _score(row["Rating"], 2)
            if name == "reviews.csv" and (row.get("Review") or "").strip():
                entry["review"] = row["Review"]
    for row in rows("watchlist.csv"):
        # Watchlist titles arrive unwatched unless another file shows them as seen.
        film(row)
    return [
        _row("movies", item["title"], year=item["year"], rating=item["rating"],
             completed=item["watched"], review=item["review"])
        for item in films.values()
    ]


def letterboxd_csv_name(filename: str) -> str | None:
    """Name the Letterboxd export file a lone CSV came from, when its name says so."""
    base = posixpath.basename((filename or "").replace("\\", "/")).lower()
    for name in LETTERBOXD_FILES:
        stem = name[:-4]
        if base == name or re.fullmatch(rf"{stem}(\s*\(\d+\))?\.csv", base):
            return name
    return None


# ---------------------------------------------------------------------------
# Trakt: the JSON files from its data export, alone or zipped.

def _trakt_media(item: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    if isinstance(item.get("movie"), dict):
        return "movies", item["movie"]
    if isinstance(item.get("show"), dict):
        return "tv-shows", item["show"]
    return None


def _trakt_show_finished(item: dict[str, Any], show: dict[str, Any]) -> bool:
    aired = _number(show.get("aired_episodes"))
    if not aired:
        return False
    seen = sum(len(season.get("episodes") or []) for season in item.get("seasons") or [] if isinstance(season, dict))
    return seen >= aired


def _trakt_rows(documents: list[tuple[str, Any]]) -> list[Row]:
    titles: dict[tuple[str, str, str], dict[str, Any]] = {}
    for filename, document in documents:
        if not isinstance(document, list):
            continue
        base = posixpath.basename(filename).lower()
        for item in document:
            if not isinstance(item, dict):
                continue
            found = _trakt_media(item)
            if found is None:
                continue
            category, media = found
            title = _text(media.get("title"))
            if not title:
                continue
            kind = _text(item.get("type")).lower()
            whole_title = kind in {"", "movie", "show"}
            rated = "rated_at" in item and whole_title
            watched = any(key in item for key in ("last_watched_at", "plays", "watched_at"))
            listed = "listed_at" in item and "watchlist" in base
            if not (rated or watched or listed):
                # Collections are owned copies and custom lists are not history.
                continue
            year = _text(media.get("year"))
            entry = titles.setdefault((category, title.casefold(), year), {
                "category": category, "title": title, "year": year, "rating": "", "completed": False,
            })
            if rated:
                entry["rating"] = _score(item.get("rating")) or entry["rating"]
                entry["completed"] = True
            if watched and whole_title:
                entry["completed"] = entry["completed"] or category == "movies" or _trakt_show_finished(item, media)
    return [
        _row(item["category"], item["title"], year=item["year"], rating=item["rating"], completed=item["completed"])
        for item in titles.values()
    ]


def _looks_like_trakt(document: Any) -> bool:
    return isinstance(document, list) and any(
        isinstance(item, dict) and _trakt_media(item) is not None for item in document[:50]
    )


# ---------------------------------------------------------------------------
# AniList: the anime and manga lists the Import Studio fetches from AniList's public API.

def _anilist_title(media: dict[str, Any]) -> str:
    title = media.get("title") or {}
    if not isinstance(title, dict):
        return ""
    return _text(title.get("english") or title.get("romaji") or title.get("userPreferred") or title.get("native"))


def _anilist_rows(document: dict[str, Any]) -> list[Row]:
    rows: list[Row] = []
    seen: set[int] = set()
    for key in ("anime", "manga"):
        collection = document.get(key) or {}
        for media_list in collection.get("lists") or [] if isinstance(collection, dict) else []:
            for entry in (media_list or {}).get("entries") or []:
                media = (entry or {}).get("media") or {}
                media_id = media.get("id")
                title = _anilist_title(media)
                if not title or (media_id is not None and media_id in seen):
                    continue
                if media_id is not None:
                    seen.add(media_id)
                finished = _text(entry.get("status")).upper() in ANILIST_FINISHED
                year = ((media.get("startDate") or {}).get("year")) or media.get("seasonYear") or ""
                review = _text(entry.get("notes"))
                rating = _score(entry.get("score"))
                if key == "manga" or _text(media.get("format")).upper() in ANILIST_BOOK_FORMATS:
                    rows.append(_row("books", title, year=year, rating=rating, completed=finished, review=review))
                else:
                    rows.append(_row("anime", title, year=year, rating=rating, completed=finished,
                                     review=review, episodes=media.get("episodes")))
    return rows


# ---------------------------------------------------------------------------
# MyAnimeList-format XML: MyAnimeList itself, Kitsu, and AniList converters.

def _mal_rows(text: str) -> list[Row]:
    # Anywhere in the file: comments or whitespace can push a declaration far past the start.
    if re.search(r"<!(DOCTYPE|ENTITY)", text, re.IGNORECASE):
        raise ValueError("XML files with document type declarations aren't accepted.")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ValueError("The XML file could not be read.") from exc
    if root.tag != "myanimelist":
        raise ValueError("This XML file isn't a MyAnimeList-format list export.")

    def value(node: ElementTree.Element, name: str) -> str:
        return _text(node.findtext(name))

    rows: list[Row] = []
    for node in root:
        status = value(node, "my_status").lower()
        rating = _score(value(node, "my_score"))
        review = value(node, "my_comments")
        if node.tag == "anime":
            title = value(node, "series_title")
            if title:
                rows.append(_row("anime", title, rating=rating, completed=status in MAL_FINISHED,
                                 review=review, episodes=value(node, "series_episodes")))
        elif node.tag == "manga":
            title = value(node, "manga_title")
            if title:
                rows.append(_row("books", title, rating=rating, completed=status in MAL_FINISHED, review=review))
    return rows


# ---------------------------------------------------------------------------

def _zip_files(content: bytes) -> dict[str, bytes]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ValueError("The ZIP file could not be opened.") from exc
    files: dict[str, bytes] = {}
    total = 0
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if not name.lower().endswith((".csv", ".json")):
                continue
            total += info.file_size
            if total > MAX_EXPANDED_BYTES:
                raise ValueError("The ZIP file expands beyond what one import can read.")
            with archive.open(info) as handle:
                data = handle.read(info.file_size + 1)
            if len(data) > info.file_size:
                raise ValueError("The ZIP file could not be read safely.")
            files[name] = data
    return files


def _letterboxd_from_zip(files: dict[str, bytes]) -> list[Row] | None:
    found: dict[str, str] = {}
    for name, data in files.items():
        parts = [part.lower() for part in name.split("/")]
        if LETTERBOXD_SKIPPED_FOLDERS & set(parts[:-1]) or parts[-1] not in LETTERBOXD_FILES:
            continue
        found[parts[-1]] = _decode(data)
    if not found:
        return None
    return _letterboxd_rows(found)


def read_structured(content: bytes, filename: str) -> tuple[str, list[Row]]:
    """Return (source, generic rows) for a ZIP, XML, gzip or JSON export."""
    name = (filename or "").lower()
    if content[:2] == b"\x1f\x8b":
        content = _gunzip(content)
        name = name.removesuffix(".gz")
    if content[:4] == b"PK\x03\x04":
        files = _zip_files(content)
        rows = _letterboxd_from_zip(files)
        if rows is not None:
            return "letterboxd", rows
        documents = []
        for member, data in files.items():
            if member.lower().endswith(".json"):
                try:
                    documents.append((member, json.loads(_decode(data))))
                except json.JSONDecodeError:
                    continue
        if any(_looks_like_trakt(document) for _, document in documents):
            return "trakt", _trakt_rows(documents)
        raise ValueError("This ZIP doesn't contain a Letterboxd or Trakt export. Extract it and choose the CSV inside instead.")
    text = _decode(content).lstrip()
    if text.startswith("<"):
        return "myanimelist", _mal_rows(text)
    if text.startswith(("{", "[")):
        try:
            document = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("The JSON file could not be read.") from exc
        if isinstance(document, dict) and document.get("source") == "anilist":
            return "anilist", _anilist_rows(document)
        if _looks_like_trakt(document):
            return "trakt", _trakt_rows([(name, document)])
        raise ValueError("This JSON file isn't a Trakt or AniList export. To restore an OmniTrackr backup, use Import Data in your library instead.")
    raise ValueError("This file isn't a format the Import Studio reads. Choose a CSV, TSV, ZIP, XML or JSON export.")
