"""Reads what another app shares into OmniTrackr and works out which title it is.

The installed app registers as a share target (see routers/pwa.py), so on Android
a member can tap Share in IMDb, Spotify, Goodreads, YouTube and so on and pick
OmniTrackr. The phone sends whatever the other app put in the share sheet: a
link, a line of text, a page title, or any mix of the three, with no fixed format.

read_share() turns that into a search the dashboard's "Add anything" box can
run: a clean title, which shelf to search, and the year when the text gives one.
It only parses strings. lookup_extras() is the optional network step: it asks
Spotify or YouTube for the name behind a bare link, and OMDb for the exact title
behind an IMDb id.
"""
from __future__ import annotations

import os
import re
import string
from dataclasses import dataclass, replace
from typing import Optional
from urllib.parse import quote, unquote, urlsplit

import httpx

# Shelves the dashboard search knows, plus "screen" for links that could be a
# film or a series (IMDb, Netflix and the like) so both get searched.
KINDS = ("movies", "tv-shows", "anime", "video-games", "music", "books", "manga", "podcasts", "audiobooks", "screen")
MAX_FIELD = 2000
# Titles sit at the start of shared text; the rest is descriptions. Keeping the regex work to
# this many characters bounds every pattern below, whatever the other app sends.
MAX_TITLE_TEXT = 300
MAX_SLUG = 200
MAX_QUERY = 120
MAX_ENCODED_QUERY = 400
LOOKUP_TIMEOUT = httpx.Timeout(3.0, connect=2.0)

_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_IMDB_ID = re.compile(r"/title/(tt\d{7,10})(?:/|$)")
_YEAR_IN_PARENS = re.compile(
    r"\s*\((?P<label>(?:TV|Video|Podcast)?\s*(?:Series|Mini[- ]Series|Movie|Special|Short|Game)?\s*)"
    r"(?P<year>(?:19|20)\d{2})(?:\s*[–—-]\s*(?:(?:19|20)\d{2})?\s*)?\)",
    re.IGNORECASE,
)
_RATING = re.compile(r"\s*(?:⭐|★|☆)\s*\d.*$")
_SEPARATOR = re.compile(r"\s+[|•·—–-]\s+")

# Site names that end page titles ("Dune - IMDb", "Hades on Steam").
_SITE_NAMES = (
    "imdb", "spotify", "youtube", "youtube music", "goodreads", "letterboxd", "myanimelist", "myanimelist.net",
    "anilist", "steam", "netflix", "apple music", "apple podcasts", "apple books", "apple tv", "apple tv+",
    "audible", "audible.com", "audible.co.uk", "amazon", "amazon.com", "amazon.co.uk", "prime video", "crunchyroll",
    "rotten tomatoes", "open library", "backloggd", "rawg", "tmdb", "the movie database", "the movie database (tmdb)",
    "trakt", "trakt.tv", "bandcamp", "mangadex", "kitsu", "storygraph", "the storygraph", "disney+", "hulu", "max",
    "pocket casts", "overcast", "deezer", "tidal", "soundcloud", "gog.com", "epic games store", "igdb",
    "playstation store", "nintendo", "xbox", "metacritic", "justwatch", "barnes & noble", "libby", "kindle",
    "scribd", "everand", "google play", "google books", "wikipedia",
)
_SITE_SUFFIX = re.compile(
    r"\s+(?:on|at|via|from|\|)\s+(?:" + "|".join(re.escape(name) for name in sorted(_SITE_NAMES, key=len, reverse=True))
    + r")\s*$",
    re.IGNORECASE,
)
_SITE_SEGMENT = re.compile(
    r"^(?:" + "|".join(re.escape(name) for name in sorted(_SITE_NAMES, key=len, reverse=True))
    + r")(?:\s+(?:\w+\s+)?(?:page|app|store))?$",
    re.IGNORECASE,
)
# Segments that mean "the rest is about a video, not the title": trailers, clips and so on.
_VIDEO_NOISE = re.compile(
    r"\b(?:trailer|teaser|official\s+(?:music\s+)?video|official\s+audio|music\s+video|lyric\s+video|lyrics|"
    r"visualizer|full\s+album|official\s+clip|gameplay|first\s+look|sneak\s+peek)\b",
    re.IGNORECASE,
)
_VIDEO_NOISE_INLINE = re.compile(
    r"\s*[\(\[](?:official\s+)?(?:\w+\s+)?(?:trailer|teaser|music video|video|audio|lyric video|lyrics|visualizer|"
    r"hd|4k|remastered(?:\s+\d{4})?)(?:\s+\d+)?[\)\]]",
    re.IGNORECASE,
)
_SPOTIFY_BY = re.compile(r"^(?P<title>.+?)\s+[-–—]\s+(?:album|single|ep|song|podcast|audiobook|compilation)\s+by\s+(?P<who>.+)$",
                         re.IGNORECASE)
