"""The /guides library: every written guide on the site, by format and by kind.

/guides used to be a how-to page for the tracker with a short list of help pages at
the bottom. The written guides (franchise orders, "how long does it take", If you
liked, the Essential 100, release guides, the holiday and awards pages...) were only
reachable from their own hubs, so nothing showed them as one body of work.

This module builds the library part of the page from ``editorial_index`` (so a new
guide shows up here the day it is published) plus the written pages outside that
catalog: switch guides, browse shelves, monthly challenges and the tracker help
pages. Each guide is tagged with the formats it covers, worked out from the titles
it writes about (``guide_links``), so the page can be filtered to one format with
``?format=films`` or, with JavaScript, without a reload.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from html import escape

from . import editorial_index

# (query value, kind key used by guide_links, chip label, singular, plural)
FORMATS = (
    ("films", "movie", "Films", "film", "films"),
    ("tv", "tv", "TV", "TV", "TV"),
    ("anime", "anime", "Anime", "anime", "anime"),
    ("games", "game", "Games", "game", "games"),
    ("books", "book", "Books", "book", "books"),
    ("music", "music", "Music", "music", "music"),
    ("manga", "manga", "Manga", "manga", "manga"),
    ("podcasts", "podcast", "Podcasts", "podcast", "podcasts"),
    ("audiobooks", "audiobook", "Audiobooks", "audiobook", "audiobooks"),
)
FORMAT_BY_SLUG = {row[0]: row[1] for row in FORMATS}
LABEL_BY_KIND = {row[1]: row[2] for row in FORMATS}
PLURAL_BY_KIND = {row[1]: row[4] for row in FORMATS}
ALL_KINDS = tuple(row[1] for row in FORMATS)
# guide_links counts "album" for music picks in the seasonal and best-of data.
_KIND_FIX = {"album": "music"}
LIBRARY_ANCHOR = "guide-library-heading"

# The awards pages list nominees, not titles with a kind, so their formats are set here.
_AWARDS_FORMATS = {
    "/awards": ("movie", "tv", "game", "music"),
    "/awards/the-game-awards-2026": ("game",),
    "/awards/grammys-2027": ("music",),
    "/awards/golden-globes-2027": ("movie", "tv"),
    "/awards/oscars-2027": ("movie",),
}
_SWITCH_FORMATS = {
    "letterboxd": ("movie",),
    "imdb": ("movie", "tv", "game"),
    "goodreads": ("book",),
    "storygraph": ("book",),
    "myanimelist": ("anime", "manga"),
    "anilist": ("anime", "manga"),
    "trakt": ("movie", "tv"),
    "steam": ("game",),
    "spotify": ("music", "podcast"),
    "podcast-apps": ("podcast",),
    "rate-your-music": ("music",),
    "libib": ("book", "movie", "music", "game"),
}
_TRACKER_PAGES = (
    ("movie_tracker.html", ("movie",)),
    ("tv_show_tracker.html", ("tv",)),
    ("anime_tracker.html", ("anime",)),
    ("game_tracker.html", ("game",)),
    ("book_tracker.html", ("book",)),
    ("music_tracker.html", ("music",)),
    ("manga_tracker.html", ("manga",)),
    ("podcast_tracker.html", ("podcast",)),
    ("audiobook_tracker.html", ("audiobook",)),
)
_SETUP_PAGES = ("media_tracking.html", "media_tracker_checklist.html", "tracking_templates.html",
                "export_import_guide.html", "media_statistics.html", "review_guidelines.html",
                "compare.html", "use_cases.html", "faq.html")


# Shelves, in the order the page shows them: (key, heading, intro, hubs).
# Intros describe how that kind of guide is made, so they stay true as guides are added.
SHELVES = (
    ("in-order", "Series in order",
     "Long series rarely arrive in the order you'd want to take them. Each of these lists every "
     "entry with its year, then gives two or more ways through, such as release order, story order "
     "or a shorter route, and says what each entry adds. When a series spreads across films, shows, "
     "books and games, the guide says which of them you need.",
     (("/in-order", "Every franchise in order"),)),
    ("binge", "How long it takes",
     "Each of these adds up one long series season by season, film by film or book by book, so you "
     "can check the total against the parts. Episode counts come from TVmaze and running times from "
     "each film's Wikipedia entry. Every guide says what the total leaves out and suggests a pace "
     "you could keep on ordinary evenings.",
     (("/binge-calculator", "Open the binge calculator"),)),
    ("if-you-liked", "If you liked…",
     "Start from one favourite. These guides say what made it work, then pick films, shows, games, "
     "books and albums that share one of those things. Each pick says what it has in common with "
     "the favourite and where it differs, so you can tell a near miss from a good fit.",
     (("/if-you-liked", "Every If you liked guide"),)),
    ("discover", "Discover trails",
     "Trails built around a mood or an idea, like found family or small adventures, with one pick "
     "each from four different formats. Each trail compares its picks by tone and intensity and "
     "explains what connects them.",
     (("/discover", "All Discover trails"),)),
    ("essentials", "The Essential 100",
     "Nine lists of one hundred all-time titles, one for each format, in date order. Every title "
     "has a few sentences on why it's there and a line on where to start, and you can tick off "
     "the ones you've already seen, played, read or heard.",
     (("/essentials", "All nine lists"),)),
    ("best-of", "Best of the year",
     "The standouts of 2026 in each format, with where each one came out, a few more worth a look "
     "and the releases still due before the year ends. Nothing here is ranked by chart position.",
     (("/best-of", "Every best-of list"),)),
    ("new-releases", "Release guides",
     "Previews of what's coming out in a month or a season. Most of these titles aren't out when "
     "the guide is written, so each pick says who should wait for reviews. Dates move, so these "
     "guides are rechecked more often than the rest.",
     (("/new-releases", "Every release guide"),)),
    ("seasonal", "Holidays and seasons",
     "Picks for a time of year. The Halloween, winter holiday and Valentine's pages put every pick on "
     "a scale so you can choose how far to go, from spooky-not-scary to lights-on-afterwards. The gift "
     "guide and the Black Friday guide are the only guides on this shelf with affiliate shop links, and "
     "both say so before the first one.",
     (("/holidays", "Holiday picks"), ("/halloween", "Halloween"))),
    ("awards", "Awards season",
     "Dates, how the winners are picked and how to watch the big ceremonies, with a ballot for "
     "your own picks once the official nominations are out. Nominees go up only after they are "
     "announced and checked against the official list.",
     (("/awards", "The awards calendar"),)),
    ("monthly", "Monthly editions and challenges",
     "Each monthly edition picks six works, one from each of six formats, around a single idea "
     "and adds a short essay on why they belong together. The monthly challenge sets a themed "
     "goal that resets on the first of the month.",
     (("/discover", "Editions on Discover"), ("/challenges", "This month's challenge"))),
    ("browse", "Shelves to start with",
     "Where to start with manga, podcasts and audiobooks, the three formats people most often "
     "ask about. Each page groups first picks into short shelves and adds a popularity chart "
     "that refreshes a few times a day.",
     (("/browse", "All shelves"),)),
    ("switch", "Switch from another tracker",
     "Where IMDb, Letterboxd, Goodreads, MyAnimeList, Spotify and the rest keep their exports, "
     "what comes across when you import, and what to check afterwards. Each one was checked "
     "against the importer it describes.",
     (("/switch", "The switching guide"),)),
    ("help", "Using the tracker",
     "How OmniTrackr handles each format and how to set up a library: what to record for a film "
     "and what for a podcast, how episode, page and chapter progress works, and how to choose "
     "ratings, reviews and privacy before your first week.",
     (("/media-tracking", "The tracking hub"), ("#choose-path-heading", "The how-to below"))),
)
SHELF_KEYS = tuple(key for key, *_ in SHELVES)


# Hand-picked first reads. Each line says why to start there, in words that stay true.
START_HERE = (
    ("/in-order/star-wars",
     "Three good ways through eleven films and three series, and a clear answer on what you can skip. "
     "It shows what every franchise order on the site does."),
    ("/binge-calculator/breaking-bad",
     "Sixty-two episodes added up season by season, where to take a break, and a pace that "
     "fits around work."),
    ("/if-you-liked/interstellar",
     "One film, and what to try next in five other formats, each with a note on what it shares "
     "with Interstellar and what it doesn't."),
    ("/in-order/discworld",
     "Forty-one novels, six routes in, and the three books we'd hand someone who has never read Pratchett."),
    ("/essentials/games",
     "A hundred games from Pong to Baldur's Gate 3, with the version to play today and how long each one takes."),
    ("/discover/found-family",
     "A film, a TV drama, an anime and an album compared side by side on one idea: people who choose each other."),
)


def _date_label(value: str, short: bool = False) -> str:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        return ""
    month = f"{parsed:%b}" if short else f"{parsed:%B}"
    return f"{month} {parsed.day}, {parsed.year}"


def _formats_for(entry: dict) -> tuple[str, ...]:
    """The formats one editorial guide covers.

    A guide about one format (an anime season guide) belongs to that format. A guide that
    mixes formats on purpose (Valentine's Day, a Discover trail) belongs to each of them.
    A franchise order mostly about films still counts for TV when it names two or more
    shows, but one tie-in series is not enough to list Fast & Furious under TV.
    """
    if entry["href"] in _AWARDS_FORMATS:
        return _AWARDS_FORMATS[entry["href"]]
    kinds: dict[str, int] = {}
    for kind, count in entry.get("kinds", {}).items():
        kind = _KIND_FIX.get(kind, kind)
        if kind in LABEL_BY_KIND:
            kinds[kind] = kinds.get(kind, 0) + count
    main = _KIND_FIX.get(entry.get("kind"), entry.get("kind"))
    if main:
        picked = {main} | {kind for kind, count in kinds.items() if count >= 2}
    else:
        picked = set(kinds)
    return tuple(kind for kind in ALL_KINDS if kind in picked)


def _shelf_for(entry: dict) -> str:
    if entry["section"] == "seasonal" and entry["href"].startswith("/awards"):
        return "awards"
    return entry["section"]


# The "how long" guides for book and film series name no titles with a kind, so their
# own "kind" field says what they count.
_BINGE_KINDS = {"tv": "tv", "anime": "anime", "book": "book", "film": "movie"}


def _editorial_rows() -> list[dict]:
    from . import binge_calculator, guide_links
    from .binge_guides import GUIDES as BINGE_GUIDES
    binge_kinds = {binge_calculator.path(slug): _BINGE_KINDS.get(guide.get("kind")) for slug, guide in BINGE_GUIDES.items()}
    index = guide_links._index()
    rows = []
    for entry in editorial_index.entries():
        indexed = index.get(entry["href"], entry)
        formats = _formats_for(indexed)
        main = _KIND_FIX.get(indexed.get("kind"), indexed.get("kind"))
        if entry["section"] == "binge" and binge_kinds.get(entry["href"]):
            main = main or binge_kinds[entry["href"]]
            # The book series guides also give the unabridged audiobook length.
            formats = formats or ((main, "audiobook") if main == "book" else (main,))
        if entry["href"] in _AWARDS_FORMATS and len(formats) == 1:
            main = formats[0]
        rows.append({"shelf": _shelf_for(entry), "href": entry["href"], "name": entry["name"],
                     "updated": entry["updated"], "formats": formats, "main": main, "note": ""})
    return rows


def _other_rows() -> list[dict]:
    """Written pages outside editorial_index: challenges, browse shelves, switch and help pages."""
    from . import browse, challenges, reader_pages, switch_guides
    rows = []
    for month in challenges.public_months():
        challenge = challenges.CHALLENGES[month]
        label = date.fromisoformat(f"{month}-01")
        rows.append({"shelf": "monthly", "href": f"/challenges/{challenges.slug_for(month)}",
                     "name": f"{label:%B} {label.year} challenge: {challenge['name']}",
                     "updated": challenge.get("published", ""), "formats": ALL_KINDS, "main": None, "note": ""})
    browse_kinds = {"manga": "manga", "podcasts": "podcast", "audiobooks": "audiobook"}
    for kind in browse.KINDS:
        rows.append({"shelf": "browse", "href": browse.path(kind), "name": f"{kind.capitalize()} worth starting",
                     "updated": "", "formats": (browse_kinds.get(kind, kind),), "main": browse_kinds.get(kind), "note": ""})
    for slug, guide in switch_guides.GUIDES.items():
        name = f"Switch from {guide['name']}" if guide["name"] != "your podcast app" else "Switch podcast apps"
        rows.append({"shelf": "switch", "href": switch_guides.path(slug), "name": name,
                     "updated": guide.get("reviewed", ""), "formats": _SWITCH_FORMATS.get(slug, ()),
                     "main": None, "note": ""})
    for template, kinds in _TRACKER_PAGES:
        page = reader_pages.PAGES[template]
        rows.append({"shelf": "help", "href": page.path, "name": page.name, "updated": "",
                     "formats": kinds, "main": kinds[0], "note": page.blurb})
    # Setup pages apply to every format alike, so they stay out of the format filters
    # instead of padding each format's count with the same nine pages.
    for template in _SETUP_PAGES:
        page = reader_pages.PAGES[template]
        rows.append({"shelf": "help", "href": page.path, "name": page.name, "updated": "",
                     "formats": (), "main": None, "note": page.blurb})
    return rows


@lru_cache(maxsize=1)
def _rows_for(_day: str) -> tuple[dict, ...]:
    return tuple(_editorial_rows() + _other_rows())


def rows() -> list[dict]:
    # Release guides and challenges go live on their dates, so the list is rebuilt daily.
    return [dict(row) for row in _rows_for(date.today().isoformat())]


def format_slug(value) -> str | None:
    """The ?format= value if it names one of the nine formats, else None."""
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value if value in FORMAT_BY_SLUG else None


def _format_names(kinds: tuple[str, ...]) -> str:
    if len(kinds) == len(ALL_KINDS):
        return "Every format"
    if len(kinds) > 4:
        return f"{len(kinds)} formats"
    return ", ".join(LABEL_BY_KIND[kind] for kind in kinds)


def _row_html(row: dict, hidden: bool) -> str:
    formats = " ".join(row["formats"])
    when = (f'<time datetime="{escape(row["updated"], quote=True)}">{escape(_date_label(row["updated"], short=True))}</time>'
            if _date_label(row["updated"]) else "")
    shows_formats = bool(row["formats"])
    meta = " · ".join(part for part in (escape(_format_names(row["formats"])) if shows_formats else "", when) if part)
    note = f'<span class="gl-row__note">{escape(row["note"])}</span>' if row["note"] else ""
    return (f'<li class="gl-row" data-formats="{escape(formats, quote=True)}" '
            f'data-name="{escape(row["name"].lower(), quote=True)}"{" hidden" if hidden else ""}>'
            f'<a href="{escape(row["href"], quote=True)}">{escape(row["name"])}</a>{note}'
            + (f'<span class="gl-row__meta">{meta}</span>' if meta else "") + "</li>")


def _shelf_sort(shelf: str, items: list[dict]) -> list[dict]:
    if shelf in ("in-order", "binge", "if-you-liked", "switch"):
        return sorted(items, key=lambda row: _sort_name(row["name"]))
    if shelf in ("essentials", "best-of", "help", "browse"):
        return items  # catalog order: one per format, in the site's usual format order
    return sorted(items, key=lambda row: row["updated"], reverse=True)


def _sort_name(name: str) -> str:
    """Sort by the series: "How long does it take to watch Breaking Bad?" files under B."""
    key = name.lower()
    for prefix in ("how long does it take to watch ", "how long does it take to read ", "if you liked ",
                   "switch from ", "every ", "all the ", "the "):
        key = key.removeprefix(prefix)
    for prefix in ("all the ", "every ", "the "):
        key = key.removeprefix(prefix)
    return key


def _hub_links(hubs) -> str:
    return " · ".join(f'<a href="{escape(href, quote=True)}">{escape(label)}</a>' for href, label in hubs)


def _shelf_html(key: str, heading: str, intro: str, hubs, items: list[dict], kind: str | None) -> str:
    shown = [row for row in items if kind is None or kind in row["formats"]]
    count = len(items)
    rows_html = "".join(_row_html(row, hidden=kind is not None and kind not in row["formats"])
                        for row in _shelf_sort(key, items))
    return (
        f'<section class="gl-shelf" id="shelf-{key}" data-gl-shelf aria-labelledby="shelf-{key}-title"'
        f'{" hidden" if not shown else ""}>'
        f'<div class="gl-shelf__head"><h3 id="shelf-{key}-title">{escape(heading)} '
        f'<span class="gl-shelf__count" data-gl-shelf-count>{len(shown) if kind else count}</span></h3>'
        f'<p class="gl-shelf__hubs">{_hub_links(hubs)}</p></div>'
        f'<p class="gl-shelf__intro">{escape(intro)}</p>'
        f'<ul class="gl-rows">{rows_html}</ul></section>'
    )


def _chips(counts: dict[str, int], total: int, current: str | None) -> str:
    def chip(slug: str | None, label: str, count: int, kind: str) -> str:
        href = f"/guides?format={slug}#{LIBRARY_ANCHOR}" if slug else f"/guides#{LIBRARY_ANCHOR}"
        active = (slug or None) == current
        plural = PLURAL_BY_KIND.get(kind, "")
        return (f'<a class="gl-chip" href="{href}" data-format="{kind}" data-slug="{slug or ""}" '
                f'data-plural="{escape(plural, quote=True)}"{" aria-current=\"true\"" if active else ""}>'
                f'{escape(label)} <span>{count}</span></a>')
    chips = [chip(None, "All", total, "")]
    chips += [chip(row[0], row[2], counts.get(row[1], 0), row[1]) for row in FORMATS]
    return "".join(chips)


def _count_line(shown: int, total: int, kind: str | None) -> str:
    if kind is None:
        return f"Showing all {total} guides."
    return f"Showing {shown} of {total} guides that cover {PLURAL_BY_KIND[kind]}."


def library_html(format_value=None) -> str:
    """The filter bar and every shelf. ``format_value`` is the raw ?format= value."""
    current = format_slug(format_value)
    kind = FORMAT_BY_SLUG.get(current) if current else None
    all_rows = rows()
    total = len(all_rows)
    counts = {key: sum(1 for row in all_rows if key in row["formats"]) for key in ALL_KINDS}
    shown = counts.get(kind, total) if kind else total
    shelves = "".join(
        _shelf_html(key, heading, intro, hubs, [row for row in all_rows if row["shelf"] == key], kind)
        for key, heading, intro, hubs in SHELVES
        if any(row["shelf"] == key for row in all_rows)
    )
    return (
        '<div class="gl-tools" data-gl-tools>'
        f'<nav class="gl-chips" aria-label="Show the guides for one format">{_chips(counts, total, current)}</nav>'
        '<div class="gl-find" data-gl-find hidden><label for="gl-search">Find a guide by name</label>'
        '<input id="gl-search" type="search" autocomplete="off" spellcheck="false" '
        'placeholder="Try Zelda, Christmas or anime" data-gl-search></div>'
        f'<p class="gl-count" data-gl-count aria-live="polite" data-total="{total}">{escape(_count_line(shown, total, kind))}</p>'
        '</div>'
        f'<div class="gl-shelves">{shelves}</div>'
        '<p class="gl-empty" data-gl-empty hidden>No guide has that in its name. Try a series, a '
        'format or a time of year, or <a href="/site-map">look through the site map</a>.</p>'
    )


# One paragraph per format, written for the page. Counts and links are worked out below it.
FORMAT_NOTES = {
    "movie": "Watch orders for the big film series, from Star Wars and the Marvel films to James Bond "
             "and The Conjuring, the hours the longest ones take, a hundred films worth knowing, and "
             "the new releases worth planning an evening around.",
    "tv": "How many hours a show takes from the pilot to the finale, with where to take a break, plus "
          "a hundred shows worth knowing, the best of 2026 and the premieres coming this winter.",
    "anime": "Watch orders for series that branch into films and spin-offs, like Monogatari, Fate and "
             "Dragon Ball, how long the long runs take, and a guide to each new anime season.",
    "game": "Play orders for Zelda, Kingdom Hearts, Metal Gear and Resident Evil, a hundred games with "
            "the version to play today, the year's best and a ballot for The Game Awards.",
    "book": "Reading orders for Discworld, the Cosmere, Narnia and The Witcher, how many hours a long "
            "series takes to read, and the new novels worth reading each season.",
    "music": "A hundred albums worth knowing with where to start on each, the best albums of 2026, a "
             "Grammys ballot, and albums picked to sit beside films and books in the mixed guides.",
    "manga": "A hundred manga worth knowing, the best new series of 2026, a shelf of first picks sorted "
             "by how long a run you want, and the manga behind the anime watch orders.",
    "podcast": "A hundred podcasts worth knowing, the best new shows of 2026, and a shelf of first picks "
               "for anyone who has never found a show that stuck.",
    "audiobook": "A hundred audiobooks worth knowing, each with its narrator and length, the best of 2026, "
                 "a shelf of first listens, and how many hours the long book series take.",
}
# Which guides lead each format desk: a format's own list in these sections, in this order.
_DESK_ORDER = ("essentials", "best-of", "new-releases", "in-order", "binge", "if-you-liked", "browse", "awards")
DESK_LINKS = 4


def formats_html() -> str:
    """Nine format desks: a note, the count, the guides about only that format and a filter link."""
    all_rows = rows()
    desks = []
    for slug, kind, label, word, _ in FORMATS:
        covering = [row for row in all_rows if kind in row["formats"]]
        own = [row for row in covering if row["main"] == kind and row["shelf"] in _DESK_ORDER]
        own.sort(key=lambda row: (_DESK_ORDER.index(row["shelf"]), row["updated"] and -date.fromisoformat(row["updated"]).toordinal()))
        picked, per_shelf = [], {}
        for row in own:
            if per_shelf.get(row["shelf"], 0) >= 1:
                continue
            per_shelf[row["shelf"]] = 1
            picked.append(row)
            if len(picked) >= DESK_LINKS:
                break
        links = "".join(f'<li><a href="{escape(row["href"], quote=True)}">{escape(row["name"])}</a></li>' for row in picked)
        desks.append(
            f'<article class="gl-desk" id="format-{slug}">'
            f'<h3>{escape(label)} <span>{len(covering)} guides</span></h3>'
            f'<p>{escape(FORMAT_NOTES[kind])}</p>'
            f'<ul>{links}</ul>'
            f'<a class="gl-desk__all" href="/guides?format={slug}#{LIBRARY_ANCHOR}" data-format="{kind}">'
            f'Every {escape(word)} guide</a></article>'
        )
    return f'<div class="gl-desks">{"".join(desks)}</div>'


def start_here_html() -> str:
    by_href = {row["href"]: row for row in _editorial_rows()}
    cards = []
    for href, why in START_HERE:
        row = by_href.get(href)
        if not row:
            continue
        label = editorial_index.SECTION_LABELS.get(row["shelf"], "Guide")
        cards.append(
            f'<a class="gl-pick" href="{escape(href, quote=True)}"><span class="gl-pick__kind">{escape(label)}</span>'
            f'<strong>{escape(row["name"])}</strong><span class="gl-pick__why">{escape(why)}</span></a>'
        )
    return f'<div class="gl-picks">{"".join(cards)}</div>'


def recent_html(limit: int = 8) -> str:
    items = []
    for piece in editorial_index.latest(limit):
        when = _date_label(piece["updated"])
        items.append(
            f'<li><time datetime="{escape(piece["updated"], quote=True)}">{escape(when)}</time>'
            f'<a href="{escape(piece["href"], quote=True)}">{escape(piece["name"])}</a>'
            f'<span>{escape(editorial_index.SECTION_LABELS[piece["section"]])}</span></li>'
        )
    return f'<ol class="gl-recent">{"".join(items)}</ol>'


def newest_check() -> str:
    pieces = editorial_index.entries()
    return max(piece["updated"] for piece in pieces) if pieces else date.today().isoformat()


def stats_html() -> str:
    pieces = editorial_index.entries()
    total = len(rows())
    newest = newest_check()
    return (f'<p class="gl-stats"><span><strong>{len(pieces)}</strong> dated reading guides</span>'
            f'<span><strong>{total - len(pieces)}</strong> how-to and switching guides</span>'
            f'<span>Last check <time datetime="{escape(newest, quote=True)}">{escape(_date_label(newest))}</time></span></p>')


def replacements(format_value=None) -> dict[str, str]:
    """Markers in guides.html and what fills them."""
    reading = len(editorial_index.entries())
    return {
        "<!--GUIDE_COUNT-->": str(reading),
        "<!--GUIDE_STATS-->": stats_html(),
        "<!--GUIDE_START_HERE-->": start_here_html(),
        "<!--GUIDE_RECENT-->": recent_html(),
        "<!--GUIDE_FORMATS-->": formats_html(),
        "<!--GUIDE_LIBRARY-->": library_html(format_value),
        "2099-01-01": newest_check(),  # dateModified placeholder in the page's JSON-LD
    }


def rail_html(path: str) -> str:
    """"In the library" links for the rail beside one guide: its shelf, its format, the whole library."""
    every = rows()
    row = next((item for item in every if item["href"] == path), None)
    if row is None:
        return ""
    shelf = next((entry for entry in SHELVES if entry[0] == row["shelf"]), None)
    links = []
    if shelf:
        size = sum(1 for item in every if item["shelf"] == row["shelf"])
        hub_href = shelf[2][0][0]
        links.append(f'<li><a href="{escape(hub_href, quote=True)}">{escape(shelf[1])}</a> <span>{size}</span></li>')
    if row["main"] in LABEL_BY_KIND:
        slug = next(item[0] for item in FORMATS if item[1] == row["main"])
        singular = next(item[3] for item in FORMATS if item[1] == row["main"])
        size = sum(1 for item in every if row["main"] in item["formats"])
        links.append(f'<li><a href="/guides?format={slug}#{LIBRARY_ANCHOR}">Every {escape(singular)} guide</a> <span>{size}</span></li>')
    links.append(f'<li><a href="/guides">The whole library</a> <span>{len(every)}</span></li>')
    return (f'<nav class="guide-rail__library" aria-label="In the library"><p class="guide-rail__label">In the library</p>'
            f'<ul>{"".join(links)}</ul></nav>')
