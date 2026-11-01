"""BreadcrumbList structured data for indexed pages that don't carry their own.

The homepage, the tracker guides and a few others write their own breadcrumbs.
About ninety indexed pages (Discover trails, "If you liked", franchise orders,
best-of lists, daily puzzles, weekly roundups, public lists...) had none, so
Google had to guess where each one sits. This builds the trail from the page's
canonical URL: Home, then the section hub the page belongs to, then the page
itself, named from its <title>.

Pages that are noindex, have no canonical link, or already have a
BreadcrumbList are left alone. Only real hub pages appear as a middle step.
"""
from __future__ import annotations

import json
import re
from html import unescape
from typing import Optional
from urllib.parse import urlsplit

# Section hubs: path -> the name shown in the trail. A page's parent is the
# longest hub its path starts with (PARENTS covers the ones that don't nest).
HUBS = {
    "/discover": "Discover",
    "/if-you-liked": "If you liked",
    "/in-order": "Franchises in order",
    "/best-of": "Best of the year",
    "/new-releases": "Release guides",
    "/daily": "OmniTrackr Daily",
    "/new-this-week/archive": "New this week",
    "/collections/explore": "Public lists",
    "/browse": "Browse shelves",
    "/challenges": "Monthly challenges",
    "/reviews": "Reviews",
    "/release-radar": "Release Radar",
    "/titles": "Titles",
    "/trending": "Trending",
    "/people": "People",
    "/studios": "Studios",
    "/guides": "Guides",
    "/holidays": "Holiday picks",
    "/halloween": "Halloween picks",
}
PARENTS = {
    "/new-this-week/": "/new-this-week/archive",
    "/collections/public/": "/collections/explore",
    "/daily/archive": "/daily",
}

_CANONICAL = re.compile(r'<link rel="canonical" href="(https://[^"]+)"', re.I)
_ROBOTS = re.compile(r'<meta name="robots" content="([^"]*)"', re.I)
_TITLE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
_NONCE = re.compile(r'<script\b[^>]*\snonce="([A-Za-z0-9_+/=-]+)"', re.I)
_SUFFIX = re.compile(r"\s*(?:[|\-–—]\s*(?:OmniTrackr(?: Collection)?|Discover)\s*)+$", re.I)


def _page_name(html: str) -> Optional[str]:
    match = _TITLE.search(html)
    if not match:
        return None
    name = _SUFFIX.sub("", " ".join(unescape(match.group(1)).split()))
    # "Movies like Interstellar: 7 to watch, play..." reads as "Movies like Interstellar".
    head, sep, _ = name.partition(": ")
    if sep and len(name) > 40 and len(head.split()) >= 2:
        name = head
    return name.strip() or None


def _parent(path: str) -> Optional[str]:
    for prefix, hub in PARENTS.items():
        if path.startswith(prefix) and path != hub:
            return hub
    best = None
    for hub in HUBS:
        if path != hub and path.startswith(hub + "/") and (best is None or len(hub) > len(best)):
            best = hub
    return best


def trail(canonical: str, name: str) -> list[tuple[str, str]]:
    """[(name, url), ...] from Home to the page itself."""
    parts = urlsplit(canonical)
    origin = f"{parts.scheme}://{parts.netloc}"
    path = parts.path.rstrip("/") or "/"
    steps = [("Home", origin + "/")]
    if path == "/":
        return steps
    # /reviews?category=movie is a filtered view that sits under /reviews itself.
    filtered_hub = bool(parts.query) and path in HUBS
    hubs = []
    parent = path if filtered_hub else _parent(path)
    while parent:
        hubs.append(parent)
        parent = _parent(parent)
    for hub in reversed(hubs):
        steps.append((HUBS[hub], origin + hub))
    leaf = None if filtered_hub else HUBS.get(path)
    steps.append((leaf or name, canonical))
    return steps


def breadcrumb_json(steps: list[tuple[str, str]]) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": index, "name": label, "item": url}
            for index, (label, url) in enumerate(steps, start=1)
        ],
    }
    # "</" can't appear inside a <script> block.
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def add_breadcrumbs(html: str) -> str:
    if "</head>" not in html or "BreadcrumbList" in html:
        return html
    head = html[: html.find("</head>")]
    robots = _ROBOTS.search(head)
    canonical = _CANONICAL.search(head)
    if not robots or "noindex" in robots.group(1).lower() or "index" not in robots.group(1).lower() or not canonical:
        return html
    url = unescape(canonical.group(1))
    if (urlsplit(url).path.rstrip("/") or "/") == "/":
        return html
    name = _page_name(head)
    if not name:
        return html
    # Pages sent with a nonce CSP put the nonce on every script tag; match them.
    nonce = _NONCE.search(head)
    nonce_attr = f' nonce="{nonce.group(1)}"' if nonce else ""
    block = f'<script type="application/ld+json"{nonce_attr}>{breadcrumb_json(trail(url, name))}</script>\n'
    return html.replace("</head>", block + "</head>", 1)
