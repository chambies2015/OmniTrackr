"""The Black Friday and Cyber Monday guide at /holidays/black-friday (writing in deal_guides.py).

The page reads completely without scripts or an account. Signed-in members also get
a short list from their own library, the titles they haven't started and the
favourites they'd like to own, each with an Amazon search link, and the format
sections ordered by what they track most. Nothing is stored: the list is read from
the library each time the page loads.
"""
from __future__ import annotations

from datetime import date
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import affiliate, gift_lists, title_pages
from ..deal_guides import GUIDE, PICKS, SECTIONS
from ..dependencies import get_db, get_optional_current_user
from .discover import page
from .gift_guide import _art, _title_pages

router = APIRouter(tags=["deals-guide"])
CSS_VERSION = "20261109-black-friday-1"
SITE = "https://omnitrackr.xyz"
SIGNUP_NEXT = quote(GUIDE["path"], safe="")
STORE_LABELS = {"audible": "Find it on Audible"}
MEMBER_WAITING = 8
MEMBER_FAVOURITES = 4
BLACK_FRIDAY = "2026-11-27"
CYBER_MONDAY = "2026-11-30"


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


def _head(*, ads: bool) -> str:
    head = ('<link rel="stylesheet" href="/static/if-you-liked.css?v=20261104-gifts-1">'
            '<link rel="stylesheet" href="/static/seasonal.css?v=20261106-holiday-guides-1">'
            '<link rel="stylesheet" href="/static/gift-guide.css?v=20261104-gifts-1">'
            f'<link rel="stylesheet" href="/static/deals-guide.css?v={CSS_VERSION}">')
    if ads:
        head += '<script src="/static/ad-loader.js" defer></script>'
    return head


def countdown(today: date) -> str:
    """A short line for the hero: days to Black Friday, today's name, or nothing once the week is over."""
    friday, monday = date.fromisoformat(BLACK_FRIDAY), date.fromisoformat(CYBER_MONDAY)
    if today < friday:
        days = (friday - today).days
        return f"{days} day{'s' if days != 1 else ''} to Black Friday"
    if today == friday:
        return "It's Black Friday today"
    if today < monday:
        return "Cyber Monday is on November 30"
    if today == monday:
        return "It's Cyber Monday today"
    return ""


# ---------------------------------------------------------------- page parts

def _calendar(today: date) -> str:
    entries = GUIDE["calendar"]
    # The day we're in: the last entry that has started (the first one covers Monday to Wednesday).
    now = None
    for index, entry in enumerate(entries):
        if date.fromisoformat(entry["date"]) <= today:
            now = index
    if now is not None and today > date.fromisoformat(CYBER_MONDAY) and now < len(entries) - 1:
        now = None  # between Cyber Monday and the Steam sale nothing is "on"
    days = []
    for index, entry in enumerate(entries):
        classes = "bf-day" + (" bf-day--big" if entry["tone"] == "big" else "") + (" bf-day--now" if index == now else "")
        flag = '<span class="bf-day__now">Now</span>' if index == now else ""
        days.append(
            f'<li class="{classes}"><p class="bf-day__when"><span>{_e(entry["day"])}</span> '
            f'<time datetime="{_e(entry["date"])}">{_e(entry["label"])}</time>{flag}</p>'
            f'<h3>{_e(entry["name"])}</h3><p>{_e(entry["text"])}</p></li>')
    return ('<section class="bf-week" id="dates" aria-labelledby="dates-heading"><p class="eyebrow">THE DATES</p>'
            f'<h2 id="dates-heading">The week, day by day</h2><p class="bf-lead">{_e(GUIDE["calendar_intro"])}</p>'
            f'<ol class="bf-days">{"".join(days)}</ol></section>')


def _checks() -> str:
    items = "".join(f'<li><h3>{_e(name)}</h3><p>{_e(text)}</p></li>' for name, text in GUIDE["checks"])
    return ('<section class="bf-checks" id="checks" aria-labelledby="checks-heading"><p class="eyebrow">BEFORE YOU PAY</p>'
            f'<h2 id="checks-heading">Five checks before you buy anything</h2><ol class="bf-checks__list">{items}</ol></section>')


