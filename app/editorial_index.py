"""Every written guide on the public site, in one list.

The Discover guides, monthly editions, "In order" and "If you liked" guides, the
seasonal hubs, the best-of-the-year lists and the release guides are the pages a
visitor can read in full without an account. They live in seven catalogs; this module gathers them so the
homepage (and anything else that wants "the latest reading") links to them without
knowing each catalog's shape.
"""
from __future__ import annotations

from datetime import date
from html import escape
from itertools import zip_longest

# The person who reviews every guide before it goes up. None keeps the bylines and the
# editorial standards page anonymous ("the site owner").
EDITOR_NAME = None


def editor_label() -> str:
    """How the editorial standards page names the reviewer, at the start of a sentence."""
    return f"{escape(EDITOR_NAME)}, who runs OmniTrackr," if EDITOR_NAME else "The site owner"


SECTION_LABELS = {
    "discover": "Discover guide",
    "monthly": "Monthly edition",
    "in-order": "In order",
    "if-you-liked": "If you liked",
    "seasonal": "Seasonal",
    "best-of": "Best of the year",
    "new-releases": "Release guide",
}


def _discover() -> list[dict]:
    from .discover_catalog import TRAILS
    from .discover_guides import GUIDES
    return [{"section": "discover", "href": f"/discover/{slug}", "name": TRAILS[slug]["name"],
             "summary": guide["summary"], "updated": guide["reviewed"]}
            for slug, guide in GUIDES.items() if slug in TRAILS]


def _monthly() -> list[dict]:
    from .discover_catalog import published_editions
    return [{"section": "monthly", "href": f"/discover/monthly/{slug}", "name": edition["name"],
             "summary": edition["intro"], "updated": edition.get("reviewed", edition["published_date"])}
            for slug, edition in published_editions().items()]


def _in_order() -> list[dict]:
    from . import in_order
    from .in_order_guides import GUIDES
    return [{"section": "in-order", "href": in_order.path(slug), "name": f"{guide['name']} in order",
             "summary": guide["summary"], "updated": guide["reviewed"]}
            for slug, guide in GUIDES.items()]


def _if_you_liked() -> list[dict]:
    from . import if_you_liked
    from .if_you_liked_guides import GUIDES
    return [{"section": "if-you-liked", "href": if_you_liked.path(slug),
             "name": f"If you liked {guide['anchor']['title']}", "summary": guide["summary"],
             "updated": guide["reviewed"]}
            for slug, guide in GUIDES.items()]


def _seasonal() -> list[dict]:
    from .seasonal_guides import SEASONS
    return [{"section": "seasonal", "href": entry["path"], "name": f"{entry['name']} picks",
             "summary": entry["summary"], "updated": entry["reviewed"]}
            for entry in SEASONS.values()] + [_gift_guide()] + _holiday_guides()


def _holiday_guides() -> list[dict]:
    from .holiday_guides import GUIDES
    return [{"section": "seasonal", "href": entry["path"], "name": entry["name"],
             "summary": entry["summary"], "updated": entry["reviewed"]}
            for entry in GUIDES.values()]


def _gift_guide() -> dict:
    from .gift_guides import GUIDE
    return {"section": "seasonal", "href": GUIDE["path"], "name": "Holiday gift guide",
            "summary": GUIDE["summary"], "updated": GUIDE["reviewed"]}


def _best_of() -> list[dict]:
    from . import best_of
    from .best_of_guides import GUIDES
    return [{"section": "best-of", "href": best_of.path(slug), "name": guide["name"],
             "summary": guide["summary"], "updated": guide["reviewed"]}
            for slug, guide in GUIDES.items()]


def _new_releases() -> list[dict]:
    from . import new_releases
    return [{"section": "new-releases", "href": new_releases.path(slug), "name": guide["name"],
             "summary": guide["summary"], "updated": guide["reviewed"]}
            for slug, guide in new_releases.published().items()]


def entries() -> list[dict]:
    """Every guide, newest first (ties keep catalog order)."""
    pieces = _discover() + _monthly() + _in_order() + _if_you_liked() + _seasonal() + _best_of() + _new_releases()
    return sorted(pieces, key=lambda piece: piece["updated"], reverse=True)


def latest(limit: int = 6) -> list[dict]:
    """The newest guides, taking turns between sections so one catalog cannot fill the list."""
    by_section: dict[str, list[dict]] = {}
    for piece in entries():
        by_section.setdefault(piece["section"], []).append(piece)
    # Sections with the most recent piece go first.
    ordered = sorted(by_section.values(), key=lambda pieces: pieces[0]["updated"], reverse=True)
    mixed = [piece for row in zip_longest(*ordered) for piece in row if piece]
    return mixed[:limit]


