"""Where Pick swap (/swap) and Watch together (/together) get pointed out (Nov 2026).

Both live behind the Community menu, so most people never find them. This module holds
the few places that mention them, so the copy and the dates stay in one file:

* a "with your people" section on the holiday guides and the gift guide,
* the Pick swap chip on the home holiday card while swaps are in season,
* a holiday line at the top of the guest homepage, also only in season,
* one idea at a time in the Friends column of the member home's What's new card.

Nothing here writes to the database; the home idea reads two counts.
"""
from __future__ import annotations

from datetime import date
from html import escape
from typing import Optional

from sqlalchemy.orm import Session

# A holiday swap needs a draw day and a few days to pick, so the season stops before Christmas week.
SWAP_SEASON = ((11, 15), (12, 22))

SWAP_CHIP = {"path": "/swap", "name": "Pick swap",
             "tagline": "Secret Santa with recommendations: draw names, pick one title each, unwrap together."}


def swap_season(today: Optional[date] = None) -> bool:
    today = today or date.today()
    (start_month, start_day), (end_month, end_day) = SWAP_SEASON
    return date(today.year, start_month, start_day) <= today <= date(today.year, end_month, end_day)


def _e(value) -> str:
    return escape(str(value), quote=True)


SWAP = "swap"
TOGETHER = "together"

# Per page: heading, a line under it, then the tools in the order shown with this page's text for each.
CALLOUTS = {
    "holidays": {
        "heading": "Do the holidays with your people",
        "intro": "The picks above are for you. These two are for the group chat, and both start from one link.",
        "tools": [
            (SWAP, "Secret Santa where the gift is a recommendation. Everyone draws a name, picks one film, show, "
                   "book, game or album for that person with a line on why, and you all unwrap on the same morning."),
            (TOGETHER, "Starting a series over the break? Agree on a few episodes a week and keep going after "
                       "everyone's gone home. Everyone sees where the others are, and notes stay hidden until you "
                       "reach them."),
        ],
    },
    "christmas": {
        "heading": "Give each other something to watch",
        "intro": "Two ways to share the season with people who aren't on the couch with you.",
        "tools": [
            (SWAP, "Draw names in the family group chat and give one recommendation each: a film, a show, a book, "
                   "a game or an album, with a note on why. Make Christmas morning the unwrap day and nobody finds "
                   "out who had whom until then."),
            (TOGETHER, "Choose the show you'll all start the day after Christmas, set two episodes a week, and keep "
                       "going into January from wherever you live. Notes about an episode stay locked until you've "
                       "seen it."),
        ],
    },
    "thanksgiving": {
        "heading": "Drawing names at Thanksgiving?",
        "intro": "If your family does Secret Santa, Thanksgiving is often when the names come out of the hat. "
                 "Both of these can be set up before everyone heads home.",
        "tools": [
            (SWAP, "Run the draw on OmniTrackr and make the gift a recommendation. Everyone picks one title for the "
                   "person they drew, and you choose the unwrap day. Christmas morning works."),
            (TOGETHER, "Found a show the cousins all want to start? Agree on a pace, two episodes a week say, and "
                       "watch from separate couches. One track shows where everyone is."),
        ],
    },
    "reading-and-listening": {
        "heading": "Read it with someone",
        "intro": "A long book or a podcast back catalog is easier to finish when somebody else is on the same "
                 "chapter.",
        "tools": [
            (TOGETHER, "Watch together works for books, audiobooks, manga and podcasts. Choose one, agree on a few "
                       "chapters or episodes a week, and leave notes at the part they're about. Nobody sees a note "
                       "until they get there."),
            (SWAP, "Or run a short book swap: everyone draws a name and picks a book under 300 pages for that "
                   "person, and you all open them on the same day."),
        ],
    },
    "gifts": {
        "heading": "Or give a recommendation",
        "intro": "For the friends you don't buy for, or a group with a spending limit of zero.",
        "tools": [
            (SWAP, "A pick swap is Secret Santa where the gift is one thing to watch, read, play or listen to. "
                   "Everyone draws a name, wraps a pick with a line on why, and you unwrap on the day you choose. "
                   "It costs nothing."),
        ],
    },
}

# Lines that tie a tool to Christmas morning or the week after. From the day after each date until
# Dec 31 the plain text below replaces them; the rest of the year the Christmas plan still holds.
LATE_DECEMBER = {
    ("christmas", SWAP): (22, "Draw names in the family group chat and give one recommendation each: a film, a show, "
                              "a book, a game or an album, with a note on why. Nobody finds out who had whom until "
                              "unwrap day."),
    ("christmas", TOGETHER): (26, "Choose a show you'll all start before New Year's, set two episodes a week, and keep "
                                  "going into January from wherever you live. Notes about an episode stay locked "
                                  "until you've seen it."),
    ("thanksgiving", SWAP): (22, "Run the draw on OmniTrackr and make the gift a recommendation. Everyone picks one "
                                 "title for the person they drew, and you choose the unwrap day."),
}