def _buy(pick: dict) -> str:
    if pick.get("link"):
        url, label = pick["link"]
        return (f'<a class="button button--ghost" href="{_e(url)}" target="_blank" rel="noopener">{_e(label)} '
                '<span aria-hidden="true">↗</span></a>')
    if not pick.get("search"):
        return ""
    links = affiliate.search_links(pick["search"], pick["store"])
    label = STORE_LABELS.get(pick["store"])
    return "".join(
        f'<a class="button gg-buy" href="{_e(link["url"])}" target="_blank" rel="sponsored noopener noreferrer">'
        f'{_e(label or link["label"])} <span aria-hidden="true">↗</span></a>'
        for link in links)


def _meta(pick: dict) -> str:
    if pick["kind"] in title_pages.KINDS and pick.get("title"):
        parts = [title_pages.KINDS[pick["kind"]][3], str(pick["year"])]
        if pick.get("creator"):
            parts.append(pick["creator"])
        return " · ".join(parts)
    return ""


def _pick_html(pick: dict, pages: dict) -> str:
    detail = pages.get(pick["id"], {})
    meta = _meta(pick)
    title_link = (f'<a class="gg-gift__link" href="{_e(detail["url"])}">See the title page</a>'
                  if detail.get("url") else "")
    return (
        f'<article class="gg-gift bf-pick" id="pick-{_e(pick["id"])}">'
        f'<div class="gg-gift__head">{_art(pick["name"], detail.get("image"), "gg-gift__art")}<div>'
        f'<h3>{_e(pick["name"])}</h3>'
        + (f'<p class="gg-gift__meta">{_e(meta)}</p>' if meta else "")
        + '</div></div>'
        f'<p class="gg-gift__why">{_e(pick["why"])}</p>'
        f'<p class="caveat"><strong>Before you buy:</strong> {_e(pick["check"])}</p>'
        f'<div class="gg-gift__actions">{_buy(pick)}{title_link}</div></article>'
    )


def _section_html(section: dict, pages: dict) -> str:
    drops = "".join(f"<li>{_e(line)}</li>" for line in section["drops"])
    holds = "".join(f"<li>{_e(line)}</li>" for line in section["holds"])
    picks = "".join(_pick_html(pick, pages) for pick in section["picks"])
    key = _e(section["key"])
    return (
        f'<section class="sn-shelf bf-section" id="{key}" aria-labelledby="section-{key}">'
        f'<header class="sn-shelf__head"><p class="eyebrow">{_e(section["name"].upper())}</p>'
        f'<h2 id="section-{key}">{_e(section["tagline"])}</h2>'
        f'<div class="sn-shelf__intro">{_paragraphs(section["intro"])}</div></header>'
        '<div class="bf-verdicts">'
        f'<div class="bf-verdict bf-verdict--drops"><h3>Tends to get cheaper</h3><ul>{drops}</ul></div>'
        f'<div class="bf-verdict bf-verdict--holds"><h3>Rarely moves</h3><ul>{holds}</ul></div></div>'
        f'<h3 class="bf-watch">Worth watching for</h3><div class="gg-gifts bf-picks">{picks}</div></section>'
    )


def ordered_sections(counts: Optional[dict]) -> list[dict]:
    """The format sections, most-tracked first for a member; page order otherwise."""
    if not counts or not any(counts.values()):
        return list(SECTIONS)
    return sorted(SECTIONS, key=lambda section: -sum(counts.get(kind, 0) for kind in section["kinds"]))


def _member_item(entry: dict) -> str:
    meta = [entry["label"]]
    if entry.get("year"):
        meta.append(str(entry["year"]))
    if entry.get("creator"):
        meta.append(entry["creator"])
    links = affiliate.links_for(entry["kind"], entry["title"], entry.get("creator") or "")
    buy = "".join(
        f'<a class="bf-mine__buy" href="{_e(link["url"])}" target="_blank" rel="sponsored noopener noreferrer">'
        f'{_e(link["label"])} <span aria-hidden="true">↗</span></a>' for link in links)
    category = title_pages.KINDS[entry["kind"]][2]
    library = f'/?library_category={_e(category)}&amp;library_item={int(entry["id"])}'
    return (f'<li class="gg-idea bf-mine__item">{_art(entry["title"], entry.get("image"), "gg-item__art")}'
            f'<div class="gg-item__body"><strong>{_e(entry["title"])}</strong><small>{_e(" · ".join(meta))}</small>'
            f'<span class="bf-mine__links">{buy}<a class="bf-mine__open" href="{library}">In your library</a></span></div></li>')


