"""Where to watch (or play) a title, cached next to its public facts.

Sources, all best-effort with short timeouts like title_metadata:

* TMDB watch providers (data from JustWatch) for movies, TV and anime. Off
  until TMDB_API_KEY is set (a v3 key or a v4 read token). When it is on, every
  place that shows the result credits JustWatch and TMDB, as both require.
* TVmaze (CC BY-SA) for the service or network a show was made for.
* Jikan / MyAnimeList for an anime's official streaming services.
* RAWG for the stores that sell a game (needs RAWG_API_KEY, like its facts).

The TVmaze, MyAnimeList and RAWG ids come from the title's cached facts, so this
adds at most a couple of requests per title per week.

WATCH_REGION (default "US") picks the country for TMDB results and the JustWatch
search link.
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote_plus

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from . import title_metadata
from .title_metadata import HEADERS, TIMEOUT, _https, _norm, _title_matches

VIDEO_KINDS = ("movie", "tv", "anime")
KINDS = VIDEO_KINDS + ("game",)
# Streaming catalogues change often, so this refreshes sooner than the 30-day facts.
FRESH = {"ok": timedelta(days=7), "miss": timedelta(days=3), "error": timedelta(hours=6)}
TMDB_API = "https://api.themoviedb.org/3"
TMDB_LOGO = "https://image.tmdb.org/t/p/w92"
LOGO_PATH = re.compile(r"^/[A-Za-z0-9_-]{1,64}\.(?:jpg|png|svg)$")
STORE_DOMAIN = re.compile(r"^[a-z0-9.-]{3,80}\.[a-z]{2,10}$")
# TMDB offer type -> heading, in the order people care about.
OFFER_GROUPS = (("flatrate", "Stream"), ("free", "Free"), ("ads", "Free with ads"), ("rent", "Rent"), ("buy", "Buy"))
GROUP_LIMIT = 8


def cache_key(category: str, normalized_title: str, year: Optional[int]) -> str:
    return "where:" + title_metadata.cache_key(category, normalized_title, year)


def region() -> str:
    value = os.getenv("WATCH_REGION", "US").strip().upper()
    return value if re.fullmatch(r"[A-Z]{2}", value) else "US"


def tmdb_enabled() -> bool:
    return bool(os.getenv("TMDB_API_KEY", "").strip())


def verb(kind: str) -> str:
    return "play" if kind == "game" else "watch"


def justwatch_search(title: str) -> str:
    return f"https://www.justwatch.com/{region().lower()}/search?q={quote_plus((title or '').strip()[:150])}"


async def _get(client, url: str, params: Optional[dict] = None, headers: Optional[dict] = None):
    response = await client.get(url, params=params, headers={**HEADERS, **(headers or {})}, timeout=TIMEOUT,
                                follow_redirects=True)
    if response.status_code != 200:
        return None
    return response.json()


def _source_url(metadata: dict, pattern: str) -> Optional[re.Match]:
    for entry in (metadata.get("links") or []) + (metadata.get("sources") or []):
        match = re.search(pattern, str(entry.get("url") or ""))
        if match:
            return match
    return None


def _provider(name, url=None, logo=None) -> Optional[dict]:
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:60]
    if not name:
        return None
    entry = {"name": name}
    if _https(url):
        entry["url"] = _https(url)
    if logo:
        entry["logo"] = logo
    return entry


# ---------------------------------------------------------------- TMDB (JustWatch data)

def _tmdb_auth() -> tuple[dict, dict]:
    key = os.getenv("TMDB_API_KEY", "").strip()
    if "." in key:  # A v4 read access token (a JWT).
        return {}, {"Authorization": f"Bearer {key}"}
    return {"api_key": key}, {}


async def _tmdb_find(client, kind: str, title: str, year: Optional[int], metadata: dict) -> Optional[tuple[str, int]]:
    params, headers = _tmdb_auth()
    imdb = _source_url(metadata, r"imdb\.com/title/(tt\d{5,10})/")
    if imdb:
        data = await _get(client, f"{TMDB_API}/find/{imdb.group(1)}", {**params, "external_source": "imdb_id"}, headers) or {}
        for media, field in (("movie", "movie_results"), ("tv", "tv_results")):
            if data.get(field) and isinstance(data[field][0].get("id"), int):
                return media, data[field][0]["id"]
    order = {"movie": ("movie",), "tv": ("tv",), "anime": ("tv", "movie")}[kind]
    for media in order:
        query = {**params, "query": title[:150]}
        if year:
            query["year" if media == "movie" else "first_air_date_year"] = year
        data = await _get(client, f"{TMDB_API}/search/{media}", query, headers) or {}
        matches = []
        for result in (data.get("results") or [])[:8]:
            names = [result.get("title"), result.get("original_title")] if media == "movie" else \
                [result.get("name"), result.get("original_name")]
            if isinstance(result.get("id"), int) and any(_title_matches(title, name or "") for name in names):
                exact = any(_norm(name or "") == _norm(title) for name in names)
                matches.append((not exact, len(matches), result["id"]))
        if matches:
            return media, min(matches)[2]
    return None


async def tmdb_providers(client, kind: str, title: str, year: Optional[int], metadata: dict) -> dict:
    if not tmdb_enabled() or kind not in VIDEO_KINDS:
        return {}
    found = await _tmdb_find(client, kind, title, year, metadata)
    if not found:
        return {}
    media, tmdb_id = found
    params, headers = _tmdb_auth()
    data = await _get(client, f"{TMDB_API}/{media}/{tmdb_id}/watch/providers", params, headers) or {}
    offers = (data.get("results") or {}).get(region()) or {}
    link = _https(offers.get("link"))
    if link and not link.startswith("https://www.themoviedb.org/"):
        link = None
    groups = []
    for field, label in OFFER_GROUPS:
        providers = []
        for entry in sorted(offers.get(field) or [], key=lambda e: e.get("display_priority") or 999):
            logo_path = entry.get("logo_path")
            logo = TMDB_LOGO + logo_path if isinstance(logo_path, str) and LOGO_PATH.match(logo_path) else None
            provider = _provider(entry.get("provider_name"), link, logo)
            if provider and all(p["name"] != provider["name"] for p in providers):
                providers.append(provider)
        if providers:
            groups.append({"label": label, "providers": providers[:GROUP_LIMIT]})
    if not groups:
        return {}
    return {"groups": groups, "link": link, "justwatch": True}


# ---------------------------------------------------------------- free sources

async def tvmaze_home(client, metadata: dict) -> dict:
    match = _source_url(metadata, r"tvmaze\.com/shows/(\d{1,9})(?:/|$)")
    if not match:
        return {}
    show = await _get(client, f"https://api.tvmaze.com/shows/{match.group(1)}") or {}
    channel, network = show.get("webChannel") or {}, show.get("network") or {}
    official = _https(show.get("officialSite"))
    if channel.get("name"):
        site = _https(channel.get("officialSite"))
        # The show's own site is usually its page on the service, which beats the service's home page.
        host = re.sub(r"^https://(www\.)?", "", site or "").split("/")[0]
        url = official if official and host and host in official else site
        provider = _provider(channel["name"], url)
        return {"groups": [{"label": "Made for", "providers": [provider]}]} if provider else {}
    if network.get("name"):
        provider = _provider(network["name"], network.get("officialSite"))
        return {"groups": [{"label": "Originally aired on", "providers": [provider]}]} if provider else {}
    return {}


async def jikan_streams(client, metadata: dict) -> dict:
    match = _source_url(metadata, r"myanimelist\.net/anime/(\d{1,9})(?:/|$)")
    if not match:
        return {}
    data = await _get(client, f"https://api.jikan.moe/v4/anime/{match.group(1)}/streaming") or {}
    providers = []
    for entry in data.get("data") or []:
        provider = _provider(entry.get("name"), entry.get("url"))
        if provider and provider.get("url") and all(p["name"] != provider["name"] for p in providers):
            providers.append(provider)
    return {"groups": [{"label": "Official streams", "providers": providers[:GROUP_LIMIT]}]} if providers else {}


async def rawg_stores(client, metadata: dict) -> dict:
    key = os.getenv("RAWG_API_KEY")
    match = _source_url(metadata, r"rawg\.io/games/([a-z0-9-]{1,120})$")
    if not key or not match:
        return {}
    game = await _get(client, f"https://api.rawg.io/api/games/{match.group(1)}", {"key": key}) or {}
    if not isinstance(game.get("id"), int):
        return {}
    links = await _get(client, f"https://api.rawg.io/api/games/{game['id']}/stores", {"key": key}) or {}
    urls = {entry.get("store_id"): entry.get("url") for entry in links.get("results") or []}
    providers = []
    for entry in game.get("stores") or []:
        store = entry.get("store") or {}
        domain = str(store.get("domain") or "").lower()
        fallback = f"https://{domain}" if STORE_DOMAIN.match(domain) else None
        provider = _provider(store.get("name"), urls.get(store.get("id")) or fallback)
        if provider and all(p["name"] != provider["name"] for p in providers):
            providers.append(provider)
    if not providers:
        return {}
    return {"groups": [{"label": "Buy or play on", "providers": providers[:GROUP_LIMIT]}],
            "credit": {"name": "RAWG", "url": f"https://rawg.io/games/{match.group(1)}"}}


# ---------------------------------------------------------------- assembly

async def _safe(coro):
    try:
        return await coro or {}
    except Exception:
        return {}


async def fetch(client, kind: str, title: str, year: Optional[int], metadata: Optional[dict]) -> dict:
    """Everything we can find for one title. Returns {} when no source knows it."""
    if kind not in KINDS:
        return {}
    metadata = metadata or {}
    free = {"tv": lambda: tvmaze_home(client, metadata), "anime": lambda: jikan_streams(client, metadata),
            "game": lambda: rawg_stores(client, metadata)}.get(kind)
    tmdb, extra = await asyncio.gather(
        _safe(tmdb_providers(client, kind, title, year, metadata)),
        _safe(free()) if free else asyncio.sleep(0, result={}),
    )
    groups = list(tmdb.get("groups") or [])
    listed = {p["name"].casefold() for group in groups for p in group["providers"]}
    for group in extra.get("groups") or []:
        providers = [p for p in group["providers"] if p["name"].casefold() not in listed]
        if providers:
            groups.append({**group, "providers": providers})
    if not groups:
        return {}
    credits = []
    if tmdb:
        credits.append({"name": "JustWatch", "url": "https://www.justwatch.com/"})
        credits.append({"name": "TMDB", "url": tmdb.get("link") or "https://www.themoviedb.org/"})
    if kind == "tv" and extra:
        credits.append({"name": "TVmaze", "url": "https://www.tvmaze.com/"})
    if kind == "anime" and extra:
        credits.append({"name": "MyAnimeList", "url": "https://myanimelist.net/"})
    if extra.get("credit"):
        credits.append(extra["credit"])
    return {
        "v": 1,
        "kind": kind,
        "region": region() if tmdb else None,
        "groups": groups,
        "link": tmdb.get("link"),
        "justwatch": bool(tmdb.get("justwatch")),
        "credits": credits,
        "fetched": datetime.utcnow().strftime("%Y-%m-%d"),
    }


def cached(db: Session, key: str) -> tuple[Optional[dict], bool]:
    return title_metadata.cached(db, key, FRESH)


_locks: dict[str, asyncio.Lock] = {}


async def get_or_fetch(db: Session, client, kind: str, normalized_title: str, display_title: str,
                       year: Optional[int], metadata: Optional[dict], wait: float = 5.0) -> Optional[dict]:
    if kind not in KINDS:
        return None
    key = cache_key(kind, normalized_title, year)
    data, fresh = await run_in_threadpool(cached, db, key)
    if fresh or client is None:
        return data
    lock = _locks.setdefault(key, asyncio.Lock())
    if lock.locked():
        return data
    async with lock:
        await run_in_threadpool(db.rollback)
        try:
            result = await asyncio.wait_for(fetch(client, kind, display_title, year, metadata), timeout=wait)
            await run_in_threadpool(title_metadata.store, db, key, result or None, "ok" if result else "miss")
            return result or data
        except Exception:
            await run_in_threadpool(title_metadata.store, db, key, None, "error")
            return data
        finally:
            _locks.pop(key, None)


def names(where: Optional[dict], limit: int = 3) -> list[str]:
    """The first few services, streaming first, for one-line summaries."""
    found = []
    for group in (where or {}).get("groups") or []:
        for provider in group["providers"]:
            if provider["name"] not in found:
                found.append(provider["name"])
    return found[:limit]


def stream_names(where: Optional[dict], limit: int = 3) -> list[str]:
    for group in (where or {}).get("groups") or []:
        if group["label"] in ("Stream", "Official streams", "Made for", "Free", "Free with ads"):
            return [p["name"] for p in group["providers"][:limit]]
    return []
