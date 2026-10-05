"""Release Radar: upcoming movies, TV premieres, anime seasons and games.

Data comes from sources whose terms allow a small ad-supported site to display
it with attribution:

* Movies  - Wikidata (CC0) via the public SPARQL endpoint.
* TV      - TVmaze schedules (CC BY-SA, attribution link required).
* Anime   - AniList GraphQL (free below $150/month revenue).
* Games   - RAWG (free for hobby projects; active link on every page).

Nothing here touches the database schema. Results are normalized into plain
dictionaries, cached in memory (and optionally on local disk so a restart does
not immediately hit every API again), and refreshed in the background. Pages
never wait on a slow provider for long: a stale copy is served while a refresh
runs, and a cold cache renders a short "warming up" state instead.
"""
from __future__ import annotations

import asyncio
import calendar
import json
import os
import re
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import httpx

CATEGORY_ORDER = ("movies", "tv", "anime", "games")
CATEGORY_LABELS = {
    "movies": "Movies",
    "tv": "TV premieres",
    "anime": "Anime",
    "games": "Video games",
}
CATEGORY_SINGULAR = {"movies": "movie", "tv": "TV show", "anime": "anime", "games": "game"}
SOURCES = {
    "movies": ("Wikidata", "https://www.wikidata.org/"),
    "tv": ("TVmaze", "https://www.tvmaze.com/"),
    "anime": ("AniList", "https://anilist.co/"),
    "games": ("RAWG", "https://rawg.io/"),
}
SEASONS = ("winter", "spring", "summer", "fall")
SEASON_START_MONTH = {"winter": 1, "spring": 4, "summer": 7, "fall": 10}

FRESH_SECONDS = int(os.getenv("RELEASE_RADAR_FRESH_SECONDS", str(6 * 3600)))
STALE_MAX_SECONDS = int(os.getenv("RELEASE_RADAR_STALE_SECONDS", str(10 * 24 * 3600)))
FIRST_LOAD_WAIT_SECONDS = float(os.getenv("RELEASE_RADAR_FIRST_WAIT", "6"))
USER_AGENT = "OmniTrackr/1.0 (https://omnitrackr.xyz; omnitrackr@gmail.com) ReleaseRadar"
# Lists shorter than this are noindex and stay out of the sitemap.
MIN_INDEXABLE_ITEMS = 8
# Release lists are mostly data from Wikidata, TVmaze, AniList and RAWG with the same
# explanatory text on every page. Useful to visitors, but thin for search and ads
# (AdSense "low value content", Oct 2026): only the overview is indexed, and no
# Release Radar page carries ads.
INDEX_CATEGORY_PAGES = False
RADAR_ADS = False
MAX_ITEMS = {"movies": 80, "tv": 120, "anime": 100, "games": 60}
ALLOWED_IMAGE_HOSTS = (
    "static.tvmaze.com",
    "s4.anilist.co",
    "media.rawg.io",
    "commons.wikimedia.org",
    "upload.wikimedia.org",
)


# ---------------------------------------------------------------------------
# Windows (a month for movies/TV/games, a broadcast season for anime)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Window:
    category: str
    slug: str          # "2026-10" or "fall-2026"
    start: date
    end: date          # exclusive
    label: str         # "October 2026" or "Fall 2026"

    @property
    def cache_key(self) -> str:
        return f"{self.category}:{self.slug}"


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def month_window(category: str, year: int, month: int) -> Window:
    start = date(year, month, 1)
    ny, nm = _add_months(year, month, 1)
    return Window(category, f"{year:04d}-{month:02d}", start, date(ny, nm, 1), f"{calendar.month_name[month]} {year}")


