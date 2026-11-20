"""Covers, format colours and the guest save dock for Discover, trending and the browse shelves (Nov 20 2026).

The title pages draw a stand-in cover in the format's colour when a title has no art
(title-detail.css, routers/titles._cover_html). These index pages use the same idea at
card size, styled by app/static/explore.css, so a row of picks reads as a row of covers
whether or not the art has been found yet. Pages that load explore.css put class
"explore" on <body>; any element with data-kind="<title kind>" inside takes that
format's colour as --kind.
"""
from __future__ import annotations

from html import escape
from typing import Iterable, Optional

from sqlalchemy.orm import Session

CSS_VERSION = "20261120-explore-1"
STYLESHEET = f'<link rel="stylesheet" href="/static/explore.css?v={CSS_VERSION}">'

# Short labels for the corner of a drawn cover and the coloured format tags.
KIND_LABELS = {"movie": "Movie", "tv": "TV", "anime": "Anime", "game": "Game", "album": "Album", "book": "Book",
               "manga": "Manga", "podcast": "Podcast", "audiobook": "Audiobook"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def hue(name: str) -> int:
    """The same steady colour per name the title pages use (routers/titles._hue)."""
    return sum(ord(ch) * (index + 1) for index, ch in enumerate((name or "").casefold())) % 360


def cover(title: str, kind: str, image: Optional[str] = None, *, square: bool = False, label: bool = True,
          eager: bool = False, width: Optional[int] = None) -> str:
    """A poster box: the real art when there is some, otherwise the title drawn as a cover in the format's colour.

    width is the size the box is drawn at, in CSS pixels. At thumbnail sizes it goes on
    the <img> so image_sizes asks the CDN for a smaller copy.
    """
    shape = " x-art--square" if square else ""
    corner = f'<span class="x-cover__kind">{_e(KIND_LABELS.get(kind, ""))}</span>' if label else ""
    # The drawn cover sits under the art too: it shows while the image loads, and if the image never does.
    inner = f'<span class="x-cover" style="--cover-hue:{hue(title)}">{corner}<b>{_e(title)}</b></span>'
    if image:
        loading = "" if eager else ' loading="lazy"'
        size = f' width="{width}" height="{width if square else width * 3 // 2}"' if width else ""
        inner += f'<img src="{_e(image)}" alt=""{size}{loading} decoding="async">'
    return f'<span class="x-art{shape}" data-kind="{_e(kind)}" aria-hidden="true">{inner}</span>'


def kind_tag(kind: str, text: Optional[str] = None) -> str:
    """A format label with a dot in the format's colour."""
    return f'<span class="x-kind" data-kind="{_e(kind)}">{_e(text or KIND_LABELS.get(kind, kind))}</span>'


def dock(button_text: str = "Keep my list") -> str:
    """The bar that rises from the bottom once a visitor has saved a title on the page.

    guest-list.js shows it (data-guest-bar) and fills the count (data-guest-count). Its
    /#signup link opens the keep-your-list sheet, which html_finish switches on for any
    page with a data-guest-bar. site-nav.js hides data-guest-only for members.
    """
    return ('<div class="x-dock" data-guest-bar data-guest-only hidden role="region" aria-label="Your saved titles">'
            '<span class="x-dock__icon" aria-hidden="true"></span>'
            '<p class="x-dock__count" data-guest-count role="status" aria-live="polite"></p>'
            f'<a class="site-btn site-btn--primary site-btn--sm x-dock__go" href="/#signup">{_e(button_text)}</a></div>')


def cached_posters(db: Session, wanted: Iterable[tuple[str, str, Optional[int]]]) -> dict[tuple[str, str, Optional[int]], str]:
    """(title kind, title, year) -> poster from the shared title facts cache, in one query.

    Only what is already cached: these pages never wait on an outside lookup. A title
    whose facts are missing keeps its drawn cover until a title page or a shelf warms it.
    """
    import json

    from . import models, title_metadata, title_pages

    keys = {}
    for kind, title, year in wanted:
        keys[(kind, title, year)] = title_metadata.cache_key(kind, title_pages.normalize(title), year)
    if not keys:
        return {}
    rows = {row.key: row for row in db.query(models.TitleMetadata.key, models.TitleMetadata.data)
            .filter(models.TitleMetadata.key.in_(set(keys.values())), models.TitleMetadata.status == "ok")}
    found = {}
    for wanted_key, cache_key in keys.items():
        row = rows.get(cache_key)
        if row is None or not row.data:
            continue
        try:
            data = json.loads(row.data)
        except ValueError:
            continue
        poster = title_pages._safe_image(data.get("poster")) if isinstance(data, dict) else None
        if poster:
            found[wanted_key] = poster
    return found