def member_panel(suggestions: Optional[dict]) -> str:
    waiting = (suggestions or {}).get("waiting", [])[:MEMBER_WAITING]
    favourites = (suggestions or {}).get("favourites", [])[:MEMBER_FAVOURITES]
    lists = ""
    if waiting:
        lists += ('<div><h3>Still on your to-do list</h3><p class="gg-muted">The newest titles you added and haven\'t '
                  f'started.</p><ul class="gg-ideas__list">{"".join(_member_item(entry) for entry in waiting)}</ul></div>')
    if favourites:
        lists += ('<div><h3>Favourites you might want to own</h3><p class="gg-muted">Finished and rated 8 or more.</p>'
                  f'<ul class="gg-ideas__list">{"".join(_member_item(entry) for entry in favourites)}</ul></div>')
    if not lists:
        lists = ('<p class="gg-muted">Add a few titles you want to get to, or rate the ones you loved, and they\'ll show '
                 'up here with a link to look for them in the sales. <a href="/">Open your library</a>.</p>')
    return (
        '<section id="your-list" class="gg-panel bf-mine" aria-labelledby="your-list-title">'
        '<p class="eyebrow">FROM YOUR LIBRARY</p><h2 id="your-list-title">Your list for the sales</h2>'
        '<p class="gg-panel__lead">The things you already said you want are the best place to start. Check the price '
        'history before you buy, and if you\'d rather someone else bought them, put them on '
        f'<a href="/holidays/gifts#gift-list">your gift list</a> instead.</p><div class="bf-mine__grid">{lists}</div></section>'
    )


def guest_promo() -> str:
    return (
        '<section id="your-list" class="gg-panel gg-promo" aria-labelledby="your-list-title">'
        '<p class="eyebrow">KNOW WHAT YOU WANT FIRST</p><h2 id="your-list-title">Shop from your own list, not the banners</h2>'
        '<ol class="gg-steps">'
        '<li>Track what you watch, play, read and listen to on OmniTrackr, or bring it over from Letterboxd, Goodreads, '
        'Steam and other services.</li>'
        '<li>Come back to this page signed in. It lists the titles you haven\'t started and the favourites you\'d like to '
        'own, each with a link to look for it.</li>'
        '<li>Buy the ones that are really cheaper, and send the rest to family as a gift list.</li></ol>'
        f'<p class="gg-promo__actions"><a class="button" href="/?next={SIGNUP_NEXT}#signup">Start my list, free</a>'
        f'<a class="gg-gift__link" href="/?next={SIGNUP_NEXT}#login">I already have an account</a></p></section>'
    )


def _related(today: date) -> str:
    links = [
        ("/holidays/gifts", "Holiday gift guide", "Four gift ideas for each kind of fan, and a gift list you can send "
                                                   "the family."),
        ("/holidays/thanksgiving", "Thanksgiving weekend guide", "Twenty picks for the long weekend, from the drive "
                                                                 "there to the drive home."),
        ("/holidays", "Holiday picks", "Movies, shows, anime, games, books and albums for the break, sorted by how "
                                       "festive they are."),
    ]
    try:
        from .. import release_guides
        for slug, guide in release_guides.GUIDES.items():
            if guide["published"] <= today.isoformat() and guide.get("ends", "9999") >= today.isoformat():
                links.append((f"/new-releases/{slug}", guide["name"], guide["summary"]))
    except Exception:
        pass
    cards = "".join(f'<article><h3><a href="{_e(href)}">{_e(name)}</a></h3><p>{_e(text)}</p></article>'
                    for href, name, text in links[:5])
    return ('<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE TO READ</p>'
            f'<h2 id="related-heading">More for the season</h2><div class="guide-related-grid">{cards}</div></section>')