_LEADING_CHATTER = re.compile(
    r"^(?:(?:hey|look|ooh|omg)[,!]?\s+)?(?:check\s+(?:this|it)\s+out[:!,]?\s+|check\s+out\s+|listen\s+to\s+|"
    r"(?:you\s+should\s+)?(?:watch|read|play|listen\s+to)\s+|i(?:'|’)?m\s+(?:watching|reading|playing|listening\s+to)\s+|"
    r"now\s+(?:watching|reading|playing)[:\s]+|currently\s+(?:watching|reading|playing)[:\s]+|"
    r"i\s+(?:just\s+)?(?:watched|read|played|finished|loved)\s+)",
    re.IGNORECASE,
)
_TRAILING_CHATTER = re.compile(r"\s+(?:by\s+[^|]+?\s+)?on\s+(?:" + "|".join(re.escape(name) for name in _SITE_NAMES) + r")[.!]?$",
                               re.IGNORECASE)
_TITLE_GARBAGE = re.compile(r"^(?:share|untitled|home|watch|listen|read|play|search|login|sign in|log in)$", re.IGNORECASE)
_NETFLIX_WATCH = re.compile(r"^watch\s+(.+?)(?:\s+\|\s+netflix.*)?$", re.IGNORECASE)
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


@dataclass(frozen=True)
class SharedTitle:
    query: str = ""
    kind: Optional[str] = None
    source: Optional[str] = None
    year: Optional[str] = None
    imdb_id: Optional[str] = None
    link: Optional[str] = None
    who: Optional[str] = None  # artist or author when the share names one

    def search_query(self) -> str:
        """The text the dashboard searches: title, plus the artist or author for music and books."""
        if self.who and self.kind in {"music", "books", "audiobooks"} and self.who.lower() not in self.query.lower():
            return f"{self.query} {self.who}"[:MAX_QUERY].strip()
        return self.query

    def dashboard_path(self) -> str:
        """Where the dashboard picks the share up: /?share=1&q=…&kind=…&year=…&via=…, always in this order."""
        parts = ["share=1"]
        query = self.search_query()
        encoded = quote(query, safe="")
        while len(encoded) > MAX_ENCODED_QUERY:  # long non-Latin titles; keeps the sign-in return link short
            query = query[:-1]
            encoded = quote(query, safe="")
        if query:
            parts.append("q=" + encoded)
        if self.kind:
            parts.append("kind=" + self.kind)
        if self.year:
            parts.append("year=" + self.year)
        if self.source:
            parts.append("via=" + self.source)
        return "/?" + "&".join(parts)


@dataclass(frozen=True)
class _Site:
    key: str
    hosts: tuple[str, ...]
    kind: Optional[str] = None


