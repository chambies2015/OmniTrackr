"""Optional affiliate "where to get it" links.

Everything here is off until the site owner sets an environment variable, so a
deploy without configuration renders exactly what it did before.

* AMAZON_ASSOCIATES_TAG  - e.g. "omnitrackr-20". Enables Amazon search links
  for movies, TV, anime, games, music and books.
* AFFILIATE_DISCLOSURE   - optional override for the disclosure sentence.

Links are search links (title + format), so they work for any title without a
product database, and they always open in a new tab with rel="sponsored".
"""
from __future__ import annotations

import os
import re
from html import escape
from urllib.parse import urlencode

# Amazon search index per OmniTrackr category, plus a word that steers the
# search towards the right format.
AMAZON_INDEX = {
    "movies": ("movies-tv", "movie"),
    "tv": ("movies-tv", "tv series"),
    "anime": ("movies-tv", "anime"),
    "games": ("videogames", ""),
    "music": ("popular", "album"),
    "books": ("stripbooks", ""),
}
CATEGORY_ALIASES = {
    "movie": "movies", "movies": "movies",
    "tv": "tv", "tv_show": "tv", "tv-shows": "tv",
    "anime": "anime",
    "video_game": "games", "video-games": "games", "games": "games",
    "music": "music",
    "book": "books", "books": "books",
}
LINK_LABELS = {
    "movies": "Find it on Amazon",
    "tv": "Find it on Amazon",
    "anime": "Find it on Amazon",
    "games": "Pre-order or buy on Amazon",
    "music": "Find it on Amazon",
    "books": "Find it on Amazon",
}
DEFAULT_DISCLOSURE = "As an Amazon Associate OmniTrackr earns from qualifying purchases. It never changes what we list."


def amazon_tag() -> str:
    tag = os.getenv("AMAZON_ASSOCIATES_TAG", "").strip()
    return tag if re.fullmatch(r"[A-Za-z0-9_-]{2,40}", tag) else ""


def affiliate_enabled() -> bool:
    return bool(amazon_tag())


def disclosure_text() -> str:
    return os.getenv("AFFILIATE_DISCLOSURE", "").strip()[:300] or DEFAULT_DISCLOSURE


def links_for(category: str, title: str, creator: str = "") -> list[dict]:
    """Return [{label, url}] for one title, or [] when affiliate links are off."""
    category = CATEGORY_ALIASES.get(category, "")
    tag = amazon_tag()
    title = re.sub(r"\s+", " ", title or "").strip()[:150]
    if not tag or not category or not title:
        return []
    index, hint = AMAZON_INDEX[category]
    keywords = " ".join(part for part in (title, (creator or "").strip()[:80], hint) if part)
    url = "https://www.amazon.com/s?" + urlencode({"k": keywords, "i": index, "tag": tag})
    return [{"label": LINK_LABELS[category], "url": url, "merchant": "Amazon"}]


def links_html(category: str, title: str, creator: str = "", css_class: str = "affiliate-links") -> str:
    links = links_for(category, title, creator)
    if not links:
        return ""
    anchors = "".join(
        f'<a class="affiliate-link" href="{escape(link["url"], quote=True)}" target="_blank" '
        f'rel="sponsored noopener noreferrer">{escape(link["label"])} ↗</a>'
        for link in links
    )
    return f'<span class="{escape(css_class, quote=True)}">{anchors}</span>'


def disclosure_html(css_class: str = "affiliate-disclosure") -> str:
    if not affiliate_enabled():
        return ""
    return f'<p class="{escape(css_class, quote=True)}">{escape(disclosure_text())}</p>'