def _date_label(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return ""
    return f"{parsed:%B} {parsed.day}, {parsed.year}"


def homepage_section(limit: int = 6) -> str:
    """Server-rendered cards for the homepage; empty when there is nothing to show."""
    pieces = latest(limit)
    if not pieces:
        return ""
    cards = "".join(
        f'<li class="lp-reads__card lp-reads__card--{escape(piece["section"])}">'
        f'<a href="{escape(piece["href"], quote=True)}">'
        f'<span class="lp-reads__kind">{escape(SECTION_LABELS[piece["section"]])}</span>'
        f'<strong>{escape(piece["name"])}</strong>'
        f'<span class="lp-reads__summary">{escape(piece["summary"])}</span>'
        + (f'<span class="lp-reads__date">Updated <time datetime="{escape(piece["updated"])}">'
           f'{escape(_date_label(piece["updated"]))}</time></span>' if _date_label(piece["updated"]) else "")
        + '</a></li>'
        for piece in pieces
    )
    total = len(entries())
    return (
        '<section class="lp-section lp-section--tight lp-reads" aria-labelledby="reads-title">'
        '<div class="lp-wrap">'
        '<div class="lp-section-head lp-section-head--row"><div>'
        '<p class="lp-eyebrow">Read before you sign up</p>'
        '<h2 id="reads-title">New from the guides</h2>'
        f'<p>{total} free guides: the best order through long franchises, what to try after a favourite, '
        'and themed picks across every format. Each one is dated and says who each pick suits, with a fair caveat.</p>'
        '</div></div>'
        f'<ul class="lp-reads__grid">{cards}</ul>'
        '<p class="lp-reads__more"><a href="/in-order">Franchises in order</a>'
        '<a href="/if-you-liked">If you liked…</a><a href="/discover">Discover trails</a></p>'
        '</div></section>'
    )


SECTION_ORDER = (
    ("in-order", "Franchises in order", "/in-order"),
    ("if-you-liked", "If you liked…", "/if-you-liked"),
    ("discover", "Discover guides", "/discover"),
    ("monthly", "Monthly editions", "/discover"),
    ("seasonal", "Seasonal picks", "/halloween"),
    ("best-of", "Best of the year", "/best-of"),
    ("new-releases", "Release guides", "/new-releases"),
)


def directory_html() -> str:
    """Every guide, grouped by section, for the HTML site map."""
    pieces = entries()
    groups = []
    for section, heading, hub in SECTION_ORDER:
        links = sorted((piece for piece in pieces if piece["section"] == section), key=lambda piece: piece["name"])
        if not links:
            continue
        items = "".join(f'<li><a href="{escape(piece["href"], quote=True)}">{escape(piece["name"])}</a></li>'
                        for piece in links)
        groups.append(f'<div class="directory-group"><h3><a href="{escape(hub, quote=True)}">{escape(heading)}</a></h3>'
                      f'<ul>{items}</ul></div>')
    return "".join(groups)


def ledger_html() -> str:
    """Every guide with the date it was last checked, grouped by section, for the editorial standards page."""
    pieces = entries()
    groups = []
    for section, heading, hub in SECTION_ORDER:
        rows = sorted(sorted((piece for piece in pieces if piece["section"] == section), key=lambda piece: piece["name"]),
                      key=lambda piece: piece["updated"], reverse=True)
        if not rows:
            continue
        items = "".join(
            f'<li><a href="{escape(piece["href"], quote=True)}">{escape(piece["name"])}</a>'
            + (f' <span class="ledger-date">checked <time datetime="{escape(piece["updated"])}">'
               f'{escape(_date_label(piece["updated"]))}</time></span>' if _date_label(piece["updated"]) else "")
            + '</li>'
            for piece in rows
        )
        count = f'{len(rows)} guide{"s" if len(rows) != 1 else ""}'
        groups.append(f'<h3><a href="{escape(hub, quote=True)}">{escape(heading)}</a> <span class="ledger-count">{count}</span></h3>'
                      f'<ul class="guide-ledger">{items}</ul>')
    if not groups:
        return ""
    newest = max(piece["updated"] for piece in pieces)
    return (f'<p>There are {len(pieces)} guides on the site right now. The most recent check was on '
            f'<time datetime="{escape(newest)}">{escape(_date_label(newest))}</time>. Each date below is the last time '
            'that guide was reread and its facts checked, and it matches the "Updated" line on the guide itself.</p>'
            + "".join(groups))