# Hosts we recognise. The key is what the dashboard shows as "Shared from …".
_SITES = (
    _Site("imdb", ("imdb.com",), "screen"),
    _Site("tmdb", ("themoviedb.org",)),
    _Site("letterboxd", ("letterboxd.com", "boxd.it"), "movies"),
    _Site("trakt", ("trakt.tv",)),
    _Site("rottentomatoes", ("rottentomatoes.com",)),
    _Site("justwatch", ("justwatch.com",)),
    _Site("netflix", ("netflix.com",), "screen"),
    _Site("primevideo", ("primevideo.com",), "screen"),
    _Site("disneyplus", ("disneyplus.com",), "screen"),
    _Site("hulu", ("hulu.com",), "screen"),
    _Site("max", ("max.com", "hbomax.com"), "screen"),
    _Site("appletv", ("tv.apple.com",), "screen"),
    _Site("myanimelist", ("myanimelist.net",)),
    _Site("anilist", ("anilist.co",)),
    _Site("crunchyroll", ("crunchyroll.com",), "anime"),
    _Site("kitsu", ("kitsu.io", "kitsu.app")),
    _Site("mangadex", ("mangadex.org",), "manga"),
    _Site("steam", ("store.steampowered.com", "steamcommunity.com"), "video-games"),
    _Site("rawg", ("rawg.io",), "video-games"),
    _Site("backloggd", ("backloggd.com",), "video-games"),
    _Site("igdb", ("igdb.com",), "video-games"),
    _Site("gog", ("gog.com",), "video-games"),
    _Site("epic", ("store.epicgames.com",), "video-games"),
    _Site("playstation", ("store.playstation.com",), "video-games"),
    _Site("nintendo", ("nintendo.com",), "video-games"),
    _Site("xbox", ("xbox.com",), "video-games"),
    _Site("spotify", ("open.spotify.com", "spotify.link", "spotify.com")),
    _Site("applemusic", ("music.apple.com",), "music"),
    _Site("applepodcasts", ("podcasts.apple.com",), "podcasts"),
    _Site("applebooks", ("books.apple.com",), "books"),
    _Site("youtubemusic", ("music.youtube.com",), "music"),
    _Site("youtube", ("youtube.com", "youtu.be")),
    _Site("bandcamp", ("bandcamp.com",), "music"),
    _Site("deezer", ("deezer.com", "deezer.page.link"), "music"),
    _Site("tidal", ("tidal.com",), "music"),
    _Site("soundcloud", ("soundcloud.com",), "music"),
    _Site("pocketcasts", ("pca.st", "pocketcasts.com"), "podcasts"),
    _Site("overcast", ("overcast.fm",), "podcasts"),
    _Site("goodreads", ("goodreads.com",), "books"),
    _Site("openlibrary", ("openlibrary.org",), "books"),
    _Site("storygraph", ("thestorygraph.com", "app.thestorygraph.com"), "books"),
    _Site("audible", ("audible.com", "audible.co.uk", "audible.ca", "audible.com.au", "audible.de", "audible.fr"),
          "audiobooks"),
    _Site("amazon", ("amazon.com", "amazon.co.uk", "amazon.ca", "amazon.com.au", "amazon.de", "amzn.to", "a.co")),
    _Site("libby", ("libbyapp.com", "share.libbyapp.com"), "books"),
)


def _site_for(host: str) -> Optional[_Site]:
    host = host.lower().rstrip(".")
    for site in _SITES:
        for known in site.hosts:
            if host == known or host.endswith("." + known):
                return site
    return None


def _clip(value: Optional[str]) -> str:
    return str(value or "")[:MAX_FIELD]


def _first_url(*values: str) -> Optional[str]:
    for value in values:
        match = _URL.search(value or "")
        if match:
            return match.group(0).rstrip(").,!?;:'\"]")
    return None


