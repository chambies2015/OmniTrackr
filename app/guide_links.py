"""Links between written guides in different sections that cover the same titles.

Each guide already links to others of its own kind ("If you liked something else",
"More franchises in order"). Readers who arrive on /in-order/dune had no way to
find /if-you-liked/dune, or the best-of list that also picks a film from it,
because the catalogs don't know about each other. This module reads every guide
in editorial_index, collects the titles each one writes about, and for a given
guide returns the guides in *other* sections that share titles with it.

``add_crosslinks`` is an html_finish step: on a guide page it adds one
"Elsewhere in the guides" block next to the page's own related guides. A page
that is not a guide, or a guide that shares nothing with the others, is left
unchanged.
"""
from __future__ import annotations

import re
from functools import lru_cache
from html import escape

from . import editorial_index

SITE_URL = "https://omnitrackr.xyz"
MAX_LINKS = 4
MAX_PER_SECTION = 2
MARKER = "data-guide-crosslinks"
_CANONICAL = re.compile(r'<link rel="canonical" href="https://omnitrackr\.xyz(/[^"?#]*)"')
_WORDS = re.compile(r"[a-z0-9]+")
# Leading words that differ between how two guides spell the same title.
_DROP = {"the", "a", "an"}


def _key(title: str) -> str:
    # "Mushi-Shi" and "Mushishi" are the same show; "Spider-Man" stays one word either way.
    words = _WORDS.findall(title.lower().replace("&", " and ").replace("-", ""))
    while words and words[0] in _DROP:
        words = words[1:]
    return " ".join(words)


_KIND_ALIASES = {"movies": "movie", "tv-shows": "tv", "games": "game", "books": "book", "video-games": "game",
                 "albums": "music", "podcasts": "podcast", "audiobooks": "audiobook"}


def _kind(value: dict):
    kind = value.get("kind") or value.get("category")
    return _KIND_ALIASES.get(kind, kind) if isinstance(kind, str) else None


def _walk(value, found: dict) -> None:
    """Collect titles, creators and kinds from every dict that describes a title."""
    if isinstance(value, dict):
        title = value.get("title")
        if isinstance(title, str) and title and ("kind" in value or "category" in value or "year" in value):
            found["titles"].setdefault(_key(title), title)
            for other in value.get("aka") or ():
                found["titles"].setdefault(_key(other), title)
            creator = value.get("creator")
            if isinstance(creator, str) and creator:
                found["creators"].setdefault(_key(creator), creator)
            kind = _kind(value)
            if kind:
                found["kinds"][kind] = found["kinds"].get(kind, 0) + 1
        for child in value.values():
            _walk(child, found)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _walk(child, found)


def _main_kind(section: str, data, found: dict):
    """The one format a guide is about, or None for guides that mix formats on purpose."""
    if isinstance(data, dict):
        if section == "if-you-liked":
            return _kind(data["anchor"])
        if section == "best-of":
            return _kind(data)
        if section == "new-releases" and data.get("focus"):
            return _KIND_ALIASES.get(data["focus"], data["focus"])
    if section == "in-order" and found["kinds"]:
        kind, count = max(found["kinds"].items(), key=lambda row: row[1])
        if count * 2 > sum(found["kinds"].values()):
            return kind
    return None


def _source(section: str, href: str):
    """The catalog data behind one editorial_index entry."""
    slug = href.rstrip("/").rsplit("/", 1)[-1]
    if section == "discover":
        from .discover_catalog import TRAILS
        from .discover_guides import GUIDES
        return [TRAILS.get(slug), GUIDES.get(slug)]
    if section == "monthly":
        from .discover_catalog import published_editions
        return published_editions().get(slug)
    if section == "in-order":
        from .in_order_guides import GUIDES
        return GUIDES.get(slug)
    if section == "if-you-liked":
        from .if_you_liked_guides import GUIDES
        return GUIDES.get(slug)
    if section == "seasonal":
        from .gift_guides import GUIDE
        from .seasonal_guides import SEASONS
        if href == GUIDE["path"]:
            return GUIDE
        return next((entry for entry in SEASONS.values() if entry["path"] == href), None)
    if section == "best-of":
        from . import best_of
        from .best_of_guides import GUIDES
        return next((entry for key, entry in GUIDES.items() if best_of.path(key) == href), None)
    if section == "new-releases":
        from . import new_releases
        return new_releases.published().get(slug)
    return None


