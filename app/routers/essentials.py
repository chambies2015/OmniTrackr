"""The Essential 100 (/essentials and /essentials/<format>): a canon page per format, 100 titles each.

Every page reads in full without scripts or an account. Visitors can tick off what
they have finished; the ticks stay in their browser (essentials.js) and move into a
new library after sign-up through POST /api/essentials/import. "Want to" uses the
site-wide guest list. Members save straight to their library through
POST /api/essentials/save, and their counts ("37 of 100 films") come from what the
library already holds, so nothing new is stored.

A count can be shared as /essentials/<format>/score/<n> (or /essentials/score/<a-b-c...>
for all nine lists): a small noindex page with its own share card. The number is in
the URL and nothing else about the person is.
"""
from __future__ import annotations

import io
import re
from datetime import date
from functools import lru_cache
from html import escape
from typing import Literal, Optional
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import essentials, explore_art, funnel, title_pages, title_search
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..library_lifecycle import delete_owned_media
from ..progress import lock_progress_owner
from .discover import page
from .if_you_liked import GUEST_LIST_JS

router = APIRouter(tags=["essentials"])
CSS_VERSION = "20261121-phone-1"
# Both the phone pass (Titles only) and the Nov 21 sweep changed essentials.js.
JS_VERSION = "20261121-phone-2"
IMPORT_JS = "/static/essentials-import.js?v=20261121-essentials-sweep-1"
SITE = "https://omnitrackr.xyz"
PUBLISHED = "2026-11-21"
HUB_TITLE = "The Essential 100: the films, shows, games, books and albums worth knowing"
HUB_DESCRIPTION = ("Nine hand-written lists of 100 essential titles each: films, TV, anime, games, books, albums, manga, "
                   "podcasts and audiobooks, with why each one matters and where to start.")
FORMAT_KINDS = {"movies": "movie", "tv": "tv", "anime": "anime", "games": "game", "books": "book", "music": "album",
                "manga": "manga", "podcasts": "podcast", "audiobooks": "audiobook"}
HUB_FAQ = (
    ("What is the Essential 100?",
     "Nine lists, one for each format OmniTrackr tracks, with 100 titles on each. They are the films, shows, anime, "
     "games, books, albums, manga, podcasts and audiobooks we would point a curious friend to first, with a short note "
     "on why each one is there and practical advice on where to start."),
    ("Is it a ranking?",
     "No. Each list runs in date order inside a few sections, so you can see how a format changed over time. Ten titles "
     "on every list are marked as the place to start if you have not tried much of that format yet."),
    ("Do I need an account to use the checklists?",
     "No. Tick what you have finished and the count is kept in your browser. If you make a free account, the titles you "
     "ticked move into your library, and the lists then count from your library on any device."),
    ("How often do the lists change?",
     "Rarely, and only by swapping a title out for a stronger one. Each list has a date at the top saying when it was "
     "last checked, and a section on what nearly made it."),
)


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _hours_label(hours: float) -> str:
    hours = round(hours)
    if hours >= 48:
        return f"about {hours:,} hours"
    return f"about {hours} hours"


def _year_text(item: dict) -> str:
    return item.get("dated") or (str(item["year"]) if item.get("year") else "")


def _meta_line(item: dict) -> str:
    parts = [item.get("creator"), item.get("origin"), item.get("length")]
    extra = item.get("extra") or {}
    if item["kind"] == "audiobook" and extra.get("narrator"):
        parts.insert(1, f"read by {extra['narrator']}")
    return " · ".join(part for part in parts if part)


def _details(db: Session) -> dict:
    try:
        return essentials.title_details(title_search.index(db))
    except Exception:
        return {}


def _art(db: Session, items: list[dict], details: dict) -> dict:
    """{item id: image} from title pages members track, then the shared title facts cache."""
    images = {item_id: detail["image"] for item_id, detail in details.items() if title_pages._safe_image(detail.get("image"))}
    missing = [item for item in items if item["id"] not in images]
    if missing:
        images.update(essentials.posters(db, missing))
    return images


def _states(db: Session, user, items: list[dict]) -> Optional[dict]:
    if user is None:
        return None
    try:
        return essentials.library_states(db, user.id, items)
    except Exception:
        db.rollback()
        return None


def _cover(item: dict, images: dict, width: int = 96, eager: bool = False) -> str:
    return explore_art.cover(item["title"], item["kind"], title_pages._safe_image(images.get(item["id"])),
                             square=item["kind"] in ("album", "podcast", "audiobook"), width=width, eager=eager)


# ---------------------------------------------------------------- one list

def _format_nav(current: Optional[str]) -> str:
    links = []
    for fmt in essentials.available():
        label = _e(essentials.FORMAT_LABELS[fmt])
        kind = FORMAT_KINDS[fmt]
        if fmt == current:
            links.append(f'<span aria-current="page" data-kind="{kind}">{label}</span>')
        else:
            links.append(f'<a href="{_e(essentials.path(fmt))}" data-kind="{kind}">{label}</a>')
    return (f'<nav class="es-formats" aria-label="The Essential 100 by format">'
            f'<a class="es-formats__label" href="{essentials.BASE_PATH}">The Essential 100:</a>'
            f'<div class="es-formats__list">{"".join(links)}</div></nav>')