def _from_slug(slug: str) -> str:
    """'Sousou_no_Frieren' or 'dune-part-two' or '1145360.Hades' -> words."""
    slug = unquote(slug)
    slug = re.sub(r"^\d+[-._]?", "", slug)  # leading numeric ids: TMDB "693134-dune", Goodreads "44767458.Dune"
    slug = re.sub(r"[-_.+]+", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip()
    # A slug that is only an id (hex, digits, Amazon ASIN) says nothing about the title.
    if not slug or re.fullmatch(r"[0-9a-f ]{8,}|\d+|[A-Z0-9]{10}|id\d+", slug, re.IGNORECASE):
        return ""
    return string.capwords(slug) if slug == slug.lower() else slug


def _read_link(link: str) -> tuple[Optional[_Site], Optional[str], str, Optional[str], Optional[str]]:
    """Returns (site, kind, title from the link path, imdb id, clean link)."""
    try:
        parts = urlsplit(link)
    except ValueError:
        return None, None, "", None, None
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None, None, "", None, None
    host = parts.hostname.lower()
    clean = f"https://{host}{parts.path}"
    site = _site_for(host)
    segments = [segment[:MAX_SLUG] for segment in parts.path.split("/") if segment]
    lowered = [segment.lower() for segment in segments]
    kind = site.kind if site else None
    slug = ""
    imdb_id = None

    def after(*names: str, skip: int = 0) -> str:
        for index, segment in enumerate(lowered):
            if segment in names and index + 1 + skip < len(segments):
                return segments[index + 1 + skip]
        return ""

    key = site.key if site else ""
    if key == "imdb":
        match = _IMDB_ID.search(parts.path + "/")
        imdb_id = match.group(1) if match else None
    elif key == "tmdb":
        if "movie" in lowered:
            kind, slug = "movies", after("movie")
        elif "tv" in lowered:
            kind, slug = "tv-shows", after("tv")
    elif key == "letterboxd":
        slug = after("film")
    elif key == "trakt":
        if "movies" in lowered:
            kind, slug = "movies", after("movies")
        elif "shows" in lowered:
            kind, slug = "tv-shows", after("shows")
    elif key == "rottentomatoes":
        if "m" in lowered:
            kind, slug = "movies", after("m")
        elif "tv" in lowered:
            kind, slug = "tv-shows", after("tv")
    elif key == "justwatch":
        if "movie" in lowered:
            kind, slug = "movies", after("movie")
        elif "tv-show" in lowered or "tv-series" in lowered:
            kind, slug = "tv-shows", after("tv-show", "tv-series")
    elif key in {"myanimelist", "anilist", "kitsu"}:
        for name in ("anime", "manga"):
            if name in lowered:
                kind = name
                index = lowered.index(name)
                rest = segments[index + 1:index + 3]
                # MAL and AniList: /anime/<id>/<slug>; Kitsu: /anime/<slug>.
                slug = rest[1] if len(rest) == 2 and rest[0].isdigit() else (rest[0] if rest and not rest[0].isdigit() else "")
                break
    elif key == "crunchyroll":
        slug = after("series", skip=1) or after("watch", skip=1)
    elif key == "mangadex":
        slug = after("title", skip=1)
    elif key == "steam":
        slug = after("app", skip=1)
    elif key in {"rawg", "backloggd", "igdb"}:
        slug = after("games", "game")
    elif key == "gog":
        slug = after("game")
    elif key == "epic":
        slug = after("p")
    elif key == "spotify":
        for name, shelf in (("album", "music"), ("track", "music"), ("artist", "music"), ("show", "podcasts"),
                            ("episode", "podcasts"), ("audiobook", "audiobooks")):
            if name in lowered:
                kind = shelf
                break
    elif key in {"applemusic", "applepodcasts", "applebooks"}:
        for name, shelf in (("album", "music"), ("podcast", "podcasts"), ("audiobook", "audiobooks"), ("book", "books")):
            if name in lowered:
                kind, slug = shelf, after(name)
                break
    elif key == "bandcamp":
        slug = after("album", "track")
    elif key == "goodreads":
        slug = after("show")
    elif key == "openlibrary":
        slug = after("works", "books", skip=1)
    elif key == "audible":
        slug = after("pd")
        slug = re.sub(r"[-_]Audiobook$", "", slug, flags=re.IGNORECASE)
    elif key == "amazon":
        if "dp" in lowered and lowered.index("dp") > 0:
            slug = segments[lowered.index("dp") - 1]
        slug = re.sub(r"[-_](?:Audible[-_])?Audiobook.*$", "", slug, flags=re.IGNORECASE)
    elif key == "youtube" and host.startswith("music."):
        kind = "music"
    title = _from_slug(slug) if slug else ""
    return site, kind, title, imdb_id, clean


def clean_title(raw: str, *, split_by: bool = False) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
    """Strips site names, trailer words, ratings and chatter from shared text.

    Returns (title, year, kind hint, artist/author). split_by reads "Dune by Frank
    Herbert" as a title and an author; it is only safe when the link says the share
    is a book or an album, since plenty of films are called "Stand by Me".
    """
    text = _EMOJI.sub(" ", _URL.sub(" ", raw or ""))
    text = re.sub(r"[\r\n\t]+", " | ", text)
    text = re.sub(r"\s+", " ", text).strip(" \"'“”‘’|:-–—")[:MAX_TITLE_TEXT]
    if not text:
        return "", None, None, None
    year = kind = who = None
    netflix = _NETFLIX_WATCH.match(text)
    if netflix and re.search(r"netflix", text, re.IGNORECASE):
        text = netflix.group(1)
    # "Title by Artist | Goodreads": drop the site first, then look at the rest.
    for _ in range(3):
        before = text
        text = _SITE_SUFFIX.sub("", text).strip()
        segments = _SEPARATOR.split(text)
        while len(segments) > 1 and _SITE_SEGMENT.match(segments[-1].strip()):
            segments.pop()
        text = " - ".join(segments) if len(segments) > 1 else segments[0]
        if text == before:
            break
    spotify = _SPOTIFY_BY.match(text)
    if spotify:
        text, who = spotify.group("title"), spotify.group("who").strip()
    text = _VIDEO_NOISE_INLINE.sub("", text)
    # Cut at the first segment that is about a video rather than the title itself.
    segments = _SEPARATOR.split(text)
    for index, segment in enumerate(segments):
        if index and _VIDEO_NOISE.search(segment):
            segments = segments[:index]
            break
    text = " - ".join(segments)
    text = _RATING.sub("", text)
    match = _YEAR_IN_PARENS.search(text)
    if match:
        year = match.group("year")
        label = (match.group("label") or "").lower()
        if "series" in label:
            kind = "tv-shows"
        elif "game" in label:
            kind = "video-games"
        elif "movie" in label:
            kind = "movies"
        # Whatever follows "(2024)" is genres, ratings or site chrome.
        text = text[:match.start()]
    text = _LEADING_CHATTER.sub("", text)
    text = _TRAILING_CHATTER.sub("", text)
    # A trailing "(Sousou no Frieren)" alternate title only confuses the search.
    text = re.sub(r"\s*\([^()]{2,80}\)\s*$", "", text) if not re.fullmatch(r".*\(\s*\)\s*", text) else text
    by = re.match(r"^(?P<title>.+?)\s+by\s+(?P<who>[^|]+)$", text, re.IGNORECASE)
    if split_by and by and not who and len(by.group("who").split()) <= 5:
        who = by.group("who").strip()
        text = by.group("title")
    text = re.sub(r"\s+", " ", text).strip(" \"'“”‘’|:-–—,.")
    if _TITLE_GARBAGE.match(text) or _SITE_SEGMENT.match(text):
        text = ""
    return text[:MAX_QUERY].strip(), year, kind, (who or None)


def read_share(title: Optional[str] = None, text: Optional[str] = None, url: Optional[str] = None) -> SharedTitle:
    """Works out a title search from a share sheet's title, text and url fields."""
    title, text, url = _clip(title), _clip(text), _clip(url)
    link = _first_url(url, text, title)
    site = kind = imdb_id = clean_link = None
    slug_title = ""
    if link:
        site, kind, slug_title, imdb_id, clean_link = _read_link(link)
    # Prefer what the person or the other app wrote; the link's path is the fallback.
    query = year = hinted_kind = who = None
    split_by = kind in {"books", "audiobooks", "music"} or (site is not None and site.key == "amazon")
    for candidate in (text, title):
        found, found_year, found_kind, found_who = clean_title(candidate, split_by=split_by)
        if len(found) >= 2:
            query, year, hinted_kind, who = found, found_year, found_kind, found_who
            break
    if not query and slug_title:
        query = slug_title
    if hinted_kind and kind in (None, "screen"):
        kind = hinted_kind
    return SharedTitle(
        query=(query or "").strip(),
        kind=kind if kind in KINDS else None,
        source=site.key if site else None,
        year=year,
        imdb_id=imdb_id,
        link=clean_link,
        who=who,
    )


def needs_name_lookup(shared: SharedTitle) -> bool:
    """A bare Spotify or YouTube link has no title in it; their oEmbed endpoints give one."""
    return not shared.query and shared.source in {"spotify", "youtube", "youtubemusic"} and bool(shared.link)


async def lookup_extras(shared: SharedTitle, client: Optional[httpx.AsyncClient], *, signed_in: bool) -> SharedTitle:
    """Optional network step. Any failure keeps what read_share() found."""
    if client is None or not signed_in:
        return shared
    if needs_name_lookup(shared):
        endpoint = ("https://open.spotify.com/oembed" if shared.source == "spotify"
                    else "https://www.youtube.com/oembed")
        try:
            response = await client.get(endpoint, params={"url": shared.link, "format": "json"}, timeout=LOOKUP_TIMEOUT)
            if response.status_code == 200:
                name = response.json().get("title")
                if isinstance(name, str):
                    found, year, kind, who = clean_title(name[:MAX_FIELD], split_by=shared.kind == "music")
                    if len(found) >= 2:
                        shared = replace(shared, query=found, year=shared.year or year,
                                         kind=shared.kind or kind, who=shared.who or who)
        except (httpx.HTTPError, ValueError, AttributeError):
            pass
    key = os.getenv("OMDB_API_KEY", "")
    if shared.imdb_id and key:
        try:
            response = await client.get("https://www.omdbapi.com/", params={"i": shared.imdb_id, "apikey": key},
                                        timeout=LOOKUP_TIMEOUT)
            data = response.json() if response.status_code == 200 else {}
            if isinstance(data, dict) and data.get("Response") == "True" and isinstance(data.get("Title"), str):
                kind = {"movie": "movies", "series": "tv-shows"}.get(str(data.get("Type", "")).lower(), shared.kind)
                year_match = re.match(r"(?:19|20)\d{2}", str(data.get("Year", "")))
                shared = replace(shared, query=data["Title"][:MAX_QUERY].strip(), kind=kind,
                                 year=year_match.group(0) if year_match else shared.year)
        except (httpx.HTTPError, ValueError, AttributeError):
            pass
    return shared