def guide_content(*, pages: dict, signed_in: bool, counts: Optional[dict] = None,
                  suggestions: Optional[dict] = None, today: Optional[date] = None) -> str:
    today = today or date.today()
    sections = ordered_sections(counts if signed_in else None)
    jump = "".join(f'<a href="#{_e(section["key"])}">{_e(section["name"])}</a>' for section in sections)
    faq = "".join(f'<details class="sn-faq__item"><summary>{_e(question)}</summary><p>{_e(answer)}</p></details>'
                  for question, answer in GUIDE["faq"])
    sorted_note = ""
    if signed_in and counts and any(counts.values()) and sections[0] is not SECTIONS[0]:
        sorted_note = (f'<p class="gg-sorted">Sorted for you: {_e(sections[0]["name"].lower())} comes first because '
                       'that\'s what you track most.</p>')
    ticker = countdown(today)
    reviewed = GUIDE["reviewed"]
    parts = [
        '<article class="trail-guide sn-hub gg-guide bf-guide" data-season-theme="holiday">',
        '<header class="hero hero--guide sn-hero bf-hero"><span class="sn-hero__moon bf-tag" aria-hidden="true"></span>',
        f'<p class="eyebrow">BLACK FRIDAY AND CYBER MONDAY {BLACK_FRIDAY[:4]}</p>',
        f'<h1>{_e(GUIDE["headline"])}</h1><p class="guide-deck">{_e(GUIDE["deck"])}</p>',
        (f'<p class="bf-countdown">{_e(ticker)}</p>' if ticker else ""),
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time> · eight formats, five checks, no made-up prices</p>',
        affiliate.disclosure_html("gg-disclosure"),
        f'<nav class="guide-jump" aria-label="Sections"><a href="#dates">Dates</a><a href="#your-list">Your list</a>'
        f'<a href="#checks">Checks</a>{jump}<a href="#faq">Questions</a></nav></header>',
        f'<div class="guide-intro">{_paragraphs(GUIDE["intro"])}</div>',
        _calendar(today),
        member_panel(suggestions) if signed_in else guest_promo(),
        _checks(),
        sorted_note,
    ]
    parts.extend(_section_html(section, pages) for section in sections)
    parts.extend([
        f'<section id="faq" class="editorial sn-faq" aria-labelledby="faq-heading"><h2 id="faq-heading">Questions</h2>{faq}</section>',
        _related(today),
        '<section class="guide-sources yl-method" aria-labelledby="method-heading"><h2 id="method-heading">How we wrote this</h2>',
        _paragraphs(GUIDE["method"]),
        f'<p class="muted">First published {_e(_long_date(GUIDE["published"]))}. Checked {_e(_long_date(reviewed))}. '
        '<a href="/contact">Send a tip or a correction</a> · <a href="/content-quality">Editorial standards</a></p>'
        '</section></article>',
    ])
    return "".join(parts)


def _structured() -> dict:
    url = SITE + GUIDE["path"]
    picks = [pick for section in SECTIONS for pick in section["picks"]]
    return {"@context": "https://schema.org", "@graph": [
        {
            "@type": "Article", "headline": GUIDE["headline"], "description": GUIDE["summary"],
            "datePublished": GUIDE["published"], "dateModified": GUIDE["reviewed"],
            "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
            "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
            "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(picks), "itemListElement": [
                {"@type": "ListItem", "position": index, "name": pick["name"], "url": f"{url}#pick-{pick['id']}"}
                for index, pick in enumerate(picks, 1)
            ]},
        },
        {
            "@type": "FAQPage", "url": url + "#faq", "mainEntity": [
                {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
                for question, answer in GUIDE["faq"]
            ],
        },
    ]}


@router.get(GUIDE["path"], include_in_schema=False)
def black_friday_page(request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    signed_in = user is not None
    counts = suggestions = None
    if signed_in:
        try:
            counts = gift_lists.library_counts(db, user.id)
            suggestions = gift_lists.suggestions(db, user.id)
        except Exception:
            counts = suggestions = None
    content = guide_content(pages=_title_pages(db, PICKS), signed_in=signed_in, counts=counts, suggestions=suggestions)
    response = page(GUIDE["search_title"], GUIDE["summary"], GUIDE["path"], content,
                    structured_data=_structured(), head=_head(ads=not signed_in), member=signed_in)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response