def _actions(data: dict, item: dict, signed_in: bool, state: Optional[dict], detail: dict) -> str:
    fmt = data["format"]
    done_label = essentials.done_label(fmt)
    page_link = (f'<a class="es-link" href="{_e(detail["url"])}">Title page</a>' if detail.get("url") else "")
    if signed_in:
        if state and state["state"] == "done":
            return (f'<span class="es-have es-have--done">{_e(data["done_word"].capitalize())} ✓</span>'
                    f'<a class="es-link" href="{_e(state["library_url"])}">In your library</a>{page_link}')
        if state:
            return ('<span class="es-have">In your library</span>'
                    f'<a class="es-link" href="{_e(state["library_url"])}">Open it to mark it finished</a>{page_link}')
        return (f'<button type="button" class="es-btn es-btn--seen" data-es-save="seen">{_e(done_label)}</button>'
                '<button type="button" class="es-btn" data-es-save="want">Want to</button>' + page_link)
    return (f'<button type="button" class="es-btn es-btn--seen" data-es-tick aria-pressed="false">'
            f'<span class="es-when-off">{_e(done_label)}</span><span class="es-when-on">{_e(data["done_word"].capitalize())} ✓</span></button>'
            f'<button type="button" class="es-btn" aria-pressed="false" data-guest-kind="{_e(item["kind"])}" '
            f'data-guest-slug="{_e(item["slug"])}" data-guest-title="{_e(item["title"])}">'
            '<span class="es-when-off">Want to</span><span class="es-when-on">On your list ✓</span></button>' + page_link)


def _item_html(data: dict, item: dict, signed_in: bool, states: Optional[dict], details: dict, images: dict) -> str:
    state = (states or {}).get(item["id"])
    detail = details.get(item["id"], {})
    starter = ' data-es-starter="1"' if item.get("starter") else ""
    state_attr = f' data-es-state="{_e(state["state"])}"' if state else ""
    tag = '<span class="es-item__tag">Start here</span>' if item.get("starter") else ""
    year = _year_text(item)
    return (
        f'<li class="es-item" id="{_e(item["anchor"])}" data-es-id="{_e(item["id"])}" data-kind="{_e(item["kind"])}"{starter}{state_attr}>'
        f'<div class="es-item__art">{_cover(item, images)}</div>'
        f'<div class="es-item__body"><div class="es-item__head"><p class="es-item__num"><span>{item["number"]:02d}</span>{tag}</p>'
        f'<h3><span class="es-item__title">{_e(item["title"])}</span>'
        + (f' <span class="es-item__year">{_e(year)}</span>' if year else "") + '</h3>'
        f'<p class="es-item__meta">{_e(_meta_line(item))}</p></div>'
        f'<p class="es-item__why">{_e(item["why"])}</p>'
        f'<p class="es-item__start"><strong>Where to start:</strong> {_e(item["start"])}</p>'
        f'<div class="es-item__actions">{_actions(data, item, signed_in, state, detail)}</div>'
        '<p class="es-item__status" data-es-status role="status" aria-live="polite"></p></div></li>'
    )


def _signup_back(fmt: str) -> str:
    """Sign-up that comes back to this list's count (auth.js allows the path), where the ticks move in."""
    return "/?next=" + quote(f"{essentials.path(fmt)}#your-count", safe="") + "#signup"


def _tracker(data: dict, signed_in: bool, states: Optional[dict]) -> str:
    fmt = data["format"]
    count = essentials.progress(states, fmt) if states is not None else {"done": 0, "tracked": 0, "total": len(data["items"])}
    done, total = count["done"], count["total"]
    noun, word = data["noun"], data["done_word"]
    if signed_in and states is not None:
        line = f"You have {word} {done} of these {total} {noun}."
        if count["tracked"]:
            line += f" {count['tracked']} more {'is' if count['tracked'] == 1 else 'are'} in your library, not finished yet."
        note = "Counted from your library. Tick more as you go."
    else:
        line = f"How many of these {total} {noun} have you {word}?"
        note = "Tick each one as you go. Your count stays in this browser until you make a free account."
    width = round(100 * done / total) if total else 0
    member = "1" if signed_in else "0"
    share = f"{essentials.path(fmt)}/score/{done}"
    return (
        f'<aside class="es-tracker" id="your-count" data-es-tracker data-es-format="{_e(fmt)}" data-es-member="{member}" '
        f'data-es-total="{total}" data-es-done="{done}" data-es-noun="{_e(noun)}" data-es-word="{_e(word)}" '
        f'aria-label="Your count">'
        f'<p class="es-tracker__count" aria-hidden="true"><strong data-es-count>{done}</strong><span>/{total}</span></p>'
        f'<div class="es-tracker__text"><p class="es-tracker__line" data-es-line>{_e(line)}</p>'
        f'<span class="es-tracker__bar" aria-hidden="true"><span data-es-bar style="width:{width}%"></span></span>'
        f'<p class="es-tracker__note">{_e(note)}</p></div>'
        '<div class="es-tracker__actions">'
        '<div class="es-filter" role="group" aria-label="Show" data-es-filters hidden>'
        f'<button type="button" aria-pressed="true" data-es-filter="all">All {total}</button>'
        f'<button type="button" aria-pressed="false" data-es-filter="todo">Not {_e(word)} yet</button>'
        '<button type="button" aria-pressed="false" data-es-filter="starter">Start here</button></div>'
        # Hides the notes so the list reads as a checklist; essentials.js shows it and remembers the choice.
        '<button type="button" class="es-view" aria-pressed="false" data-es-view hidden>Titles only</button>'
        f'<a class="es-share" href="{_e(share)}" data-es-share{"" if signed_in else " hidden"}>Share my count</a>'
        + ('' if signed_in else f'<a class="es-save-count" href="{_e(_signup_back(fmt))}" data-es-signup hidden>Keep my count, free</a>')
        + '</div></aside>'
    )


