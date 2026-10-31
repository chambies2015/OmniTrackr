"""Ask image CDNs for a poster-sized copy instead of the original upload.

RAWG serves its game covers and screenshots at the size the publisher uploaded,
often 1920 or 3840 pixels wide and up to 4 MB, and the public pages show them at
about 120 to 200 CSS pixels. RAWG also serves resized copies of the same file
under /media/resize/<width>/-/, so asking for that instead is a URL change with
no proxy, no cache and no change to what is stored in anyone's library. MyAnimeList
covers ending in "l.jpg" are the large version; small thumbnails can use the
regular one.

Only <img> src and srcset values in HTML responses are rewritten (see
html_finish.py). Links, share tags and structured data keep the original URL.
"""
from __future__ import annotations

import re
from typing import Optional

# RAWG only serves a few widths; anything else is a 307 back to the original.
RAWG_WIDTHS = (200, 420, 640, 1280)
_RAWG = re.compile(r"^https://media\.rawg\.io/media/(games|screenshots)/(?P<rest>[0-9a-f]{3}/[0-9a-f]{32}\.(?:jpe?g|png|webp))$", re.I)
_MAL_LARGE = re.compile(r"^(https://cdn\.myanimelist\.net/images/(?:anime|manga)/\d+/\d+)l(\.(?:jpe?g|webp))$", re.I)

POSTER_WIDTH = 420
HERO_WIDTH = 640
BACKDROP_WIDTH = 1280
# A MyAnimeList thumbnail drawn at this many CSS pixels or fewer looks the same
# from the 225-pixel regular cover on a 2x screen.
MAL_SMALL_MAX = 112

_IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
_SRC = re.compile(r'(\ssrc=")([^"]+)(")', re.I)
_SRCSET = re.compile(r'(\ssrcset=")([^"]+)(")', re.I)
_WIDTH = re.compile(r'\swidth="(\d{1,4})"', re.I)
_CLASS = re.compile(r'\sclass="([^"]*)"', re.I)


def sized(url: Optional[str], width: int = POSTER_WIDTH, *, display_width: Optional[int] = None) -> Optional[str]:
    """Return a smaller copy of a known CDN image, or the URL unchanged."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return url
    match = _RAWG.match(url)
    if match:
        target = next((w for w in RAWG_WIDTHS if w >= width), RAWG_WIDTHS[-1])
        return f"https://media.rawg.io/media/resize/{target}/-/{match.group(1)}/{match.group('rest')}"
    if display_width is not None and display_width <= MAL_SMALL_MAX:
        match = _MAL_LARGE.match(url)
        if match:
            return match.group(1) + match.group(2)
    return url


def _tag_width(tag: str) -> int:
    classes = (_CLASS.search(tag).group(1) if _CLASS.search(tag) else "").lower()
    if "backdrop" in classes:
        return BACKDROP_WIDTH
    if "hero" in classes or 'fetchpriority="high"' in tag:
        return HERO_WIDTH
    return POSTER_WIDTH


def _rewrite_tag(match: re.Match) -> str:
    tag = match.group(0)
    if "media.rawg.io" not in tag and "myanimelist.net" not in tag:
        return tag
    width = _tag_width(tag)
    declared = _WIDTH.search(tag)
    # width="200" height="300" on the release lists is an aspect-ratio hint, so
    # only the small review thumbnails (64 px) count as a display width.
    display = int(declared.group(1)) if declared and int(declared.group(1)) <= MAL_SMALL_MAX else None
    tag = _SRC.sub(lambda m: m.group(1) + (sized(m.group(2), width, display_width=display) or m.group(2)) + m.group(3), tag, count=1)

    def srcset(m: re.Match) -> str:
        parts = []
        for candidate in m.group(2).split(","):
            bits = candidate.strip().split()
            if bits:
                bits[0] = sized(bits[0], width, display_width=display) or bits[0]
            parts.append(" ".join(bits))
        return m.group(1) + ", ".join(parts) + m.group(3)

    return _SRCSET.sub(srcset, tag, count=1)


def shrink_html(html: str) -> str:
    """Rewrite oversized CDN images in every <img> tag of a page."""
    if "media.rawg.io/media/" not in html and "myanimelist.net/images/" not in html:
        return html
    return _IMG_TAG.sub(_rewrite_tag, html)
