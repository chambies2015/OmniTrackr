"""The public record of corrections and updates (/corrections).

Two lists live here:

* ``guide_changes()``: changes to the written guides and the hubs after they went
  up. Each change names the pages it touched, with a line written for that page,
  so a guide can list its own history at the end (``add_change_notes``) and the
  /corrections page can list everything, newest first.
* ``POLICY_CHANGES``: changes to the policy and standards pages.

The log was started on November 22, 2026. The earlier entries were collected from
the site's version history for November; changes made before November 2026 were
not recorded one guide at a time and are not listed.

Add a change here whenever a guide's facts, recommendations or sections change.
Spelling fixes, layout and styling changes are not logged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from html import escape, unescape
from urllib.parse import urlsplit

STARTED = "2026-11-22"
EMAIL = "omnitrackr@gmail.com"

KINDS = {
    "correction": "Correction",  # something the page said was wrong
    "update": "Update",          # new information: nominees announced, a date that moved
    "added": "Added",            # a new section
    "edited": "Edited",          # wording a reader might notice, with the facts unchanged
}


@dataclass(frozen=True)
class Change:
    date: str
    kind: str
    label: str          # what changed, for the log ("24 In order guides")
    href: str           # where the log links the label
    summary: str        # one or two sentences for the log
    pages: tuple        # ((path, line for that page's own history), ...)


def _long_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{parsed:%B} {parsed.day}, {parsed.year}"


def _in_order_dates() -> Change:
    from . import in_order
    from .in_order_guides import GUIDES, NOVEMBER_GUIDES
    pages = tuple(
        (in_order.path(slug),
         "This guide said it was first published on October 17, 2026, the day the first ten In order guides "
         "went up. It went up on November 14, 2026, and now says so.")
        for slug in GUIDES if slug in NOVEMBER_GUIDES
    )
    return Change(
        "2026-11-22", "correction", f"{len(pages)} In order guides", in_order.BASE_PATH,
        f"The {len(pages)} franchise orders added on November 14, from the Marvel Cinematic Universe to the Cosmere, "
        "gave October 17, 2026 as their first published date, in the note at the end of each guide and in the "
        "page's data. That was the date of the first ten guides. They now say November 14.",
        pages,
    )


def _binge_sections() -> Change:
    from . import binge_calculator
    from .binge_guides import GUIDES
    # Dragon Ball Z and One Piece kept two sections; every other guide gained a third.
    pages = tuple(
        (binge_calculator.path(slug),
         f"Added the section “{guide['sections'][2][1]}”. The “How we counted” box now covers "
         "only what applies to this series and links to the full method on the calculator page.")
        for slug, guide in GUIDES.items() if len(guide["sections"]) > 2
    )
    return Change(
        "2026-11-20", "added", f"{len(pages)} “How long it takes” guides", binge_calculator.BASE_PATH,
        "Each gained a third section written for its series, such as where to take a break in Breaking Bad, the nine "
        "Thanksgiving episodes of Friends and the Machete order for the Star Wars films. The “How we counted” "
        "box lost a paragraph every guide repeated. Dragon Ball Z and One Piece keep two sections.",
        pages,
    )


def _binge_fourth_sections() -> Change:
    from . import binge_calculator
    from .binge_guides import GUIDES
    pages = tuple(
        (binge_calculator.path(slug), f"Added the section “{guide['sections'][3][1]}”.")
        for slug, guide in GUIDES.items() if len(guide["sections"]) > 3
    )
    return Change(
        "2026-11-23", "added", f"{len(pages)} “How long it takes” guides", binge_calculator.BASE_PATH,
        "The nine guides with the least writing of their own each gained a fourth section: who's who in the first "
        "episode of Succession, the crew's own sessions in Cowboy Bebop, what Death Note's makers did next, David "
        "Simon's other series after The Wire, the real events behind Mad Men, when each Stranger Things season is set, "
        "where to pause Attack on Titan, a podcast and a book to go with The Sopranos, and why Lost speeds up after "
        "season 3.",
        pages,
    )


def _awards_depth() -> tuple[Change, Change]:
    added = Change(
        "2026-11-23", "added", "Awards season pages", "/awards",
        "The Golden Globes and Oscars pages gained sections on how their voting works, written for the weeks before "
        "nominations: who votes for the Globes since 2023, how their categories split and what they say about the "
        "Oscars; and which films can compete for an Oscar, how the votes are counted and what the December shortlists "
        "mean. The Globes page now lists last year's main winners, and the calendar page has notes on picking well at "
        "each show.",
        (("/awards", "Added the section “Picking well at each show”."),
         ("/awards/golden-globes-2027",
          "Added “Who the voters are now”, “How the categories split” and “What the Globes say about the Oscars”, "
          "and listed last year's winners in the main film and TV categories, not just the podcast award."),
         ("/awards/oscars-2027",
          "Added “Which films can compete”, “How the votes are counted” and “What the December shortlists tell "
          "you”. The rules section now says the casting award can go to up to three people on a film."),),
    )
    fixed = Change(
        "2026-11-23", "correction", "Awards season calendar", "/awards",
        "The answer to “When can I fill in a ballot?” kept saying the Game Awards nominees “are revealed on "
        "November 17” after that day had passed. The answer now follows where each show actually is.",
        (("/awards", "The answer to “When can I fill in a ballot?” kept saying the Game Awards nominees “are "
                     "revealed on November 17” after that day had passed. It now follows where each show actually "
                     "is, and changes by itself as nominations come out."),),
    )
    return added, fixed


def _if_you_liked_decks() -> Change:
    from . import if_you_liked
    from .if_you_liked_guides import GUIDES
    pages = tuple(
        (if_you_liked.path(slug),
         "Rewrote the line under the title, which had followed the same pattern on every If you liked guide, and "
         f"renamed the heading “Three things {guide['anchor']['title']} does well” to "
         f"“What {guide['anchor']['title']} does well”. The picks didn't change.")
        for slug, guide in GUIDES.items()
    )
    return Change(
        "2026-11-20", "edited", f"{len(pages)} If you liked guides", if_you_liked.BASE_PATH,
        "The line under each title had been written to one pattern (“Seven picks for after X, from A and B to "
        "C”). Each now says what its guide is about in its own words. The picks didn't change.",
        pages,
    )


def _best_of_decks() -> Change:
    from . import best_of
    from .best_of_guides import GUIDES
    pages = tuple((best_of.path(slug), "Rewrote the line under the title, which had followed the same pattern on "
                   "every Best of 2026 list. The picks didn't change.") for slug in GUIDES)
    return Change(
        "2026-11-20", "edited", f"{len(pages)} Best of 2026 lists", best_of.BASE_PATH,
        "The same change as the If you liked guides: the line under each title now says what the list covers in its "
        "own words instead of following one pattern. The picks didn't change.",
        pages,
    )


def _hubs() -> Change:
    pages = (
        ("/if-you-liked", "Added “How a guide is put together” and a table of what each guide's picks follow."),
        ("/new-releases", "Added “How to read a release date” and “Day one, or wait?”."),
        ("/challenges", "Added “Make a challenge of your own”."),
        ("/browse", "Added a section for each shelf on choosing a first manga, podcast or audiobook."),
    )
    return Change(
        "2026-11-18", "added", "Four guide hubs", "/guides",
        "The If you liked, Release guides, Challenges and Browse pages had little writing of their own, mostly links "
        "and lists. Each gained sections written for it: how an If you liked guide is built, what a release date means "
        "in each format and when to wait for reviews, making your own challenge, and choosing a first manga, podcast "
        "or audiobook.",
        pages,
    )


def _grammys() -> tuple[Change, Change]:
    path = "/awards/grammys-2027"
    correction = Change(
        "2026-11-17", "correction", "Grammys 2027", path,
        "The eligibility window said August 30, 2025 to August 29, 2026. Grammy.com gives August 31, 2025 to "
        "August 28, 2026, and the page now does too.",
        ((path, "The eligibility window said August 30, 2025 to August 29, 2026. Grammy.com gives August 31, 2025 "
                "to August 28, 2026, and the page now does too."),),
    )
    update = Change(
        "2026-11-17", "update", "Grammys 2027", path,
        "Added the nominees announced on November 16 and opened the ballot: 13 categories, typed from Grammy.com and "
        "checked against ABC News, Audacy and Us Weekly.",
        ((path, "Added the nominees announced on November 16 and opened the ballot: 13 categories, typed from "
                "Grammy.com and checked against ABC News, Audacy and Us Weekly."),),
    )
    return correction, update


def _if_you_liked_questions() -> Change:
    from . import if_you_liked
    from .if_you_liked_guides import GUIDES
    pages = tuple((if_you_liked.path(slug), "Added the Questions section, with three questions and answers.")
                  for slug in GUIDES)
    return Change(
        "2026-11-04", "added", f"{len(pages)} If you liked guides", if_you_liked.BASE_PATH,
        "Each gained a Questions section with three questions and answers, 36 in all.",
        pages,
    )


def _edition_notes() -> Change:
    from .discover_catalog import MONTHLY_EDITIONS
    slugs = ("september-2026", "october-2026", "november-2026")
    pages = tuple((f"/discover/monthly/{slug}",
                   f"Added “{MONTHLY_EDITIONS[slug]['notes']['heading']}”, on how the picks pair up.")
                  for slug in slugs if slug in MONTHLY_EDITIONS)
    return Change(
        "2026-11-04", "added", "September, October and November 2026 Discover editions", "/discover",
        "Each edition gained a section on how its six picks fit together.",
        pages,
    )


@lru_cache(maxsize=1)
def _spring_tv_dates() -> Change:
    pages = (
        ("/new-releases/spring-2027",
         "Added Wild Things (April 16, Apple TV) to Also on the calendar, and links to the new spring games guide. "
         "The opening now says why there is no spring TV guide yet."),
        ("/new-releases/winter-2027-tv",
         "Added Invincible season 5 (February 17, Prime Video) to Also on the calendar. Prime Video set the date on "
         "November 19."),
    )
    return Change(
        "2026-11-22", "update", "Two release guides", "/new-releases",
        "Added two TV dates found while writing the spring 2027 games guide: Wild Things on April 16 to the spring "
        "guide, and Invincible season 5 on February 17 to the winter TV guide. No picks changed.",
        pages,
    )


def _switch_sections() -> Change:
    from .switch_guides import GUIDES, NOTES, path
    pages = tuple(
        (path(slug), "Added the sections " + " and ".join(f"“{note['heading']}”" for note in notes) + ".")
        for slug, notes in NOTES.items() if slug in GUIDES
    )
    return Change(
        "2026-11-22", "added", f"{len(pages)} switching guides", "/switch",
        "Each Switch from guide gained two sections written for that service, on how its ratings convert and on the "
        "parts of its export that change what arrives, such as Goodreads series names in titles, the Steam box that "
        "hides playtime, and how Trakt decides a show is finished. They were checked against the Import Studio code "
        "the same day.",
        pages,
    )


def _switch_fixes() -> Change:
    pages = (
        ("/switch/myanimelist",
         "This guide said the export only holds each series' total episode count. The export also records how many "
         "episodes or chapters you've got through; the import doesn't read that number yet, and the guide now says so."),
        ("/switch/goodreads",
         "The answer to “Will books I already added be duplicated?” said no. Goodreads puts the series in some "
         "titles, and those don't match a book you added under its plain title, so the answer now says that."),
    )
    return Change(
        "2026-11-22", "correction", "Two switching guides", "/switch",
        "The MyAnimeList guide said the export holds only each series' episode total, when it also records your own "
        "progress, which the import doesn't read yet. The Goodreads guide said books you already track are never "
        "duplicated, which isn't true of titles Goodreads writes with the series in brackets.",
        pages,
    )


def guide_changes() -> tuple[Change, ...]:
    """Every logged change to a guide or hub, newest first."""
    changes = [*_awards_depth(), _binge_fourth_sections(), _switch_fixes(), _switch_sections(), _in_order_dates(),
               _binge_sections(), _if_you_liked_decks(), _best_of_decks(), _hubs(), *_grammys(),
               _if_you_liked_questions(), _edition_notes(), _spring_tv_dates()]
    return tuple(sorted(changes, key=lambda change: change.date, reverse=True))


# Changes to the policy and standards pages, newest first. (date, page name, path, what changed)
POLICY_CHANGES = (
    ("2026-11-22", "Corrections and updates", "/corrections",
     "Started this log. A guide that has changed since it went up now lists the changes at the end of the page, and "
     "every guide shows when it was first published and last checked."),
    ("2026-11-22", "About", "/about",
     "Corrected the description of the Discover guides, which said each one connects a film, a show, a game, an album "
     "and a book. Each connects four titles in different formats. Added a short history of the site."),
    ("2026-11-20", "Terms", "/terms",
     "Added sections on clubs and discussions, imports and exports, Ko-fi memberships, ads and affiliate links, "
     "outside data sources and copyright complaints. None of them changed how the site works; they describe it."),
    ("2026-11-17", "Privacy policy", "/privacy",
     "Added the check-in email: one email to a member who saved titles and last visited between 9 and 29 days ago, "
     "asking whether they finished any of them."),
    ("2026-11-15", "Privacy policy", "/privacy",
     "Added two-step sign-in, passkeys, episode notes, award ballots, the advent calendar, gift lists, shared lists "
     "and clubs, saves kept only in your browser, Ko-fi and Amazon Associates."),
    ("2026-11-04", "Editorial standards", "/content-quality",
     "Added how each kind of guide is made, the list of every guide with the date it was last checked, and that "
     "drafts are written with AI writing tools before they are edited and checked."),
)


def changes_for(path: str) -> list[tuple[Change, str]]:
    """(change, line for this page), newest first, for one page."""
    path = path.rstrip("/") or "/"
    return [(change, line) for change in guide_changes() for page, line in change.pages if page == path]


def latest_date() -> str:
    dates = [change.date for change in guide_changes()] + [row[0] for row in POLICY_CHANGES]
    return max(dates)


def _kind_badge(kind: str) -> str:
    return f'<span class="fix-kind fix-kind--{kind}">{KINDS[kind]}</span>'


def _time(value: str) -> str:
    return f'<time datetime="{value}">{_long_date(value)}</time>'


def log_html() -> str:
    """The guide log for /corrections, grouped by day."""
    days: dict[str, list[Change]] = {}
    for change in guide_changes():
        days.setdefault(change.date, []).append(change)
    blocks = []
    for day, changes in days.items():
        items = []
        for change in changes:
            pages = ""
            if len(change.pages) > 1:
                links = "".join(f'<li><a href="{escape(page, quote=True)}">{escape(_page_name(page))}</a></li>'
                                for page, _ in change.pages)
                pages = (f'<details class="fix-pages"><summary>The {len(change.pages)} pages</summary>'
                         f'<ul>{links}</ul></details>')
            items.append(
                f'<li class="fix-entry">{_kind_badge(change.kind)} '
                f'<a class="fix-entry__what" href="{escape(change.href, quote=True)}">{escape(change.label)}</a>'
                f'<p>{escape(change.summary)}</p>{pages}</li>'
            )
        blocks.append(f'<h3 class="fix-day">{_time(day)}</h3><ul class="fix-log">{"".join(items)}</ul>')
    return "\n".join(blocks)


def policy_html() -> str:
    items = "".join(
        f'<li class="fix-entry"><span class="fix-entry__date">{_time(day)}</span> '
        f'<a class="fix-entry__what" href="{escape(path, quote=True)}">{escape(name)}</a><p>{escape(text)}</p></li>'
        for day, name, path, text in POLICY_CHANGES
    )
    return f'<ul class="fix-log fix-log--policies">{items}</ul>'


def _page_name(path: str) -> str:
    names = _guide_names()
    if path in names:
        return names[path]
    hubs = {"/if-you-liked": "If you liked", "/new-releases": "Release guides", "/challenges": "Monthly challenges",
            "/browse": "Browse shelves", "/switch": "Switching guide"}
    if path.startswith("/switch/"):
        from .switch_guides import GUIDES
        guide = GUIDES.get(path.removeprefix("/switch/"))
        if guide:
            return f"Switch from {guide['name']}"
    return hubs.get(path, path)


def _guide_names() -> dict[str, str]:
    # Monthly editions and release guides go live on their own dates, so the list is rebuilt
    # daily. Cached for good, a page that went live after the last restart got no note.
    return _guide_names_on(date.today().isoformat())


@lru_cache(maxsize=1)
def _guide_names_on(_day: str) -> dict[str, str]:
    from . import editorial_index
    return {piece["href"]: piece["name"] for piece in editorial_index.entries()}


# ---------------------------------------------------------------------------
# The note at the end of each guide (an html_finish step)

_CANONICAL = re.compile(r'<link rel="canonical" href="https://omnitrackr\.xyz([^"]*)"')
_ARTICLE_OPEN = re.compile(r'<article class="trail-guide[^"]*"[^>]*>')
_ARTICLE_TAG = re.compile(r"<(/?)article\b[^>]*>", re.I)
_SECTION_TAG = re.compile(r"<(/?)section\b[^>]*>", re.I)
_SOURCES_OPEN = re.compile(r'<section\b[^>]*class="[^"]*\b(?:guide-sources|aw-sources)\b[^"]*"[^>]*>')
_SAVE_PANEL = re.compile(r'<section id="save-picks"')
_PUBLISHED = re.compile(r'"datePublished":\s*"(\d{4}-\d{2}-\d{2})')
_MODIFIED = re.compile(r'"dateModified":\s*"(\d{4}-\d{2}-\d{2})')
MARKER = "data-guide-changes"


def _matching_close(html: str, start: int, pattern: re.Pattern) -> int:
    depth = 0
    for match in pattern.finditer(html, start):
        depth += -1 if match.group(1) else 1
        if depth == 0:
            return match.start()
    return -1


def note_html(path: str, published: str | None = None, modified: str | None = None) -> str:
    """The "Changes to this guide" note, or "" when there is nothing to add.

    Dates are shown only when given (pages that don't already say when they were
    first published); the change list only when the page has logged changes.
    """
    changes = changes_for(path)
    dates = ""
    if published:
        dates = f'<p class="guide-changes__dates">First published {_time(published)}'
        if modified and modified != published:
            dates += f'. Last checked {_time(modified)}'
        dates += ".</p>"
    if not changes and not dates:
        return ""
    listed = ""
    if changes:
        rows = "".join(f'<li>{_time(change.date)} {_kind_badge(change.kind)} {escape(line)}</li>'
                       for change, line in changes)
        listed = f'<ol class="guide-changes__list">{rows}</ol>'
    heading = "Changes to this guide" if changes else "About this guide"
    return (
        f'<div class="guide-changes" id="guide-changes" {MARKER}>'
        f'<h3>{heading}</h3>{dates}{listed}'
        '<p class="guide-changes__links"><a href="/corrections">Every correction and update</a> · '
        '<a href="/corrections#send">Send a correction</a></p></div>'
    )


def _insert_point(html: str, start: int, end: int) -> int:
    """Where the note goes between ``start`` and ``end``: the end of the last sources or
    method section, else just before the save panel, else ``end``."""
    last = None
    for match in _SOURCES_OPEN.finditer(html, start, end):
        last = match
    if last:
        close = _matching_close(html, last.start(), _SECTION_TAG)
        if 0 <= close <= end:
            return close
    panel = _SAVE_PANEL.search(html, start, end)
    return panel.start() if panel else end


def add_change_notes(html: str) -> str:
    if MARKER in html or ("trail-guide" not in html and "aw-sources" not in html):
        return html
    canonical = _CANONICAL.search(html)
    if not canonical:
        return html
    path = urlsplit(unescape(canonical.group(1))).path.rstrip("/") or "/"
    if path not in _guide_names():
        return html
    published = modified = None
    if "First published" not in html:
        found = _PUBLISHED.search(html)
        published = found.group(1) if found else None
        found = _MODIFIED.search(html)
        modified = found.group(1) if found else None
    note = note_html(path, published, modified)
    if not note:
        return html
    article = _ARTICLE_OPEN.search(html)
    if article:
        end = _matching_close(html, article.start(), _ARTICLE_TAG)
        if end < 0:
            return html
        point = _insert_point(html, article.end(), end)
    else:
        sources = None
        for match in _SOURCES_OPEN.finditer(html):
            sources = match
        if not sources:
            return html
        point = _matching_close(html, sources.start(), _SECTION_TAG)
        if point < 0:
            return html
    return html[:point] + note + html[point:]