def _starter_strip(data: dict, images: dict) -> str:
    tiles = []
    for item in essentials.starters(data["format"]):
        tiles.append(f'<li><a href="#{_e(item["anchor"])}" data-kind="{_e(item["kind"])}">{_cover(item, images, width=88)}'
                     f'<span class="es-start__title">{_e(item["title"])}</span>'
                     f'<span class="es-start__year">{_e(_year_text(item))}</span></a></li>')
    return (f'<section class="es-start" id="start-here" aria-labelledby="start-here-heading">'
            f'<p class="eyebrow">NEW TO {_e(essentials.FORMAT_LABELS[data["format"]].upper())}?</p>'
            f'<h2 id="start-here-heading">Ten to start with</h2>'
            f'<p>If you have {_e(data["done_word"])} few of these, begin here. They are marked "Start here" in the list below.</p>'
            f'<ol class="es-start__row">{"".join(tiles)}</ol></section>')


def _source_link(label: str, url: str) -> str:
    host = urlsplit(url).hostname or ""
    return (f'<li><a href="{_e(url)}" rel="noopener" target="_blank">{_e(label)}</a>'
            f' <span class="muted">({_e(host.removeprefix("www."))})</span></li>')


def _faq_html(faq) -> str:
    answers = "".join(f'<h3>{_e(question)}</h3><p>{_e(answer)}</p>' for question, answer in faq)
    return (f'<section id="questions" class="editorial es-faq" aria-labelledby="questions-heading">'
            f'<h2 id="questions-heading">Questions</h2>{answers}</section>')


def list_content(data: dict, details: dict, images: dict, signed_in: bool, states: Optional[dict]) -> str:
    fmt = data["format"]
    reviewed = data["reviewed"]
    jump = ['<a href="#start-here">Start here</a>']
    jump += [f'<a href="#{_e(section["key"])}">{_e(section["heading"])}</a>' for section in data["sections"]]
    jump += ['<a href="#where-to-start">Where to begin</a>', '<a href="#left-out">Nearly made it</a>',
             '<a href="#questions">Questions</a>', '<a href="#method">How we chose</a>']
    hours = essentials.total_hours(fmt)
    facts = [f'<span><strong>{len(data["items"])}</strong> {_e(data["noun"])}</span>',
             f'<span><strong>{len(data["sections"])}</strong> sections</span>']
    if hours:
        facts.append(f'<span>{_e(_hours_label(hours).capitalize())} in all</span>')
    parts = [
        f'<article class="trail-guide es-guide" data-es-format="{_e(fmt)}" data-kind="{_e(data["kind"])}">',
        f'<header class="hero hero--guide es-hero"><a href="{essentials.BASE_PATH}">← All nine lists</a>',
        f'<p class="eyebrow">THE ESSENTIAL 100 · {_e(essentials.FORMAT_LABELS[fmt].upper())}</p>',
        f'<h1>{_e(data["name"])}</h1><p class="guide-deck">{_e(data["deck"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time></p>',
        f'<p class="es-hero__facts">{"".join(facts)}</p>',
        f'<nav class="guide-jump" aria-label="On this page">{"".join(jump)}</nav></header>',
        _format_nav(fmt),
        f'<div class="guide-intro">{_paragraphs(data["lead"])}</div>',
        _tracker(data, signed_in, states),
        _starter_strip(data, images),
    ]
    for section in data["sections"]:
        first = section["items"][0]["number"]
        items = "".join(_item_html(data, item, signed_in, states, details, images) for item in section["items"])
        parts.append(
            f'<section class="es-section" id="{_e(section["key"])}" aria-labelledby="{_e(section["key"])}-heading">'
            f'<p class="eyebrow">{first:02d} to {section["items"][-1]["number"]:02d}</p>'
            f'<h2 id="{_e(section["key"])}-heading">{_e(section["heading"])}</h2>'
            f'<p class="es-section__intro">{_e(section["intro"])}</p>'
            f'<ol class="es-list" start="{first}">{items}</ol></section>')
    if not signed_in:
        parts.append(explore_art.dock("Keep my list"))
    parts.append('<section id="where-to-start" class="editorial es-begin" aria-labelledby="begin-heading">'
                 f'<h2 id="begin-heading">Where to begin</h2>{_paragraphs(data["start"])}</section>')
    near = "".join(f'<li><strong>{_e(title)}</strong> {_e(text)}</li>' for title, text in data["left_out"])
    parts.append('<section id="left-out" class="editorial es-near" aria-labelledby="left-out-heading">'
                 f'<h2 id="left-out-heading">Nearly made it</h2><ul>{near}</ul></section>')
    parts.append(_faq_html(data["faq"]))
    others = [other for other in essentials.available() if other != fmt]
    position = essentials.FORMATS.index(fmt)
    others.sort(key=lambda other: abs(essentials.FORMATS.index(other) - position))
    related = "".join(
        f'<article><h3><a href="{_e(essentials.path(other))}">{_e(essentials.get(other)["name"])}</a></h3>'
        f'<p>{_e(essentials.get(other)["summary"])}</p></article>' for other in others[:4])
    parts.append('<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE LISTS</p>'
                 f'<h2 id="related-heading">The other essential lists</h2><div class="guide-related-grid">{related}</div></section>')
    sources = "".join(_source_link(label, url) for label, url in data["sources"])
    parts.append(
        '<section id="method" class="guide-sources es-method" aria-labelledby="method-heading">'
        f'<h2 id="method-heading">How we chose</h2><p>{_e(data["method"])}</p>'
        '<p>Nothing on this list is sponsored, and nobody paid to be included. Lengths are rounded and vary by edition, cut '
        'or version. Links go to OmniTrackr title pages, not shops.</p>'
        f'<h3>Lists and references we checked against</h3><ul class="es-sources">{sources}</ul>'
        f'<p class="muted">First published {_e(_long_date(data.get("published") or PUBLISHED))}. Checked {_e(_long_date(reviewed))}. '
        '<a href="/contact">Suggest a title or send a correction</a> · <a href="/content-quality">Editorial standards</a></p>'
        '</section></article>')
    return "".join(parts)