def season_for(day: date) -> tuple[str, int]:
    return SEASONS[(day.month - 1) // 3], day.year


def season_window(season: str, year: int) -> Window:
    start_month = SEASON_START_MONTH[season]
    start = date(year, start_month, 1)
    ny, nm = _add_months(year, start_month, 3)
    return Window("anime", f"{season}-{year}", start, date(ny, nm, 1), f"{season.title()} {year}")


def current_window(category: str, today: Optional[date] = None) -> Window:
    today = today or today_utc()
    if category == "anime":
        return season_window(*season_for(today))
    return month_window(category, today.year, today.month)


FEATURE_NEXT_WITHIN_DAYS = 10


def featured_window(category: str, today: Optional[date] = None) -> Window:
    """The period a visitor most likely wants: the next one once it is days away."""
    today = today or today_utc()
    current = current_window(category, today)
    if (current.end - today).days <= FEATURE_NEXT_WITHIN_DAYS:
        windows = allowed_windows(category, today)
        return windows[windows.index(current) + 1]
    return current


def allowed_windows(category: str, today: Optional[date] = None) -> list[Window]:
    """The browsable range: one period back, the current one, and a few ahead."""
    today = today or today_utc()
    if category == "anime":
        season, year = season_for(today)
        index = year * 4 + SEASONS.index(season)
        return [season_window(SEASONS[i % 4], i // 4) for i in range(index - 1, index + 3)]
    return [month_window(category, *_add_months(today.year, today.month, delta)) for delta in range(-1, 4)]


def parse_window(category: str, slug: str, today: Optional[date] = None) -> Optional[Window]:
    for window in allowed_windows(category, today):
        if window.slug == slug:
            return window
    return None


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _clean_text(value: Any, limit: int = 160) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    text = "".join(ch for ch in text if ch.isprintable())
    return text[:limit]


def _safe_image(url: Any) -> Optional[str]:
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    host = url[8:].split("/", 1)[0].lower()
    if host not in ALLOWED_IMAGE_HOSTS or any(ch in url for ch in "\"'<> \\"):
        return None
    return url[:500]


def _safe_link(url: Any, allowed_prefixes: tuple[str, ...]) -> Optional[str]:
    if isinstance(url, str) and url.startswith(allowed_prefixes) and not any(ch in url for ch in "\"'<> \\"):
        return url[:500]
    return None


def _iso_date(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", value)
    if not match:
        return None
    try:
        return date(int(match[1]), int(match[2]), int(match[3])).isoformat()
    except ValueError:
        return None


def _in_window(iso: Optional[str], window: Window) -> bool:
    if not iso:
        return False
    try:
        day = date.fromisoformat(iso)
    except ValueError:
        return False
    return window.start <= day < window.end


def make_item(
    *, category: str, key: str, title: str, release_date: Optional[str], source_url: Optional[str],
    image: Optional[str] = None, alt_title: str = "", genres: Optional[list[str]] = None,
    details: Optional[list[str]] = None, badges: Optional[list[str]] = None, popularity: float = 0.0,
    save: Optional[dict] = None, platforms: Optional[list[str]] = None, date_note: str = "",
) -> dict:
    return {
        "category": category,
        "key": _clean_text(key, 80),
        "title": _clean_text(title, 200),
        "alt_title": _clean_text(alt_title, 200),
        "date": release_date,
        "date_note": _clean_text(date_note, 60),
        "image": _safe_image(image),
        "source_url": source_url,
        "genres": [_clean_text(g, 40) for g in (genres or []) if _clean_text(g, 40)][:6],
        "platforms": [_clean_text(p, 40) for p in (platforms or []) if _clean_text(p, 40)][:8],
        "details": [_clean_text(d, 80) for d in (details or []) if _clean_text(d, 80)][:4],
        "badges": [_clean_text(b, 30) for b in (badges or []) if _clean_text(b, 30)][:3],
        "popularity": float(popularity or 0),
        "save": save or {},
    }


def _dedupe_and_rank(items: list[dict], limit: int) -> list[dict]:
    seen: dict[str, dict] = {}
    for item in items:
        if not item["title"] or not item["key"]:
            continue
        existing = seen.get(item["key"])
        if existing is None or item["popularity"] > existing["popularity"]:
            seen[item["key"]] = item
    ranked = sorted(seen.values(), key=lambda i: -i["popularity"])[:limit]
    return sorted(ranked, key=lambda i: (i["date"] or "9999-99-99", -i["popularity"], i["title"].lower()))


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
US_QID = "Q30"


def _wikidata_candidates_query(window: Window) -> str:
    return f"""SELECT ?film ?filmLabel ?date ?links ?place WHERE {{
  ?film wdt:P31 wd:Q11424; wdt:P577 ?anyDate.
  FILTER(?anyDate >= "{window.start.isoformat()}T00:00:00Z"^^xsd:dateTime && ?anyDate < "{window.end.isoformat()}T00:00:00Z"^^xsd:dateTime)
  ?film wikibase:sitelinks ?links. FILTER(?links >= 4)
  ?film p:P577 ?st. ?st ps:P577 ?date. OPTIONAL {{ ?st pq:P291 ?place. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}} LIMIT 1500"""


def _wikidata_details_query(qids: list[str]) -> str:
    values = " ".join(f"wd:{qid}" for qid in qids)
    return f"""SELECT ?film ?dirLabel ?genreLabel ?imdb WHERE {{
  VALUES ?film {{ {values} }}
  OPTIONAL {{ ?film wdt:P57 ?dir. }}
  OPTIONAL {{ ?film wdt:P136 ?genre. }}
  OPTIONAL {{ ?film wdt:P345 ?imdb. }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""


async def _sparql(client: httpx.AsyncClient, query: str, timeout: float) -> list[dict]:
    response = await client.get(
        WIKIDATA_ENDPOINT,
        params={"format": "json", "query": query},
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json().get("results", {}).get("bindings", [])


def _binding(row: dict, name: str) -> str:
    return str(row.get(name, {}).get("value", ""))


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1] if uri.startswith("http://www.wikidata.org/entity/Q") else ""


def normalize_wikidata(candidates: list[dict], details: list[dict], window: Window) -> list[dict]:
    films: dict[str, dict] = {}
    for row in candidates:
        qid = _qid(_binding(row, "film"))
        label = _binding(row, "filmLabel")
        if not qid or not label or re.fullmatch(r"Q\d+", label):
            continue
        iso = _iso_date(_binding(row, "date"))
        if not _in_window(iso, window):
            continue
        place = _qid(_binding(row, "place"))
        # Only US releases or releases with no place qualifier. Festival and
        # foreign premieres would otherwise make a film look "out" early.
        if place and place != US_QID:
            continue
        film = films.setdefault(qid, {"title": label, "dates": {}, "links": 0})
        try:
            film["links"] = max(film["links"], int(_binding(row, "links") or 0))
        except ValueError:
            pass
        kind = "us" if place == US_QID else "general"
        current = film["dates"].get(kind)
        film["dates"][kind] = min(current, iso) if current else iso

    directors: dict[str, list[str]] = {}
    genres: dict[str, list[str]] = {}
    imdb: dict[str, str] = {}
    for row in details:
        qid = _qid(_binding(row, "film"))
        if not qid:
            continue
        director = _binding(row, "dirLabel")
        if director and not re.fullmatch(r"Q\d+", director) and director not in directors.setdefault(qid, []):
            directors[qid].append(director)
        genre = _binding(row, "genreLabel")
        if genre and not re.fullmatch(r"Q\d+", genre):
            genre = re.sub(r"\s+film$", "", genre).strip()
            if genre and genre not in genres.setdefault(qid, []):
                genres[qid].append(genre)
        imdb_id = _binding(row, "imdb")
        if re.fullmatch(r"tt\d{5,10}", imdb_id):
            imdb[qid] = imdb_id

    items = []
    for qid, film in films.items():
        release = film["dates"].get("us") or film["dates"].get("general")
        date_note = "US release" if film["dates"].get("us") else "Release"
        director_list = directors.get(qid, [])[:2]
        year = int(release[:4]) if release else None
        items.append(make_item(
            category="movies",
            key=f"wd-{qid}",
            title=film["title"],
            release_date=release,
            date_note=date_note,
            source_url=f"https://www.wikidata.org/wiki/{qid}",
            genres=[g.capitalize() for g in genres.get(qid, [])][:4],
            details=[f"Directed by {', '.join(director_list)}"] if director_list else [],
            popularity=film["links"],
            save={"title": film["title"], "director": director_list[0] if director_list else None, "year": year,
                  "imdb": imdb.get(qid)},
        ))
    return _dedupe_and_rank(items, MAX_ITEMS["movies"])


async def fetch_movies(client: httpx.AsyncClient, window: Window) -> list[dict]:
    candidates = await _sparql(client, _wikidata_candidates_query(window), timeout=45.0)
    qids = sorted({_qid(_binding(row, "film")) for row in candidates} - {""})[:200]
    details = await _sparql(client, _wikidata_details_query(qids), timeout=30.0) if qids else []
    return normalize_wikidata(candidates, details, window)


TVMAZE_TYPES = {"Scripted", "Animation", "Documentary", "Reality", "Variety"}
TVMAZE_MIN_WEIGHT = 60


def normalize_tvmaze(episodes: list[dict], window: Window) -> list[dict]:
    items = []
    for episode in episodes:
        if not isinstance(episode, dict) or episode.get("number") != 1:
            continue
        show = episode.get("show") or (episode.get("_embedded") or {}).get("show") or {}
        if not isinstance(show, dict) or show.get("type") not in TVMAZE_TYPES:
            continue
        weight = show.get("weight") or 0
        if not isinstance(weight, (int, float)) or weight < TVMAZE_MIN_WEIGHT:
            continue
        iso = _iso_date(episode.get("airdate"))
        if not _in_window(iso, window):
            continue
        season = episode.get("season") if isinstance(episode.get("season"), int) else None
        channel = (show.get("webChannel") or {}).get("name") or (show.get("network") or {}).get("name")
        is_new = season == 1
        premiered = _iso_date(show.get("premiered"))
        show_id = show.get("id")
        if not isinstance(show_id, int):
            continue
        details = []
        if channel:
            details.append(("Streaming on " if show.get("webChannel") else "Airs on ") + _clean_text(channel, 50))
        if show.get("language") and show.get("language") != "English":
            details.append(f"{_clean_text(show.get('language'), 30)} language")
        items.append(make_item(
            category="tv",
            key=f"tvm-{show_id}-s{season or 0}",
            title=show.get("name"),
            release_date=iso,
            date_note="Series premiere" if is_new else f"Season {season} premiere" if season else "Premiere",
            source_url=_safe_link(show.get("url"), ("https://www.tvmaze.com/",)),
            image=(show.get("image") or {}).get("medium"),
            genres=show.get("genres") or [],
            details=details,
            badges=["New series"] if is_new else [f"Season {season}"] if season else [],
            popularity=weight,
            save={"title": _clean_text(show.get("name"), 200),
                  "year": int(premiered[:4]) if premiered else int(iso[:4]),
                  "poster_url": _safe_image((show.get("image") or {}).get("medium"))},
        ))
    return _dedupe_and_rank(items, MAX_ITEMS["tv"])


async def _tvmaze_day(client: httpx.AsyncClient, path: str, params: dict, gate: asyncio.Semaphore) -> list:
    async with gate:
        for attempt in range(3):
            response = await client.get(f"https://api.tvmaze.com{path}", params=params,
                                        headers={"User-Agent": USER_AGENT}, timeout=15.0)
            if response.status_code == 429 and attempt < 2:
                await asyncio.sleep(2.5 * (attempt + 1))
                continue
            response.raise_for_status()
            await asyncio.sleep(1.0)  # TVmaze allows ~20 calls / 10 seconds.
            data = response.json()
            return data if isinstance(data, list) else []
    return []


async def fetch_tv(client: httpx.AsyncClient, window: Window) -> list[dict]:
    gate = asyncio.Semaphore(2)
    tasks = []
    day = window.start
    while day < window.end:
        tasks.append(_tvmaze_day(client, "/schedule", {"country": "US", "date": day.isoformat()}, gate))
        tasks.append(_tvmaze_day(client, "/schedule/web", {"date": day.isoformat()}, gate))
        day += timedelta(days=1)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    failures = [r for r in results if isinstance(r, Exception)]
    if failures and len(failures) > len(results) // 3:
        raise failures[0]
    episodes = [episode for result in results if isinstance(result, list) for episode in result]
    return normalize_tvmaze(episodes, window)


ANILIST_QUERY = """query ($season: MediaSeason, $year: Int, $page: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    media(season: $season, seasonYear: $year, type: ANIME, isAdult: false, sort: POPULARITY_DESC) {
      id siteUrl format episodes popularity genres source
      title { romaji english }
      startDate { year month day }
      coverImage { large medium }
      studios(isMain: true) { nodes { name } }
    }
  }
}"""
ANILIST_FORMATS = {"TV": "TV series", "TV_SHORT": "TV short", "ONA": "Web series", "MOVIE": "Film"}
SEQUEL_PATTERN = re.compile(
    r"(season\s*\d+|\d+(st|nd|rd|th)\s+season|\bpart\s*\d+|\bcour\s*\d+|\s(ii|iii|iv|2|3|4|5)$|\bfinal season)",
    re.IGNORECASE,
)


def is_sequel_title(*titles: str) -> bool:
    return any(title and SEQUEL_PATTERN.search(title) for title in titles)


def normalize_anilist(media: list[dict], window: Window) -> list[dict]:
    items = []
    for entry in media:
        if not isinstance(entry, dict) or entry.get("format") not in ANILIST_FORMATS:
            continue
        media_id = entry.get("id")
        if not isinstance(media_id, int):
            continue
        titles = entry.get("title") or {}
        english, romaji = _clean_text(titles.get("english"), 200), _clean_text(titles.get("romaji"), 200)
        title = english or romaji
        start = entry.get("startDate") or {}
        release = None
        if isinstance(start.get("year"), int) and isinstance(start.get("month"), int) and isinstance(start.get("day"), int):
            release = _iso_date(f"{start['year']:04d}-{start['month']:02d}-{start['day']:02d}")
        studios = [s.get("name") for s in ((entry.get("studios") or {}).get("nodes") or []) if isinstance(s, dict)]
        details = []
        if studios:
            details.append("Made by " + ", ".join(_clean_text(s, 40) for s in studios[:2]))
        if isinstance(entry.get("episodes"), int) and entry["episodes"] > 1:
            details.append(f"{entry['episodes']} episodes")
        source = entry.get("source")
        if isinstance(source, str) and source not in ("ORIGINAL", "OTHER"):
            details.append("Adapted from " + source.replace("_", " ").lower())
        elif source == "ORIGINAL":
            details.append("Original story")
        sequel = is_sequel_title(english, romaji)
        cover = (entry.get("coverImage") or {})
        items.append(make_item(
            category="anime",
            key=f"al-{media_id}",
            title=title,
            alt_title=romaji if english and romaji and romaji != english else "",
            release_date=release,
            date_note="Premieres" if release else "Date to be announced",
            source_url=_safe_link(entry.get("siteUrl"), ("https://anilist.co/",)),
            image=cover.get("large") or cover.get("medium"),
            genres=entry.get("genres") or [],
            details=details,
            badges=[ANILIST_FORMATS[entry["format"]]] + (["Sequel"] if sequel else ["New"]),
            popularity=entry.get("popularity") or 0,
            save={"title": title, "year": int(release[:4]) if release else window.start.year,
                  "episodes": entry["episodes"] if isinstance(entry.get("episodes"), int) else None,
                  "poster_url": _safe_image(cover.get("large") or cover.get("medium"))},
        ))
    return _dedupe_and_rank(items, MAX_ITEMS["anime"])


async def fetch_anime(client: httpx.AsyncClient, window: Window) -> list[dict]:
    season, year = window.slug.split("-")
    media: list[dict] = []
    for page in (1, 2):
        response = await client.post(
            "https://graphql.anilist.co",
            json={"query": ANILIST_QUERY, "variables": {"season": season.upper(), "year": int(year), "page": page}},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        page_data = (payload.get("data") or {}).get("Page") or {}
        media.extend(page_data.get("media") or [])
        if not (page_data.get("pageInfo") or {}).get("hasNextPage"):
            break
        await asyncio.sleep(1.5)
    return normalize_anilist(media, window)


def normalize_rawg(results: list[dict], window: Window) -> list[dict]:
    items = []
    for game in results:
        if not isinstance(game, dict):
            continue
        slug = game.get("slug")
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9-]{1,120}", slug):
            continue
        release = _iso_date(game.get("released"))
        if not _in_window(release, window):
            continue
        platforms = [((p or {}).get("platform") or {}).get("name") for p in (game.get("platforms") or [])]
        platforms = [p for p in platforms if p]
        genres = [(g or {}).get("name") for g in (game.get("genres") or [])]
        added = game.get("added") or 0
        items.append(make_item(
            category="games",
            key=f"rawg-{slug}",
            title=game.get("name"),
            release_date=release,
            date_note="Release" if not game.get("tba") else "To be announced",
            source_url=f"https://rawg.io/games/{slug}",
            image=game.get("background_image"),
            genres=[g for g in genres if g],
            platforms=platforms,
            details=[],
            popularity=added,
            save={"title": _clean_text(game.get("name"), 200), "release_date": release,
                  "genres": ", ".join(_clean_text(g, 40) for g in genres if g)[:200] or None,
                  "cover_art_url": _safe_image(game.get("background_image")),
                  "rawg_link": f"https://rawg.io/games/{slug}"},
        ))
    return _dedupe_and_rank(items, MAX_ITEMS["games"])


async def fetch_games(client: httpx.AsyncClient, window: Window) -> list[dict]:
    key = os.getenv("RAWG_API_KEY", "")
    if not key:
        raise ProviderUnavailable("RAWG_API_KEY is not configured")
    last_day = window.end - timedelta(days=1)
    results: list[dict] = []
    for page in (1, 2):
        response = await client.get(
            "https://api.rawg.io/api/games",
            params={"key": key, "dates": f"{window.start.isoformat()},{last_day.isoformat()}",
                    "ordering": "-added", "page_size": 40, "page": page},
            headers={"User-Agent": USER_AGENT},
            timeout=15.0,
        )
        if response.status_code == 404:
            break
        response.raise_for_status()
        payload = response.json()
        results.extend(payload.get("results") or [])
        if not payload.get("next"):
            break
    return normalize_rawg(results, window)


class ProviderUnavailable(RuntimeError):
    """A provider is intentionally disabled, e.g. a missing API key."""


Provider = Callable[[httpx.AsyncClient, Window], Awaitable[list[dict]]]
PROVIDERS: dict[str, Provider] = {
    "movies": fetch_movies,
    "tv": fetch_tv,
    "anime": fetch_anime,
    "games": fetch_games,
}


# ---------------------------------------------------------------------------
# Cache with stale-while-revalidate
# ---------------------------------------------------------------------------

def _default_cache_dir() -> Optional[Path]:
    configured = os.getenv("RELEASE_RADAR_CACHE_DIR")
    if configured == "":
        return None
    return Path(configured or os.path.join(tempfile.gettempdir(), "omnitrackr-release-radar"))


class RadarCache:
    def __init__(self, cache_dir: Optional[Path] = None):
        self.entries: dict[str, dict] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.cache_dir = cache_dir

    def _disk_path(self, window: Window) -> Optional[Path]:
        if not self.cache_dir:
            return None
        return self.cache_dir / (re.sub(r"[^a-z0-9-]", "_", window.cache_key) + ".json")

    def _load_disk(self, window: Window) -> Optional[dict]:
        path = self._disk_path(window)
        if not path or not path.exists():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(entry, dict) and isinstance(entry.get("items"), list) and isinstance(entry.get("fetched_at"), (int, float)):
                return entry
        except (OSError, ValueError):
            return None
        return None

    def _save_disk(self, window: Window, entry: dict) -> None:
        path = self._disk_path(window)
        if not path:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(entry), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass

    def peek(self, window: Window) -> Optional[dict]:
        entry = self.entries.get(window.cache_key)
        if entry is None:
            entry = self._load_disk(window)
            if entry is not None:
                self.entries[window.cache_key] = entry
        if entry and time.time() - entry["fetched_at"] > STALE_MAX_SECONDS:
            return None
        return entry

    async def _refresh(self, client: httpx.AsyncClient, window: Window) -> dict:
        provider = PROVIDERS[window.category]
        try:
            items = await provider(client, window)
            for item in items:
                item["window"] = window.slug
            entry = {"items": items, "fetched_at": time.time(), "error": None}
            self.entries[window.cache_key] = entry
            self._save_disk(window, entry)
            return entry
        except Exception as error:  # Keep serving the previous copy on failure.
            previous = self.entries.get(window.cache_key)
            reason = "unavailable" if isinstance(error, ProviderUnavailable) else "error"
            if previous:
                previous = {**previous, "error": reason, "failed_at": time.time()}
                self.entries[window.cache_key] = previous
                return previous
            failed = {"items": [], "fetched_at": 0, "error": reason, "failed_at": time.time()}
            self.entries[window.cache_key] = failed
            return failed

    def _start_refresh(self, client: httpx.AsyncClient, window: Window) -> asyncio.Task:
        task = self.tasks.get(window.cache_key)
        if task is None or task.done():
            task = asyncio.create_task(self._refresh(client, window))
            self.tasks[window.cache_key] = task
        return task

    def warm(self, client: httpx.AsyncClient, window: Window) -> None:
        """Start a background fetch for an uncached period without waiting for it."""
        entry = self.peek(window)
        if entry is None or (not entry.get("fetched_at") and time.time() - entry.get("failed_at", 0) >= 300):
            self._start_refresh(client, window)

    async def get(self, client: httpx.AsyncClient, window: Window, *, wait: Optional[float] = None) -> Optional[dict]:
        if wait is None:
            wait = FIRST_LOAD_WAIT_SECONDS
        entry = self.peek(window)
        now = time.time()
        if entry and entry.get("fetched_at"):
            if now - entry["fetched_at"] > FRESH_SECONDS and now - entry.get("failed_at", 0) > 900:
                self._start_refresh(client, window)
            return entry
        # Retry a failed cold fetch at most every five minutes.
        if entry and now - entry.get("failed_at", 0) < 300:
            return entry
        task = self._start_refresh(client, window)
        if wait <= 0:
            return None
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=wait)
        except asyncio.TimeoutError:
            return None


CACHE = RadarCache(_default_cache_dir())


# ---------------------------------------------------------------------------
# Original analysis ("Radar notes") derived from the normalized data
# ---------------------------------------------------------------------------

def _plural(count: int, singular: str, plural: Optional[str] = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _join(words: list[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def _week_of(iso: str) -> date:
    day = date.fromisoformat(iso)
    return day - timedelta(days=day.weekday())


def radar_notes(category: str, items: list[dict], window: Window) -> list[str]:
    """Plain-language observations computed from this window's data."""
    if not items:
        return []
    notes = []
    dated = [i for i in items if i["date"]]
    genres = Counter(g for i in items for g in i["genres"])
    top_genres = [g for g, count in genres.most_common(3) if count >= 2]

    if dated:
        weeks = Counter(_week_of(i["date"]) for i in dated)
        busiest, count = weeks.most_common(1)[0]
        if count >= 3:
            notes.append(f"The busiest stretch is the week of {busiest.strftime('%B')} {busiest.day}, with {_plural(count, 'release')} on this list.")
        days = Counter(i["date"] for i in dated)
        day, day_count = days.most_common(1)[0]
        if day_count >= 3:
            weekday = date.fromisoformat(day)
            notes.append(f"{weekday.strftime('%A')}, {weekday.strftime('%B')} {weekday.day} is the single biggest day ({day_count} titles).")

    if category == "tv":
        new = sum(1 for i in items if "New series" in i["badges"])
        returning = len(items) - new
        notes.insert(0, f"{_plural(new, 'brand-new series', 'brand-new series')} and {_plural(returning, 'returning show')} have a premiere in {window.label}.")
        channels = Counter(d.split(" on ", 1)[1] for i in items for d in i["details"] if " on " in d)
        top_channels = [f"{name} ({count})" for name, count in channels.most_common(3) if count >= 2]
        if top_channels:
            notes.append(f"Most premieres are coming from {_join(top_channels)}.")
        non_english = sum(1 for i in items if any(d.endswith(" language") for d in i["details"]))
        if non_english >= 3:
            notes.append(f"{_plural(non_english, 'premiere')} on the list {'is' if non_english == 1 else 'are'} not in English, a good month for subtitles.")
    elif category == "anime":
        sequels = sum(1 for i in items if "Sequel" in i["badges"])
        notes.insert(0, f"{len(items)} anime titles are listed for {window.label}; {sequels} continue an existing story and {len(items) - sequels} are new starts.")
        studios = Counter(d[len('Made by '):].split(', ')[0] for i in items for d in i["details"] if d.startswith("Made by "))
        busy = [f"{name} ({count})" for name, count in studios.most_common(3) if count >= 2]
        if busy:
            notes.append(f"The busiest studios this season: {_join(busy)}.")
        originals = sum(1 for i in items if "Original story" in i["details"])
        if originals:
            story = "is an original story" if originals == 1 else "are original stories"
            notes.append(f"{originals} of them {story} rather than an adaptation, so nobody can spoil it from the source material.")
    elif category == "games":
        platform_counts = Counter(p for i in items for p in set(i["platforms"]))
        top = [f"{name} ({count})" for name, count in platform_counts.most_common(4)]
        notes.insert(0, f"{_plural(len(items), 'game')} with a firm {window.label} date are on the radar.")
        if top:
            notes.append(f"Platform spread: {_join(top)}.")
        multi = sum(1 for i in items if len(i["platforms"]) >= 3)
        if multi:
            notes.append(f"{_plural(multi, 'release')} {'lands' if multi == 1 else 'land'} on three or more platforms at once.")
    elif category == "movies":
        notes.insert(0, f"{_plural(len(items), 'film')} with a {window.label} release date are tracked here, ranked by how widely they are documented across Wikipedia editions.")
        directed = sum(1 for i in items if i["details"])
        if directed and directed < len(items):
            notes.append(f"{len(items) - directed} of them do not have a director listed yet, a sign of smaller or later-confirmed releases.")

    if top_genres:
        notes.append(f"Most common genres: {_join(top_genres)}.")
    return notes[:6]


def upcoming_within(items: list[dict], start: date, days: int) -> list[dict]:
    end = start + timedelta(days=days)
    return [i for i in items if i["date"] and start <= date.fromisoformat(i["date"]) < end]