@lru_cache(maxsize=1)
def _index_for(_day: str) -> dict[str, dict]:
    index = {}
    for piece in editorial_index.entries():
        data = _source(piece["section"], piece["href"])
        found = {"titles": {}, "creators": {}, "kinds": {}}
        _walk(data, found)
        found["titles"].pop("", None)
        found["creators"].pop("", None)
        index[piece["href"]] = {**piece, **found, "kind": _main_kind(piece["section"], data, found)}
    return index


def _index() -> dict[str, dict]:
    # Release guides go live on their publish date, so the index is rebuilt daily.
    from datetime import date
    return _index_for(date.today().isoformat())


def titles(href: str) -> dict[str, str]:
    entry = _index().get(href)
    return dict(entry["titles"]) if entry else {}


def _score(own: dict, other: dict) -> tuple[float, list[str], list[str]]:
    shared = [key for key in own["titles"] if key in other["titles"]]
    creators = [key for key in own["creators"] if key in other["creators"]]
    same_kind = bool(own["kind"]) and own["kind"] == other["kind"]
    score = 3 * len(shared) + 1.5 * min(len(creators), 2) + (1 if same_kind else 0)
    return score, shared, creators


def related(href: str, limit: int = MAX_LINKS) -> list[dict]:
    """Guides in other sections that share titles, creators or a format with this one.

    Shared titles count most, then shared creators (Denis Villeneuve made both Dune
    and Arrival), then a shared format (a TV "If you liked" guide and the year's best
    TV). Each result is an editorial_index entry plus "shared" and "creators" (as this
    page spells them) and "kind" (the format both guides are about, or None).
    """
    index = _index()
    own = index.get(href)
    if not own:
        return []
    scored = []
    for other_href, other in index.items():
        if other_href == href or other["section"] == own["section"]:
            continue
        score, shared, creators = _score(own, other)
        if score:
            scored.append((score, other["updated"], other, shared, creators))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    picked, per_section = [], {}
    for _, _, other, shared, creators in scored:
        if per_section.get(other["section"], 0) >= MAX_PER_SECTION:
            continue
        per_section[other["section"]] = per_section.get(other["section"], 0) + 1
        picked.append({key: other[key] for key in ("section", "href", "name", "summary", "updated")}
                      | {"shared": [own["titles"][key] for key in shared],
                         "creators": [own["creators"][key] for key in creators],
                         "kind": own["kind"] if own["kind"] == other["kind"] else None})
        if len(picked) >= limit:
            break
    return picked


KIND_PLURALS = {"movie": "films", "tv": "TV shows", "anime": "anime", "game": "games", "book": "books",
                "music": "albums", "manga": "manga", "podcast": "podcasts", "audiobook": "audiobooks"}


def _names(values: list[str]) -> str:
    names = [f"<em>{escape(name)}</em>" for name in values[:3]]
    if len(values) > 3:
        names.append(f"{len(values) - 3} more")
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _reason(link: dict) -> str:
    if link["shared"]:
        return f"Also covers {_names(link['shared'])}."
    if link["creators"]:
        return f"Also picks work by {_names(link['creators'])}."
    return f"More {escape(KIND_PLURALS.get(link['kind'], 'picks'))}, chosen another way."


def block_html(href: str) -> str:
    links = related(href)
    if not links:
        return ""
    heading = ("Other guides that cover these titles" if all(link["shared"] for link in links)
               else "Related guides from other sections")
    cards = "".join(
        f'<article><p class="eyebrow">{escape(editorial_index.SECTION_LABELS[link["section"]].upper())}</p>'
        f'<h3><a href="{escape(link["href"], quote=True)}">{escape(link["name"])}</a></h3>'
        f'<p><strong>{_reason(link)}</strong> {escape(link["summary"])}</p></article>'
        for link in links
    )
    return (
        f'<section class="guide-related guide-crosslinks" {MARKER} aria-labelledby="crosslinks-heading">'
        '<p class="eyebrow">ELSEWHERE IN THE GUIDES</p>'
        f'<h2 id="crosslinks-heading">{heading}</h2>'
        f'<div class="guide-related-grid">{cards}</div></section>'
    )


def add_crosslinks(html: str) -> str:
    """html_finish step: add the cross-section block to a guide page."""
    if MARKER in html:
        return html
    match = _CANONICAL.search(html)
    if not match or match.group(1) not in _index():
        return html
    block = block_html(match.group(1))
    if not block:
        return html
    for anchor in ('<section class="guide-related"', '</main>'):
        position = html.find(anchor)
        if position != -1:
            return html[:position] + block + html[position:]
    return html