def _list_structured(data: dict) -> list:
    url = SITE + essentials.path(data["format"])
    article = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": data["name"], "description": data["summary"],
        "datePublished": data.get("published") or PUBLISHED, "dateModified": data["reviewed"],
        "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
        "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(data["items"]), "itemListOrder": "https://schema.org/ItemListUnordered",
                       "itemListElement": [{"@type": "ListItem", "position": item["number"], "name": item["title"],
                                            "url": f'{url}#{item["anchor"]}'} for item in data["items"]]},
    }
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
        for question, answer in data["faq"]]}
    return [article, faq]


# ---------------------------------------------------------------- the hub

def _format_card(fmt: str, images: dict, states: Optional[dict]) -> str:
    data = essentials.get(fmt)
    picks = essentials.starters(fmt)[:3]
    art = "".join(_cover(item, images, width=64) for item in picks)
    mine = ""
    if states is not None:
        count = essentials.progress(states, fmt)
        width = round(100 * count["done"] / count["total"]) if count["total"] else 0
        mine = (f'<span class="es-card__mine"><span class="es-card__bar" aria-hidden="true"><span style="width:{width}%"></span></span>'
                f'{count["done"]} of {count["total"]} {_e(data["done_word"])}</span>')
    names = ", ".join(item["title"] for item in picks)
    hours = essentials.total_hours(fmt)
    time_line = f" · {_hours_label(hours)}" if hours else ""
    return (f'<li><a class="es-card" href="{_e(essentials.path(fmt))}" data-kind="{_e(data["kind"])}">'
            f'<span class="es-card__art">{art}</span>'
            f'<span class="es-card__text"><span class="x-kind">{_e(essentials.FORMAT_LABELS[fmt])}</span>'
            f'<strong>{_e(data["name"])}</strong>'
            f'<span class="es-card__line">Start with {_e(names)}</span>'
            f'<span class="es-card__facts">{len(data["items"])} {_e(data["noun"])}{_e(time_line)}</span>{mine}</span></a></li>')


def _scorecard(states: Optional[dict], signed_in: bool) -> str:
    formats = essentials.available()
    total = sum(len(essentials.get(fmt)["items"]) for fmt in formats)
    if not signed_in:
        return ('<aside class="es-score es-score--guest" aria-labelledby="es-score-heading"><div>'
                f'<p class="eyebrow">YOUR COUNT</p><h2 id="es-score-heading">How many of the {total} have you finished?</h2>'
                '<p>Every list is a checklist. Tick what you have seen, played, read or heard, and the page keeps count. '
                'A free account keeps the count on every device and adds the titles to your library.</p></div>'
                f'<a class="site-btn site-btn--primary" href="{_e(essentials.path(formats[0]))}#your-count">Start with films →</a></aside>'
                if formats else "")
    if states is None:
        return ""
    rows, counts = [], []
    for fmt in formats:
        count = essentials.progress(states, fmt)
        counts.append(count["done"])
        width = round(100 * count["done"] / count["total"]) if count["total"] else 0
        rows.append(f'<li data-kind="{_e(FORMAT_KINDS[fmt])}"><a href="{_e(essentials.path(fmt))}">{_e(essentials.FORMAT_LABELS[fmt])}</a>'
                    f'<span class="es-score__bar" aria-hidden="true"><span style="width:{width}%"></span></span>'
                    f'<span class="es-score__n">{count["done"]}/{count["total"]}</span></li>')
    done = sum(counts)
    if done == 0:
        lead = "None of the 900 are marked finished in your library yet. Open a list and tick what you have already done."
    else:
        best = max(formats, key=lambda fmt: essentials.progress(states, fmt)["done"])
        best_data = essentials.get(best)
        lead = (f"You have finished {done} of the {total}. You are furthest along on {best_data['name'][0].lower()}"
                f"{best_data['name'][1:]}, with {essentials.progress(states, best)['done']} {best_data['done_word']}.")
    share = f"{essentials.BASE_PATH}/score/{'-'.join(str(n) for n in counts)}" if len(formats) == len(essentials.FORMATS) else ""
    share_link = f'<p><a class="es-share" href="{_e(share)}">Share my count</a></p>' if share else ""
    return ('<aside class="es-score" aria-labelledby="es-score-heading"><div>'
            f'<p class="eyebrow">YOUR COUNT</p><h2 id="es-score-heading">{done} of {total} finished</h2>'
            f'<p>{_e(lead)}</p>{share_link}</div><ul class="es-score__formats">{"".join(rows)}</ul></aside>')