def _text(page: str, tool: str, text: str, today: date) -> str:
    late = LATE_DECEMBER.get((page, tool))
    if late and today.month == 12 and today.day > late[0]:
        return late[1]
    return text


TOOLS = {
    SWAP: {"name": "Pick swap", "kicker": "Secret Santa", "path": "/swap",
           "guest": "See how a swap works", "member": "Start a pick swap"},
    TOGETHER: {"name": "Watch together", "kicker": "Same pace", "path": "/together",
               "guest": "See how it works", "member": "Plan one"},
}


def _art(tool: str) -> str:
    if tool == SWAP:
        boxes = "".join(f'<span class="ft-box ft-box--{n}"><i></i><b>{_e(name)}</b></span>'
                        for n, name in enumerate(("For Sam", "For Jo", "For you"), 1))
        return f'<div class="ft-art ft-art--swap" aria-hidden="true">{boxes}</div>'
    dots = "".join(f'<span class="ft-track__face ft-track__face--{n}">{_e(letter)}</span>'
                   for n, letter in enumerate(("J", "M", "You"), 1))
    return ('<div class="ft-art ft-art--together" aria-hidden="true"><p class="ft-track__label">Week 3 of 8</p>'
            f'<div class="ft-track"><i></i>{dots}</div><p class="ft-track__note">2 notes waiting at episode 6</p></div>')


def callout_html(page: str, signed_in: bool, today: Optional[date] = None) -> str:
    """The "with your people" section for a guide page; empty for a page without one."""
    entry = CALLOUTS.get(page)
    if not entry:
        return ""
    today = today or date.today()
    cards = []
    for tool, text in entry["tools"]:
        text = _text(page, tool, text, today)
        info = TOOLS[tool]
        href = info["path"] + ("#start" if signed_in else "")
        label = info["member"] if signed_in else info["guest"]
        cards.append(
            f'<article class="ft-card ft-card--{tool}">{_art(tool)}<div class="ft-card__copy">'
            f'<p class="ft-card__kicker">{_e(info["kicker"])}</p><h3>{_e(info["name"])}</h3><p>{_e(text)}</p>'
            f'<a class="ft-card__link" href="{_e(href)}" data-friend-tool="{tool}">{_e(label)}</a></div></article>')
    single = " ft-callout--one" if len(cards) == 1 else ""
    return (f'<section class="ft-callout{single}" id="with-friends" aria-labelledby="ft-heading">'
            '<p class="eyebrow">WITH YOUR PEOPLE</p>'
            f'<h2 id="ft-heading">{_e(entry["heading"])}</h2><p class="ft-callout__intro">{_e(entry["intro"])}</p>'
            f'<div class="ft-callout__grid">{"".join(cards)}</div></section>')


def season_card_links(slug: str, today: Optional[date] = None) -> list[dict]:
    """Extra chips for the home holiday card: Pick swap while a holiday swap still has time to run."""
    if slug == "holidays" and swap_season(today):
        return [dict(SWAP_CHIP)]
    return []


def hero_link_html(today: Optional[date] = None) -> str:
    """The Pick swap pill for the guest homepage's news line, only while swaps are in season."""
    if not swap_season(today):
        return ""
    return ('<a href="/swap" data-home-tool="swap"><span class="lp-hero__news-tag">New</span>'
            '<span>Pick swap, a Secret Santa for recommendations</span>'
            '<svg class="lp-icon" aria-hidden="true"><use href="#i-arrow"/></svg></a>')


def hero_line_html(today: Optional[date] = None) -> str:
    """The guest homepage's one-line holiday note above the headline, only while swaps are in season."""
    link = hero_link_html(today)
    return f'<p class="lp-hero__news">{link}</p>' if link else ""


def home_idea(db: Session, user_id: int, today: Optional[date] = None) -> Optional[dict]:
    """One idea for the Friends column of What's new, or None.

    In season, members who aren't in a swap get Pick swap. Otherwise, members with a friend
    and no running plan get Watch together. The key changes each year, so hiding the swap
    line one December doesn't hide it the next.
    """
    from . import pick_swap, together
    today = today or date.today()
    if swap_season(today):
        if pick_swap.active_count(db, user_id):
            return None
        return {"key": f"swap-{today.year}", "tool": SWAP, "title": "Holiday pick swap",
                "text": "Draw names with friends or family, pick one title each, and unwrap together on the day "
                        "you choose.",
                "path": "/swap#start", "label": "Start a swap"}
    if together.active_count(db, user_id):
        return None
    return {"key": "together", "tool": TOGETHER, "title": "Watch together",
            "text": "Starting something a friend wants to see too? Set a few episodes or chapters a week and see "
                    "where each other are.",
            "path": "/together#start", "label": "Plan one"}
