"""Public facts about a title for its OmniTrackr page, cached in the database.

Sources were picked for licences that allow an ad-supported site:

* Wikipedia (text, CC BY-SA 4.0, attributed and linked) and Wikidata (facts,
  critic scores, YouTube trailer ids; CC0) for every kind of title.
* TVmaze (CC BY-SA) for TV: network, status, season counts and wallpaper images.
* RAWG (free commercial tier with a link back on every page) for games:
  platforms, Metacritic score and screenshots.
* Jikan / MyAnimeList facts for anime (episodes, studios, score, trailer). No
  synopsis text is copied from it.
* Open Library for book covers and subjects; the iTunes Search API for album
  artwork and track lists.

Every network call is best-effort with short timeouts: a page never fails
because a source is slow, it simply shows less.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models

USER_AGENT = "OmniTrackr/1.0 (https://omnitrackr.xyz; omnitrackr@gmail.com)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
TIMEOUT = 6.0
FRESH = {"ok": timedelta(days=30), "miss": timedelta(days=3), "error": timedelta(hours=6)}

# How each kind of title is described on Wikidata (matched against search descriptions).
WIKIDATA_HINTS = {
    "movie": ("film",),
    "tv": ("television series", "tv series", "television program", "web series", "miniseries", "sitcom", "drama series"),
    "anime": ("anime", "animated television series", "animated series"),
    "game": ("video game",),
    "book": ("novel", "book", "novella", "memoir", "short story collection", "non-fiction"),
    "album": ("album",),
}
WIKIDATA_EXCLUDE = {
    "movie": ("film series", "franchise", "soundtrack", "novel", "video game"),
    "tv": ("episode", "season of"),
    "anime": ("episode", "season of", "film"),
    "game": ("series", "franchise", "soundtrack"),
    "book": ("film", "series of", "television"),
    "album": ("single", "song"),
}
# Wikidata properties shown as facts: (property, label, kind)
FACT_PROPERTIES = {
    "movie": (("P57", "Director", "item"), ("P58", "Screenplay", "item"), ("P161", "Starring", "item"),
              ("P2047", "Running time", "minutes"), ("P272", "Studio", "item"), ("P495", "Country", "item")),
    "tv": (("P170", "Created by", "item"), ("P161", "Starring", "item"), ("P2437", "Seasons", "number"),
           ("P1113", "Episodes", "number"), ("P449", "Original network", "item")),
    "anime": (("P57", "Director", "item"), ("P272", "Studio", "item"), ("P1113", "Episodes", "number"),
              ("P2437", "Seasons", "number")),
    "game": (("P178", "Developer", "item"), ("P123", "Publisher", "item"), ("P400", "Platforms", "item"),
             ("P404", "Game mode", "item")),
    "book": (("P50", "Author", "item"), ("P123", "Publisher", "item"), ("P1104", "Pages", "number"),
             ("P179", "Series", "item")),
    "album": (("P175", "Artist", "item"), ("P264", "Record label", "item"), ("P2047", "Length", "minutes")),
}
SCORE_PUBLISHERS = {"Q105584": "Rotten Tomatoes", "Q150248": "Metacritic", "Q37312": "IMDb",
                    "Q4044": "Metacritic", "Q2367465": "OpenCritic"}
TRAILER_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def cache_key(category: str, normalized_title: str, year: Optional[int]) -> str:
    return f"{category}:{normalized_title[:250]}:{year or ''}"


def _https(url) -> Optional[str]:
    if isinstance(url, str) and url.startswith("https://") and len(url) < 1000:
        return url
    if isinstance(url, str) and url.startswith("http://") and len(url) < 1000:
        return "https://" + url[len("http://"):]
    return None


def _strip_html(text: Optional[str]) -> str:
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>|</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").casefold()).split())


def _title_matches(wanted: str, found: str) -> bool:
    a, b = _norm(wanted), _norm(found)
    if not a or not b:
        return False
    return a == b or b.startswith(a + " ") or a.startswith(b + " ")


async def _get_json(client, url: str, params: Optional[dict] = None):
    response = await client.get(url, params=params, headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)
    if response.status_code != 200:
        return None
    return response.json()


# ---------------------------------------------------------------- Wikidata / Wikipedia

async def _wikidata_find(client, category: str, title: str, year: Optional[int]) -> Optional[str]:
    data = await _get_json(client, "https://www.wikidata.org/w/api.php", {
        "action": "wbsearchentities", "search": title, "language": "en", "type": "item",
        "limit": 12, "format": "json",
    })
    candidates = []
    for entry in (data or {}).get("search", []):
        description = (entry.get("description") or "").casefold()
        label = entry.get("label") or ""
        if not any(hint in description for hint in WIKIDATA_HINTS[category]):
            continue
        if any(bad in description for bad in WIKIDATA_EXCLUDE[category]):
            continue
        if not _title_matches(title, label) and _norm(label) != _norm(title):
            continue
        exact = _norm(label) == _norm(title)
        years = {int(found) for found in re.findall(r"\b(1[89]\d\d|20\d\d)\b", description)}
        year_hit = bool(year) and any(abs(found - year) <= 1 for found in years)
        if year and years and not year_hit:
            continue  # Same name, different year: a remake or a namesake.
        candidates.append((year_hit, exact, entry["id"]))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (not c[0], not c[1]))
    if year and not candidates[0][0] and not candidates[0][1]:
        return None
    return candidates[0][2]


def _claims(entity: dict, prop: str) -> list:
    return [claim for claim in entity.get("claims", {}).get(prop, []) if claim.get("rank") != "deprecated"]


def _value(claim: dict):
    snak = claim.get("mainsnak", {})
    if snak.get("snaktype") != "value":
        return None
    return snak.get("datavalue", {}).get("value")


def _time(value) -> Optional[str]:
    if isinstance(value, dict) and isinstance(value.get("time"), str):
        match = re.match(r"^\+?(\d{4})-(\d{2})-(\d{2})", value["time"])
        if match:
            year, month, day = match.groups()
            precision = value.get("precision", 11)
            if precision >= 11 and month != "00" and day != "00":
                return f"{year}-{month}-{day}"
            if precision == 10 and month != "00":
                return f"{year}-{month}"
            return year
    return None


async def _labels(client, ids: list[str]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        data = await _get_json(client, "https://www.wikidata.org/w/api.php", {
            "action": "wbgetentities", "ids": "|".join(chunk), "props": "labels",
            "languages": "en", "format": "json",
        })
        for qid, entity in ((data or {}).get("entities") or {}).items():
            label = ((entity.get("labels") or {}).get("en") or {}).get("value")
            if label:
                labels[qid] = label
    return labels


async def wikidata_facts(client, category: str, qid: str) -> dict:
    data = await _get_json(client, "https://www.wikidata.org/w/api.php", {
        "action": "wbgetentities", "ids": qid, "props": "claims|sitelinks|descriptions",
        "languages": "en", "format": "json",
    })
    entity = ((data or {}).get("entities") or {}).get(qid) or {}
    if not entity:
        return {}
    result: dict = {"qid": qid, "wikipedia_title": ((entity.get("sitelinks") or {}).get("enwiki") or {}).get("title")}
    dates = sorted(filter(None, (_time(_value(c)) for c in _claims(entity, "P577") + _claims(entity, "P580"))))
    if dates:
        result["release_date"] = dates[0]
    ended = sorted(filter(None, (_time(_value(c)) for c in _claims(entity, "P582"))))
    if ended:
        result["end_date"] = ended[-1]
    for claim in _claims(entity, "P1651"):
        video = _value(claim)
        if isinstance(video, str) and TRAILER_ID.match(video):
            result["trailer"] = video
            break
    imdb = next((v for v in map(_value, _claims(entity, "P345")) if isinstance(v, str) and re.fullmatch(r"tt\d{5,10}", v)), None)
    if imdb:
        result["imdb_url"] = f"https://www.imdb.com/title/{imdb}/"
    website = next((v for v in map(_value, _claims(entity, "P856")) if isinstance(v, str)), None)
    if _https(website):
        result["website"] = _https(website)

    wanted_items: set[str] = set()
    raw_facts = []
    for prop, label, kind in FACT_PROPERTIES[category] + (("P136", "Genre", "item"),):
        values = []
        for claim in _claims(entity, prop)[: 6 if prop == "P161" else 8]:
            value = _value(claim)
            if kind == "item" and isinstance(value, dict) and value.get("id"):
                values.append(value["id"])
                wanted_items.add(value["id"])
            elif kind in ("number", "minutes") and isinstance(value, dict) and value.get("amount"):
                try:
                    number = float(value["amount"])
                except ValueError:
                    continue
                values.append(f"{int(number)} min" if kind == "minutes" else str(int(number)))
        if values:
            raw_facts.append((label, kind, values))

    scores = []
    for claim in _claims(entity, "P444"):
        value = _value(claim)
        if not isinstance(value, str) or not re.match(r"^\d{1,3}(\.\d)?(%|/100|/10)$", value.strip()):
            continue
        qualifiers = claim.get("qualifiers") or {}
        by = next((q.get("datavalue", {}).get("value", {}).get("id") for q in qualifiers.get("P447", [])), None)
        method = next((q.get("datavalue", {}).get("value", {}).get("id") for q in qualifiers.get("P459", [])), None)
        when = next((_time(q.get("datavalue", {}).get("value")) for q in qualifiers.get("P585", [])), "") or ""
        if by:
            wanted_items.add(by)
        if method:
            wanted_items.add(method)
        scores.append((by, method, value.strip(), when))

    labels = await _labels(client, sorted(wanted_items)) if wanted_items else {}
    facts, genres = [], []
    for label, kind, values in raw_facts:
        shown = [labels.get(v, "") if kind == "item" else v for v in values]
        shown = [v for v in shown if v and not re.match(r"^Q\d+$", v)]
        if not shown:
            continue
        if label == "Genre":
            genres = shown[:6]
        else:
            facts.append({"label": label, "value": ", ".join(dict.fromkeys(shown))})
    result["facts"] = facts
    result["genres"] = genres

    best: dict[str, tuple] = {}
    for by, method, value, when in scores:
        publisher = SCORE_PUBLISHERS.get(by) or labels.get(by or "", "")
        if not publisher:
            continue
        method_label = labels.get(method or "", "")
        name = publisher
        if "audience" in method_label.casefold():
            name = f"{publisher} audience"
        elif "average" in method_label.casefold():
            continue
        if name not in best or when > best[name][1]:
            best[name] = (value, when)
    result["scores"] = [{"source": name, "value": value} for name, (value, _) in sorted(best.items())]
    return result


async def wikipedia_summary(client, page_title: str) -> dict:
    from urllib.parse import quote
    data = await _get_json(client, f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(page_title.replace(' ', '_'), safe='')}")
    if not data or data.get("type") == "disambiguation" or not data.get("extract"):
        return {}
    return {
        "description": data["extract"].strip(),
        "short_description": data.get("description") or "",
        "image": _https((data.get("originalimage") or data.get("thumbnail") or {}).get("source")),
        "url": _https(((data.get("content_urls") or {}).get("desktop") or {}).get("page"))
               or f"https://en.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'))}",
    }


# ---------------------------------------------------------------- category sources

async def tvmaze_details(client, title: str, year: Optional[int]) -> dict:
    results = await _get_json(client, "https://api.tvmaze.com/search/shows", {"q": title}) or []
    show = None
    for result in results[:8]:
        candidate = result.get("show") or {}
        premiered = candidate.get("premiered") or ""
        if _title_matches(title, candidate.get("name", "")) and (not year or premiered.startswith(str(year)) or not premiered):
            show = candidate
            break
    if show is None and results and not year:
        show = results[0].get("show")
    if not show:
        return {}
    images = await _get_json(client, f"https://api.tvmaze.com/shows/{show['id']}/images") or []
    seasons = await _get_json(client, f"https://api.tvmaze.com/shows/{show['id']}/seasons") or []
    gallery = []
    for image in images:
        if image.get("type") == "background":
            resolutions = image.get("resolutions") or {}
            original = _https((resolutions.get("original") or {}).get("url"))
            medium = _https((resolutions.get("medium") or {}).get("url")) or original
            if original:
                gallery.append({"url": original, "thumb": medium})
        if len(gallery) >= 8:
            break
    network = (show.get("network") or {}).get("name") or (show.get("webChannel") or {}).get("name")
    facts = []
    if network:
        facts.append({"label": "Network", "value": network})
    if show.get("status"):
        facts.append({"label": "Status", "value": show["status"]})
    if seasons:
        facts.append({"label": "Seasons", "value": str(len(seasons))})
    if show.get("averageRuntime"):
        facts.append({"label": "Episode length", "value": f"{show['averageRuntime']} min"})
    rating = (show.get("rating") or {}).get("average")
    return {
        "summary": _strip_html(show.get("summary")),
        "url": _https(show.get("url")),
        "premiered": show.get("premiered"),
        "ended": show.get("ended"),
        "genres": show.get("genres") or [],
        "poster": _https((show.get("image") or {}).get("original")),
        "gallery": gallery,
        "facts": facts,
        "score": {"source": "TVmaze members", "value": f"{rating}/10"} if rating else None,
        "website": _https(show.get("officialSite")),
    }


async def rawg_details(client, title: str, year: Optional[int]) -> dict:
    key = os.getenv("RAWG_API_KEY")
    if not key:
        return {}
    data = await _get_json(client, "https://api.rawg.io/api/games", {"search": title, "page_size": 6, "key": key}) or {}
    game = None
    for result in data.get("results", []):
        released = result.get("released") or ""
        if _title_matches(title, result.get("name", "")) and (not year or released.startswith(str(year)) or not released):
            game = result
            break
    if game is None:
        return {}
    details = await _get_json(client, f"https://api.rawg.io/api/games/{game['id']}", {"key": key}) or {}
    shots = await _get_json(client, f"https://api.rawg.io/api/games/{game['id']}/screenshots", {"key": key}) or {}
    gallery = []
    for shot in shots.get("results", [])[:8]:
        url = _https(shot.get("image"))
        if url:
            gallery.append({"url": url, "thumb": url.replace("/media/games/", "/media/resize/640/-/games/")
                            .replace("/media/screenshots/", "/media/resize/640/-/screenshots/")})
    facts = []
    platforms = [p.get("platform", {}).get("name") for p in details.get("platforms") or []]
    if platforms:
        facts.append({"label": "Platforms", "value": ", ".join(filter(None, platforms))[:300]})
    for field, label in (("developers", "Developer"), ("publishers", "Publisher")):
        names = [entry.get("name") for entry in details.get(field) or []]
        if names:
            facts.append({"label": label, "value": ", ".join(filter(None, names))})
    if details.get("playtime"):
        facts.append({"label": "Average playtime", "value": f"{details['playtime']} hours"})
    if (details.get("esrb_rating") or {}).get("name"):
        facts.append({"label": "ESRB", "value": details["esrb_rating"]["name"]})
    slug = details.get("slug") or game.get("slug")
    return {
        "summary": (details.get("description_raw") or "").strip(),
        "url": f"https://rawg.io/games/{slug}" if slug else "https://rawg.io/",
        "released": details.get("released") or game.get("released"),
        "genres": [g.get("name") for g in details.get("genres") or [] if g.get("name")],
        "poster": _https(details.get("background_image") or game.get("background_image")),
        "gallery": gallery,
        "facts": facts,
        "score": {"source": "Metacritic", "value": f"{details['metacritic']}/100"} if details.get("metacritic") else None,
        "website": _https(details.get("website")),
    }


async def jikan_details(client, title: str, year: Optional[int]) -> dict:
    data = await _get_json(client, "https://api.jikan.moe/v4/anime", {"q": title, "limit": 6}) or {}
    anime = None
    for result in data.get("data", []):
        names = [result.get("title"), result.get("title_english")] + [t.get("title") for t in result.get("titles") or []]
        aired = ((result.get("aired") or {}).get("from") or "")[:4]
        if any(_title_matches(title, name or "") for name in names) and (not year or aired == str(year) or not aired):
            anime = result
            break
    if anime is None:
        return {}
    facts = []
    if anime.get("episodes"):
        facts.append({"label": "Episodes", "value": str(anime["episodes"])})
    studios = [s.get("name") for s in anime.get("studios") or [] if s.get("name")]
    if studios:
        facts.append({"label": "Studio", "value": ", ".join(studios)})
    if anime.get("status"):
        facts.append({"label": "Status", "value": anime["status"]})
    if anime.get("duration"):
        facts.append({"label": "Episode length", "value": anime["duration"]})
    if anime.get("source"):
        facts.append({"label": "Based on", "value": anime["source"]})
    trailer = (anime.get("trailer") or {}).get("youtube_id")
    return {
        "url": _https(anime.get("url")),
        "aired": ((anime.get("aired") or {}).get("from") or "")[:10] or None,
        "genres": [g.get("name") for g in anime.get("genres") or [] if g.get("name")],
        "poster": _https(((anime.get("images") or {}).get("jpg") or {}).get("large_image_url")),
        "facts": facts,
        "trailer": trailer if isinstance(trailer, str) and TRAILER_ID.match(trailer) else None,
        "score": {"source": "MyAnimeList", "value": f"{anime['score']}/10"} if anime.get("score") else None,
    }


async def openlibrary_details(client, title: str, year: Optional[int], creator: Optional[str]) -> dict:
    params = {"title": title, "limit": 6, "fields": "key,title,author_name,first_publish_year,cover_i,number_of_pages_median,subject,ratings_average,ratings_count"}
    if creator:
        params["author"] = creator
    data = await _get_json(client, "https://openlibrary.org/search.json", params) or {}
    book = next((doc for doc in data.get("docs", []) if _title_matches(title, doc.get("title", ""))), None)
    if not book:
        return {}
    facts = []
    if book.get("number_of_pages_median"):
        facts.append({"label": "Pages", "value": str(book["number_of_pages_median"])})
    if book.get("author_name"):
        facts.append({"label": "Author", "value": ", ".join(book["author_name"][:3])})
    rating = book.get("ratings_average")
    return {
        "url": f"https://openlibrary.org{book['key']}" if book.get("key") else None,
        "first_published": book.get("first_publish_year"),
        "genres": [s for s in (book.get("subject") or []) if len(s) < 40][:6],
        "poster": f"https://covers.openlibrary.org/b/id/{int(book['cover_i'])}-L.jpg" if book.get("cover_i") else None,
        "facts": facts,
        "score": ({"source": "Open Library readers", "value": f"{round(rating, 1)}/5"}
                  if rating and (book.get("ratings_count") or 0) >= 5 else None),
    }


async def itunes_details(client, title: str, year: Optional[int], creator: Optional[str]) -> dict:
    term = f"{creator or ''} {title}".strip()
    data = await _get_json(client, "https://itunes.apple.com/search", {"term": term, "entity": "album", "limit": 8}) or {}
    album = None
    for result in data.get("results", []):
        if _title_matches(title, result.get("collectionName", "")) and (not creator or _norm(creator) in _norm(result.get("artistName", "")) or _norm(result.get("artistName", "")) in _norm(creator)):
            album = result
            break
    if not album:
        return {}
    tracks = []
    lookup = await _get_json(client, "https://itunes.apple.com/lookup", {"id": album["collectionId"], "entity": "song"}) or {}
    for entry in lookup.get("results", []):
        if entry.get("wrapperType") == "track" and entry.get("trackName"):
            seconds = int((entry.get("trackTimeMillis") or 0) / 1000)
            tracks.append({"name": entry["trackName"], "duration": f"{seconds // 60}:{seconds % 60:02d}" if seconds else ""})
    art = album.get("artworkUrl100")
    facts = [{"label": "Artist", "value": album.get("artistName", "")}]
    if album.get("trackCount"):
        facts.append({"label": "Tracks", "value": str(album["trackCount"])})
    return {
        "url": _https(album.get("collectionViewUrl")),
        "released": (album.get("releaseDate") or "")[:10] or None,
        "genres": [album["primaryGenreName"]] if album.get("primaryGenreName") else [],
        "poster": _https(art.replace("100x100bb", "600x600bb")) if isinstance(art, str) else None,
        "facts": facts,
        "tracks": tracks[:40],
    }


# ---------------------------------------------------------------- assembly

async def _safe(coro, default=None):
    try:
        return await coro
    except Exception:
        return default if default is not None else {}


async def fetch(client, category: str, title: str, year: Optional[int], creator: Optional[str] = None) -> dict:
    """Gather everything we can find. Returns {} when nothing matched."""
    async def wiki_part():
        qid = await _wikidata_find(client, category, title, year)
        if not qid:
            return {}
        facts = await wikidata_facts(client, category, qid)
        summary = await wikipedia_summary(client, facts["wikipedia_title"]) if facts.get("wikipedia_title") else {}
        return {"wikidata": facts, "wikipedia": summary}

    extra_source = {
        "tv": lambda: tvmaze_details(client, title, year),
        "anime": lambda: jikan_details(client, title, year),
        "game": lambda: rawg_details(client, title, year),
        "book": lambda: openlibrary_details(client, title, year, creator),
        "album": lambda: itunes_details(client, title, year, creator),
    }.get(category)
    wiki, extra = await asyncio.gather(
        _safe(wiki_part()), _safe(extra_source()) if extra_source else asyncio.sleep(0, result={}),
    )
    wikidata = wiki.get("wikidata") or {}
    wikipedia = wiki.get("wikipedia") or {}
    extra = extra or {}
    if not wikidata and not wikipedia and not extra:
        return {}

    sources, links = [], []
    description, description_source = None, None
    if wikipedia.get("description"):
        description = wikipedia["description"]
        description_source = {"name": "Wikipedia", "url": wikipedia["url"], "license": "CC BY-SA 4.0",
                              "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"}
    elif category == "tv" and extra.get("summary"):
        description = extra["summary"]
        description_source = {"name": "TVmaze", "url": extra.get("url"), "license": "CC BY-SA 4.0",
                              "license_url": "https://creativecommons.org/licenses/by-sa/4.0/"}
    elif category == "game" and extra.get("summary"):
        description = extra["summary"][:2000]
        description_source = {"name": "RAWG", "url": extra.get("url")}
    if description and len(description) > 2400:
        description = description[:2400].rsplit(" ", 1)[0] + "…"

    if wikipedia.get("url"):
        links.append({"label": "Wikipedia", "url": wikipedia["url"]})
        sources.append({"name": "Wikipedia", "url": wikipedia["url"], "license": "CC BY-SA 4.0"})
    if wikidata.get("qid"):
        sources.append({"name": "Wikidata", "url": f"https://www.wikidata.org/wiki/{wikidata['qid']}", "license": "CC0"})
    if wikidata.get("imdb_url"):
        links.append({"label": "IMDb", "url": wikidata["imdb_url"]})
    extra_names = {"tv": "TVmaze", "anime": "MyAnimeList", "game": "RAWG", "book": "Open Library", "album": "Apple Music"}
    if extra.get("url"):
        links.append({"label": extra_names[category], "url": extra["url"]})
        sources.append({"name": extra_names[category], "url": extra["url"],
                        "license": "CC BY-SA 4.0" if category == "tv" else ""})
    website = wikidata.get("website") or extra.get("website")
    if website:
        links.append({"label": "Official site", "url": website})

    facts, seen = [], set()
    for fact in (wikidata.get("facts") or []) + (extra.get("facts") or []):
        if fact["label"] in seen or not fact.get("value"):
            continue
        seen.add(fact["label"])
        facts.append(fact)
    scores = list(wikidata.get("scores") or [])
    if extra.get("score") and all(s["source"] != extra["score"]["source"] for s in scores):
        scores.append(extra["score"])
    release = (wikidata.get("release_date") or extra.get("premiered") or extra.get("released")
               or extra.get("aired") or (str(extra["first_published"]) if extra.get("first_published") else None))
    genres = list(dict.fromkeys((extra.get("genres") or []) + (wikidata.get("genres") or [])))[:6]
    trailer = wikidata.get("trailer") or extra.get("trailer")
    return {
        "category": category,
        "description": description,
        "description_source": description_source,
        "short_description": wikipedia.get("short_description") or "",
        "release_date": release,
        "end_date": wikidata.get("end_date") or extra.get("ended"),
        "facts": facts[:10],
        "genres": genres,
        "scores": scores[:5],
        "poster": extra.get("poster") or wikipedia.get("image"),
        "backdrop": (extra.get("gallery") or [{}])[0].get("url") or wikipedia.get("image"),
        "gallery": (extra.get("gallery") or [])[:8],
        "trailer": trailer,
        "tracks": extra.get("tracks") or [],
        "links": links,
        "sources": sources,
        "fetched": datetime.utcnow().strftime("%Y-%m-%d"),
    }


# ---------------------------------------------------------------- cache

def cached(db: Session, key: str) -> tuple[Optional[dict], bool]:
    """(data, is_fresh). data is None for unknown or failed lookups."""
    row = db.query(models.TitleMetadata).filter_by(key=key).first()
    if row is None:
        return None, False
    fresh = datetime.utcnow() - row.fetched_at < FRESH.get(row.status, FRESH["error"])
    data = None
    if row.status == "ok" and row.data:
        try:
            data = json.loads(row.data)
        except ValueError:
            data = None
    return data, fresh


def store(db: Session, key: str, data: Optional[dict], status: str) -> None:
    row = db.query(models.TitleMetadata).filter_by(key=key).first()
    payload = json.dumps(data) if data else None
    if row is None:
        db.add(models.TitleMetadata(key=key, status=status, data=payload, fetched_at=datetime.utcnow()))
    else:
        # Keep the last good copy if a refresh fails.
        if status == "ok" or row.status != "ok":
            row.data = payload
            row.status = status
        row.fetched_at = datetime.utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


_locks: dict[str, asyncio.Lock] = {}


async def get_or_fetch(db: Session, client, category: str, normalized_title: str, display_title: str,
                       year: Optional[int], creator: Optional[str] = None, wait: float = 8.0) -> Optional[dict]:
    key = cache_key(category, normalized_title, year)
    data, fresh = cached(db, key)
    if fresh or client is None:
        return data
    lock = _locks.setdefault(key, asyncio.Lock())
    if lock.locked():
        return data
    async with lock:
        try:
            result = await asyncio.wait_for(fetch(client, category, display_title, year, creator), timeout=wait)
            store(db, key, result or None, "ok" if result else "miss")
            return result or data
        except Exception:
            store(db, key, None, "error")
            return data
        finally:
            _locks.pop(key, None)