HUB_INTRO = (
    "Every format has a short list of titles that people who love it keep coming back to: the ones that other work "
    "borrows from, that critics and fans still argue about, and that hold up when you finally get to them. The Essential "
    "100 is our attempt at that list for each of the nine formats OmniTrackr tracks.",
    "Each list has exactly 100 titles, in date order, in a handful of sections. Every title gets a few sentences on what "
    "it is and why it made the list, and a line of practical advice: which cut or translation to choose, where a long "
    "series gets good, or what to try once you have finished it. Ten on each list are marked as the place to start.",
    "The lists are also checklists. Tick what you have finished and the page keeps count, so you can see which of the "
    "100 you still have ahead of you.",
)


def hub_content(images: dict, signed_in: bool, states: Optional[dict]) -> str:
    formats = essentials.available()
    total = sum(len(essentials.get(fmt)["items"]) for fmt in formats)
    reviewed = max((essentials.get(fmt)["reviewed"] for fmt in formats), default=PUBLISHED)
    cards = "".join(_format_card(fmt, images, states) for fmt in formats)
    firsts = []
    for fmt in formats:
        item = essentials.starters(fmt)[0]
        firsts.append(f'<li data-kind="{_e(item["kind"])}"><a href="{_e(essentials.anchor_url(item))}">'
                      f'{_cover(item, images, width=72)}<span class="x-kind">{_e(essentials.FORMAT_LABELS[fmt])}</span>'
                      f'<strong>{_e(item["title"])}</strong><span>{_e(_year_text(item))}</span></a></li>')
    hero = (
        '<header class="hero hero--guide es-hero es-hero--hub">'
        '<p class="eyebrow">THE ESSENTIAL 100 · NINE FORMATS</p>'
        '<h1>The Essential 100</h1>'
        '<p class="guide-deck">One hundred films, shows, anime, games, books, albums, manga, podcasts and audiobooks worth '
        'knowing, with why each one matters and where to start.</p>'
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated '
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time></p>'
        f'<p class="es-hero__facts"><span><strong>{total}</strong> titles</span><span><strong>{len(formats)}</strong> lists</span></p>'
        '<nav class="guide-jump" aria-label="On this page"><a href="#the-lists">The nine lists</a>'
        '<a href="#one-of-each">One of each</a><a href="#how-the-lists-work">How the lists work</a>'
        '<a href="#questions">Questions</a></nav></header>'
    )
    return (
        '<article class="trail-guide es-hub">' + hero
        + f'<div class="guide-intro">{_paragraphs(HUB_INTRO)}</div>'
        + _scorecard(states, signed_in)
        + f'<section class="es-cards" id="the-lists" aria-labelledby="lists-heading"><p class="eyebrow">THE LISTS</p>'
          f'<h2 id="lists-heading">Nine lists, 100 titles each</h2><ul class="es-cards__grid">{cards}</ul></section>'
        + '<section class="es-firsts" id="one-of-each" aria-labelledby="firsts-heading"><p class="eyebrow">ONE OF EACH</p>'
          '<h2 id="firsts-heading">If you only try one from each list</h2>'
          '<p>The first "Start here" title on every list. Together they make a decent month.</p>'
          f'<ol class="es-firsts__row">{"".join(firsts)}</ol></section>'
        + '<section class="editorial" id="how-the-lists-work" aria-labelledby="how-heading"><h2 id="how-heading">How the lists work</h2>'
          '<p>We started each list from the canon lists that critics, historians and fans have already argued over, such as '
          'the Sight and Sound poll for films, Rolling Stone\'s 500 albums and the major prizes for books and manga, then '
          'checked our picks against what people still watch, play and read now. A title made the cut when it is good in '
          'its own right and you can see its effect on what came after. We kept each list spread across decades, countries '
          'and genres, and limited how many entries one creator could take, so no single studio or author fills a list.</p>'
          '<p>Every list ends with the references it was checked against and a short section on the titles that nearly made '
          'it. Lengths are rounded, and the "where to start" notes stick to editions, cuts and translations rather than '
          'where something is streaming this month, because that changes too often to keep right.</p>'
          '<p>For newer titles, see <a href="/best-of">the best of 2026</a>. For what to try after one you loved, the '
          '<a href="/if-you-liked">If you liked</a> guides go one title at a time, and <a href="/in-order">In order</a> '
          'sorts out long franchises.</p></section>'
        + _faq_html(HUB_FAQ)
        + '</article>'
    )


def _hub_structured() -> list:
    collection = {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": HUB_TITLE, "description": HUB_DESCRIPTION,
        "url": SITE + essentials.BASE_PATH, "inLanguage": "en-US",
        "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": SITE + "/"},
        "mainEntity": {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": index, "name": essentials.get(fmt)["name"], "url": SITE + essentials.path(fmt)}
            for index, fmt in enumerate(essentials.available(), 1)]},
    }
    faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
        for question, answer in HUB_FAQ]}
    return [collection, faq]


def _head(signed_in: bool, ads: bool = True) -> str:
    head = f'<link rel="stylesheet" href="/static/essentials.css?v={CSS_VERSION}">'
    if signed_in:
        # Titles ticked before signing up move into the library from here too.
        head += f'<script src="{IMPORT_JS}" defer></script>'
    else:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
    head += f'<script src="/static/essentials.js?v={JS_VERSION}" defer></script>'
    if ads and not signed_in:
        head += '<script src="/static/ad-loader.js" defer></script>'
    return head


def _cache_headers(response: Response, signed_in: bool) -> None:
    # A member's page carries their own library counts, so the browser shouldn't keep it.
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=600"
    response.headers["Vary"] = "Cookie"


def _structured_payload(blocks: list):
    """discover.page takes one JSON-LD object; several go in an @graph."""
    return {"@context": "https://schema.org", "@graph": [{k: v for k, v in block.items() if k != "@context"} for block in blocks]}


@router.get(essentials.BASE_PATH, include_in_schema=False)
def essentials_hub(user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    if not essentials.available():
        raise HTTPException(404, "Not found")
    signed_in = user is not None
    items = [item for fmt in essentials.available() for item in essentials.starters(fmt)]
    details = _details(db)
    images = _art(db, items, details)
    states = _states(db, user, list(essentials.all_items()))
    content = hub_content(images, signed_in, states)
    response = page(HUB_TITLE, HUB_DESCRIPTION, essentials.BASE_PATH, content,
                    structured_data=_structured_payload(_hub_structured()), head=_head(signed_in, ads=False), member=signed_in,
                    body_class="es-page")
    _cache_headers(response, signed_in)
    return response


@router.get(essentials.BASE_PATH + "/{fmt}", include_in_schema=False)
def essentials_list(fmt: str, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    data = essentials.get(fmt)
    if data is None:
        raise HTTPException(404, "List not found")
    signed_in = user is not None
    details = _details(db)
    images = _art(db, data["items"], details)
    states = _states(db, user, data["items"])
    content = list_content(data, details, images, signed_in, states)
    response = page(data["search_title"], data["summary"], essentials.path(fmt), content,
                    structured_data=_structured_payload(_list_structured(data)), head=_head(signed_in), member=signed_in,
                    body_class="es-page")
    _cache_headers(response, signed_in)
    return response


# ---------------------------------------------------------------- shared counts

# Plain ASCII digits without leading zeros, so each count has one address ("\d" would take "٥" or "007").
_COUNT = r"(?:0|[1-9][0-9]{0,2})"
_ALL_PATTERN = re.compile(rf"^{_COUNT}(?:-{_COUNT}){{8}}$")
_ONE_PATTERN = re.compile(rf"^{_COUNT}$")


def _parse_one(fmt: str, done: str) -> Optional[tuple[dict, int]]:
    data = essentials.get(fmt)
    if data is None or not _ONE_PATTERN.match(done or "") or int(done) > len(data["items"]):
        return None
    return data, int(done)


def _parse_all(counts: str) -> Optional[list[int]]:
    if not _ALL_PATTERN.match(counts or "") or len(essentials.available()) != len(essentials.FORMATS):
        return None
    values = [int(part) for part in counts.split("-")]
    if any(value > len(essentials.get(fmt)["items"]) for value, fmt in zip(values, essentials.FORMATS)):
        return None
    return values


def _score_page(heading: str, lead: str, path: str, card: str, cta_href: str, cta_label: str, body: str, signed_in: bool):
    content = (
        '<article class="es-shared">'
        f'<header class="hero es-shared__hero"><p class="eyebrow">THE ESSENTIAL 100</p><h1>{_e(heading)}</h1>'
        f'<p class="guide-deck">{_e(lead)}</p>'
        f'<img class="es-shared__card" src="{_e(card)}" alt="" width="1200" height="630" decoding="async">'
        f'<p class="es-shared__actions"><a class="site-btn site-btn--primary" href="{_e(cta_href)}">{_e(cta_label)}</a>'
        f'<button type="button" class="site-btn site-btn--ghost" data-es-share-page hidden>Share</button></p></header>'
        f'{body}</article>'
    )
    response = page(f"{heading} · The Essential 100", lead, path, content, indexable=False,
                    head=f'<link rel="stylesheet" href="/static/essentials.css?v={CSS_VERSION}">'
                         f'<script src="/static/essentials.js?v={JS_VERSION}" defer></script>',
                    member=signed_in, share_image=SITE + card, body_class="es-page")
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=3600"
    response.headers["Vary"] = "Cookie"
    return response


@router.get(essentials.BASE_PATH + "/score/{counts}", include_in_schema=False)
def essentials_all_score(counts: str, request: Request, user=Depends(get_optional_current_user)):
    values = _parse_all(counts)
    if values is None:
        raise HTTPException(404, "Not found")
    if user is None:
        funnel.record("essentials_count_opened", request)
    done, total = sum(values), sum(len(essentials.get(fmt)["items"]) for fmt in essentials.FORMATS)
    rows = "".join(
        f'<li data-kind="{_e(FORMAT_KINDS[fmt])}"><a href="{_e(essentials.path(fmt))}">{_e(essentials.FORMAT_LABELS[fmt])}</a>'
        f'<span class="es-score__bar" aria-hidden="true"><span style="width:{round(100 * value / len(essentials.get(fmt)["items"]))}%"></span></span>'
        f'<span class="es-score__n">{value}/{len(essentials.get(fmt)["items"])}</span></li>'
        for fmt, value in zip(essentials.FORMATS, values))
    body = (f'<section class="es-score"><div><h2>{done} of {total}, list by list</h2>'
            '<p>Each list is 100 titles in date order, with why each one matters and where to start.</p></div>'
            f'<ul class="es-score__formats">{rows}</ul></section>')
    return _score_page(f"{done} of the essential {total}",
                       f"Someone has finished {done} of the {total} titles on OmniTrackr's nine Essential 100 lists. How many have you?",
                       f"{essentials.BASE_PATH}/score/{counts}", f"{essentials.BASE_PATH}/score/{counts}/card.png",
                       essentials.BASE_PATH, "Count yours", body, user is not None)


@router.get(essentials.BASE_PATH + "/{fmt}/score/{done}", include_in_schema=False)
def essentials_score(fmt: str, done: str, request: Request, user=Depends(get_optional_current_user)):
    parsed = _parse_one(fmt, done)
    if parsed is None:
        raise HTTPException(404, "Not found")
    data, done = parsed
    if user is None:
        funnel.record("essentials_count_opened", request)
    total = len(data["items"])
    starters = "".join(f'<li><a href="{_e(essentials.anchor_url(item))}">{_e(item["title"])}</a> '
                       f'<span class="muted">{_e(_year_text(item))}</span></li>' for item in essentials.starters(fmt))
    body = (f'<section class="editorial"><h2>{_e(data["name"])}</h2><p>{_e(data["summary"])}</p>'
            f'<h3>Ten to start with</h3><ul class="es-shared__starters">{starters}</ul></section>')
    heading = f"{done} of the essential {total} {data['noun']}"
    return _score_page(heading,
                       f"Someone has {data['done_word']} {done} of OmniTrackr's essential 100 {data['noun']}. How many have you?",
                       f"{essentials.path(fmt)}/score/{done}", f"{essentials.path(fmt)}/score/{done}/card.png",
                       f"{essentials.path(fmt)}#your-count", "Count yours", body, user is not None)


ACCENTS = {"movie": (244, 114, 182), "tv": (96, 165, 250), "anime": (248, 113, 113), "game": (52, 211, 153),
           "album": (167, 139, 250), "book": (251, 191, 36), "manga": (251, 146, 60), "podcast": (45, 212, 191),
           "audiobook": (232, 121, 249)}


@lru_cache(maxsize=256)
def render_card(fmt: str, counts: tuple) -> bytes:
    """The 1200x630 share card: the count, and a 10x10 grid (one list) or nine bars (all of them)."""
    from PIL import Image, ImageDraw
    from .profiles import _fit, _font

    width, height = 1200, 630
    accent = ACCENTS[FORMAT_KINDS[fmt]] if fmt != "all" else (139, 92, 246)
    base = Image.new("RGB", (width, height), (11, 10, 24))
    glow = Image.new("RGB", (width, height), (11, 10, 24))
    glow_draw = ImageDraw.Draw(glow)
    for step in range(18, 0, -1):
        radius, mix = step * 34, (1 - step / 18) * 0.5
        shade = tuple(int(base_value + (accent_value - base_value) * mix) for base_value, accent_value in zip((11, 10, 24), accent))
        glow_draw.ellipse((-140 - radius, height + 60 - radius, -140 + radius, height + 60 + radius), fill=shade)
    image = Image.blend(base, glow, 0.8)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, outline=(60, 52, 110), width=2)
    draw.text((84, 80), "OmniTrackr · The Essential 100", font=_font(30, bold=True), fill=(94, 234, 212))
    if fmt == "all":
        done, total = sum(counts), sum(len(essentials.get(key)["items"]) for key in essentials.FORMATS)
        label = "titles finished"
    else:
        data = essentials.get(fmt)
        done, total = counts[0], len(data["items"])
        label = f"{data['noun']} {data['done_word']}"
    big = _font(150, bold=True)
    draw.text((80, 150), str(done), font=big, fill=(245, 243, 255))
    number_width = draw.textlength(str(done), font=big)
    draw.text((92 + number_width, 236), f"/{total}", font=_font(60, bold=True), fill=(167, 160, 199))
    draw.text((84, 340), _fit(draw, label, _font(44, bold=True), 520), font=_font(44, bold=True), fill=accent)
    draw.text((84, 410), _fit(draw, "How many have you?", _font(32), 520), font=_font(32), fill=(214, 211, 235))
    host = SITE.replace("https://", "")
    draw.text((84, height - 108), f"{host}/essentials", font=_font(26), fill=(167, 160, 199))
    if fmt == "all":
        top = 120
        for index, key in enumerate(essentials.FORMATS):
            y = top + index * 46
            value, size = counts[index], len(essentials.get(key)["items"])
            draw.text((640, y), essentials.FORMAT_LABELS[key], font=_font(24, bold=True), fill=(214, 211, 235))
            draw.rounded_rectangle((830, y + 6, 1110, y + 26), radius=10, fill=(36, 32, 66))
            filled = 830 + round(280 * value / size) if size else 830
            if filled > 836:
                draw.rounded_rectangle((830, y + 6, filled, y + 26), radius=10, fill=ACCENTS[FORMAT_KINDS[key]])
    else:
        cell, gap, left, top = 36, 7, 690, 118
        for index in range(total):
            row, column = divmod(index, 10)
            x, y = left + column * (cell + gap), top + row * (cell + gap)
            draw.rounded_rectangle((x, y, x + cell, y + cell), radius=7, fill=accent if index < done else (36, 32, 66))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _png(content: bytes) -> Response:
    return Response(content=content, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"})


@router.get(essentials.BASE_PATH + "/score/{counts}/card.png", include_in_schema=False)
def essentials_all_card(counts: str, request: Request):
    values = _parse_all(counts)
    if values is None:
        raise HTTPException(404, "Not found")
    return _png(render_card("all", tuple(values)))


@router.get(essentials.BASE_PATH + "/{fmt}/score/{done}/card.png", include_in_schema=False)
def essentials_card(fmt: str, done: str, request: Request):
    parsed = _parse_one(fmt, done)
    if parsed is None:
        raise HTTPException(404, "Not found")
    return _png(render_card(fmt, (parsed[1],)))


# ---------------------------------------------------------------- saving

class EssentialSave(BaseModel):
    id: str = Field(..., min_length=3, max_length=160)
    answer: Literal["seen", "want"]


def _image_for(db: Session, item: dict) -> Optional[str]:
    image = _details(db).get(item["id"], {}).get("image")
    if not title_pages._safe_image(image):
        image = essentials.posters(db, [item]).get(item["id"])
    return title_pages._safe_image(image)


@router.post("/api/essentials/save")
def essentials_save(payload: EssentialSave, request: Request, response: Response,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add one essential title to the member's library: finished ("seen") or not started ("want")."""
    response.headers["Cache-Control"] = "private, no-store"
    item = essentials.item_by_id(payload.id)
    if item is None:
        raise HTTPException(404, "That title isn't on the list.")
    lock_progress_owner(db, user.id)
    state, record = essentials.add(db, user, item, payload.answer == "seen", _image_for(db, item))
    # An anime film the member filed under movies is found there, so name the shelf it is on.
    kind = essentials.kind_of(record) or item["kind"]
    category = title_pages.KINDS[kind][2]
    result = {
        "state": state, "title": record.title, "category": category, "item_id": record.id,
        "done": bool(getattr(record, title_pages.COMPLETE_FIELD[kind], False)),
        "library_url": f"/?library_category={category}&library_item={record.id}",
    }
    db.commit()
    if state == "created":
        funnel.record("essentials_saved", request)
    return result


class EssentialUndo(BaseModel):
    category: Literal["movies", "tv-shows", "anime", "video-games", "music", "books", "manga", "podcasts", "audiobooks"]
    item_id: int = Field(..., ge=1, le=2147483647)


@router.post("/api/essentials/undo")
def essentials_undo(payload: EssentialUndo, request: Request, response: Response,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Take back a title added from a list a moment ago. Older library entries are never removed from here."""
    response.headers["Cache-Control"] = "private, no-store"
    kind = title_pages.LIBRARY_TO_KIND[payload.category]
    model = title_pages.KINDS[kind][0]
    record = db.query(model).filter(model.user_id == user.id, model.id == payload.item_id).first()
    if record is None:
        raise HTTPException(404, "That title is no longer in your library.")
    if not essentials.undo_allowed(record):
        raise HTTPException(409, "That title has been in your library for a while. Remove it from your library instead.")
    if not essentials.from_a_list(kind, record):
        # Undo is for a save made on a list; anything else is removed from the library itself.
        raise HTTPException(409, "That title isn't on the Essential 100 lists. Remove it from your library instead.")
    db.rollback()
    if delete_owned_media(db, user.id, payload.category, payload.item_id) is None:
        raise HTTPException(404, "That title is no longer in your library.")
    return {"removed": True}


class EssentialImport(BaseModel):
    ids: list[str] = Field(..., max_length=900)


@router.post("/api/essentials/import")
def essentials_import(payload: EssentialImport, request: Request, response: Response,
                      user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Move titles a visitor ticked as finished before signing up (kept in their browser) into their library."""
    response.headers["Cache-Control"] = "private, no-store"
    lock_progress_owner(db, user.id)
    added, existing, missing = 0, 0, 0
    items = []
    for item_id in dict.fromkeys(payload.ids):
        item = essentials.item_by_id(item_id) if isinstance(item_id, str) and len(item_id) <= 160 else None
        if item is None:
            missing += 1
        else:
            items.append(item)
    # One query per format for what is already there, instead of one per ticked title.
    have = essentials.library_titles(db, user.id, items)
    for item in items:
        key = (item["kind"], title_pages.normalize(item["title"]))
        # A name is enough for books and the like; films, shows, games and albums share names
        # (remakes, two albums called Blue), so essentials.add checks those properly.
        if key in have and item["kind"] not in essentials.NAME_SHARED:
            existing += 1
            continue
        state, _ = essentials.add(db, user, item, True)
        have.add(key)
        if state == "created":
            added += 1
        else:
            existing += 1
    db.commit()
    if added:
        funnel.record("essentials_imported", request)
    return {"added": added, "existing": existing, "missing": missing}
