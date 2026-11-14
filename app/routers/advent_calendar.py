"""The December advent calendar: the page, one page per door for sharing, its share card and the member API.

The page reads completely without scripts or an account: every opened door's
write-up is on it. advent-calendar.js adds the door opening, the member's
progress, saving and the morning reminder. Visitors keep opened doors and saved
picks in their browser until they sign up.
"""
from __future__ import annotations

import io
from datetime import date
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import advent_calendar as advent, badges, browse, funnel, models, pick, title_pages, title_search
from ..admin_access import is_site_admin
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_current_user, get_db, get_optional_current_user
from .profiles import _CardCache

router = APIRouter(tags=["advent-calendar"])
_CARDS = _CardCache(size=64)
CSS_VERSION = "20261114-advent-1"
JS_VERSION = "20261114-advent-1"
SEASONAL_CSS = "/static/seasonal.css?v=20261106-holiday-guides-1"
LIKED_CSS = "/static/if-you-liked.css?v=20261106-holiday-guides-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261031-browse-1"
SIGNUP_NEXT = quote(advent.BASE_PATH, safe="")
FORMAT_PLURALS = {"movie": "films", "tv": "TV", "anime": "anime", "game": "games", "book": "books", "album": "albums",
                  "manga": "manga", "podcast": "podcasts", "audiobook": "audiobooks"}
# Where each door sits on the calendar: shuffled, like a paper one, with door 24 in the bottom corner.
# Doors drawn twice as wide: the first, the solstice, Christmas Eve and three weekend doors.
# Six wide doors fill whole rows of six (desktop) and of three (phones).
BIG_DOORS = (1, 6, 12, 13, 21, 24)
GRID_ORDER = (17, 3, 11, 22, 6, 14, 1, 19, 9, 13, 4, 20, 7, 16, 2, 23, 10, 5, 15, 21, 8, 12, 18, 24)


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: date) -> str:
    return value.strftime("%B %d, %Y").replace(" 0", " ")


def _day_label(value: date) -> str:
    return value.strftime("%A, %B %d").replace(" 0", " ")


def _preview(user) -> bool:
    return user is not None and is_site_admin(user)


def _year_or_404(year: int, user=None) -> int:
    if advent.edition(year) is None:
        raise HTTPException(status_code=404, detail="No advent calendar for that year.")
    if not advent.is_public(year) and not _preview(user):
        raise HTTPException(status_code=404, detail="No advent calendar for that year.")
    return year


def _unlocked(year: int, user) -> list[int]:
    return advent.unlocked(year, preview=_preview(user) and not advent.is_public(year))


def _details(db: Session, year: int) -> dict[int, dict]:
    """{day: {"url", "image"}} for picks that already have a public title page (never raises)."""
    try:
        index = title_search.index(db)
    except Exception:
        return {}
    by_slug = {(entry["kind"], entry["slug"]): entry for entry in index}
    by_base: dict[tuple[str, str], dict] = {}
    for entry in index:
        current = by_base.get((entry["kind"], entry["base"]))
        if current is None or entry["members"] > current["members"]:
            by_base[(entry["kind"], entry["base"])] = entry
    found = {}
    for item in advent.doors(year):
        saved = advent.entry_for(item)
        match = by_slug.get((saved["kind"], saved["slug"])) or by_base.get((saved["kind"], title_pages.slugify(saved["title"])))
        if match is not None:
            found[item["day"]] = {"url": f"/titles/{match['kind']}/{match['slug']}", "image": match.get("image")}
    return found


def _meta_line(item: dict) -> str:
    parts = [title_pages.KINDS[item["kind"]][3], str(item["year"])]
    if item.get("creator"):
        parts.append(item["creator"])
    return " · ".join(parts)


# ---------------------------------------------------------------- page parts

def _grid(year: int, days: list[int]) -> str:
    cells = []
    for day in GRID_ORDER:
        item = advent.door(year, day)
        when = advent.door_date(year, day)
        size = " ad-door--big" if day in BIG_DOORS else ""
        if day in days:
            cells.append(
                f'<li class="ad-cell{size}"><a class="ad-door ad-door--ready" href="#{advent.door_anchor(day)}" '
                f'data-advent-door="{day}" data-advent-date="{when.isoformat()}" '
                f'aria-label="Door {day}, {_e(_day_label(when))}: {_e(item["hint"])}">'
                f'<span class="ad-door__front" aria-hidden="true"><span class="ad-door__num">{day}</span>'
                f'<span class="ad-door__hint">{_e(item["hint"])}</span></span>'
                f'<span class="ad-door__back" aria-hidden="true"><span class="ad-door__kind">{_e(title_pages.KINDS[item["kind"]][3])}</span>'
                f'<span class="ad-door__title">{_e(item["title"])}</span></span></a></li>')
        else:
            cells.append(
                f'<li class="ad-cell{size}"><span class="ad-door ad-door--locked" data-advent-locked="{day}">'
                f'<span class="ad-door__front"><span class="ad-door__num">{day}</span>'
                f'<span class="ad-door__hint">{_e(item["hint"])}</span>'
                f'<span class="ad-door__when">Opens {_e(when.strftime("%b %d").replace(" 0", " "))}</span></span></span></li>')
    return f'<ul class="ad-grid" aria-label="The calendar, door by door">{"".join(cells)}</ul>'


def _save_button(item: dict, signed_in: bool) -> str:
    saved = advent.entry_for(item)
    if signed_in:
        return (f'<button type="button" class="button sn-save" data-advent-add="{item["day"]}">'
                'Add to my library</button>')
    return (f'<button type="button" class="button sn-save" aria-pressed="false" data-guest-kind="{_e(saved["kind"])}" '
            f'data-guest-slug="{_e(saved["slug"])}" data-guest-title="{_e(saved["title"])}">'
            '<span class="sn-when-off">Save to my list</span><span class="sn-when-on">Saved to your list ✓</span></button>')


def door_html(year: int, item: dict, details: dict, signed_in: bool, heading: str = "h3", share: bool = True) -> str:
    day = item["day"]
    when = advent.door_date(year, day)
    detail = details.get(day, {})
    image = title_pages._safe_image(detail.get("image"))
    art = (f'<img class="sn-pick__art" src="{_e(image)}" alt="" width="96" height="144" loading="lazy" '
           'decoding="async" referrerpolicy="no-referrer">' if image
           else f'<span class="sn-pick__art sn-pick__art--letter ad-art" aria-hidden="true">{day}</span>')
    title_link = (f'<a class="sn-pick__link" href="{_e(detail["url"])}">See the title page</a>'
                  if detail.get("url") else "")
    share_title = f"Door {day} of the OmniTrackr advent calendar: {item['title']}"
    share_button = (f'<button type="button" class="button button--ghost ad-share" data-advent-share="{day}" '
                    f'data-share-url="{_e(advent.SITE_URL + advent.door_path(year, day))}" '
                    f'data-share-title="{_e(share_title)}">'
                    'Share this door</button>') if share else ""
    return (
        f'<article class="pick sn-pick ad-pick" id="{advent.door_anchor(day)}" data-advent-pick="{day}" '
        f'data-advent-date="{when.isoformat()}">'
        f'<p class="ad-pick__day"><span class="ad-pick__num">Door {day}</span> {_e(_day_label(when))}'
        '<span class="ad-pick__opened" data-advent-opened hidden>Opened</span></p>'
        f'<div class="sn-pick__head">{art}<div><p class="eyebrow">{_e(_meta_line(item))}</p>'
        f'<{heading}>{_e(item["title"])}</{heading}>'
        f'<p class="sn-pick__time">{_e(item["time"])}</p></div></div>'
        f'<p class="sn-pick__why">{_e(item["why"])}</p><p>{_e(item["note"])}</p>'
        f'<p class="caveat"><strong>Before you start:</strong> {_e(item["caveat"])}</p>'
        f'<div class="sn-pick__actions">{_save_button(item, signed_in)}{share_button}{title_link}'
        '<span class="sn-pick__owned" data-advent-owned hidden></span></div>'
        '<p class="sn-pick__status" data-advent-status role="status" aria-live="polite"></p></article>'
    )


def _related(today: date) -> str:
    from .. import new_year_challenge, seasonal
    from ..discover_catalog import published_editions
    from .seasonal import EXTRA_LINKS
    hub = seasonal.season("holidays")
    links = [(hub["path"], "Holiday picks", hub["card"])]
    links.extend((extra["path"], extra["name"], extra["tagline"]) for extra in EXTRA_LINKS.get("holidays", [])
                 if extra["path"] != advent.BASE_PATH)
    edition = f"december-{today.year}"
    editions = published_editions(today)
    if edition in editions:
        links.append((f"/discover/monthly/{edition}", editions[edition]["name"],
                      "December's Discover edition: six picks around one idea, across formats."))
    year = new_year_challenge.current_year()
    if year and new_year_challenge.is_open(year):
        links.append((new_year_challenge.path(year), f"The {year} New Year challenge",
                      f"Pick how many books, films, games and albums you want to finish in {year}."))
    links.append(("/pick", "Pick for me", "Between doors? Get one suggestion at a time from every guide on the site."))
    cards = "".join(f'<article><h3><a href="{_e(href)}">{_e(name)}</a></h3><p>{_e(text)}</p></article>'
                    for href, name, text in links)
    return ('<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE TO READ</p>'
            f'<h2 id="related-heading">More for December</h2><div class="guide-related-grid">{cards}</div></section>')


def page_content(year: int, days: list[int], details: dict, signed_in: bool, preview: bool = False,
                 today: Optional[date] = None) -> str:
    today = today or date.today()
    data = advent.edition(year)
    shown = [advent.door(year, day) for day in reversed(days)]
    formats = sorted({item["kind"] for item in advent.doors(year)}, key=list(title_pages.KINDS).index)
    how = "".join(f'<li><h3>{_e(name)}</h3><p>{_e(text)}</p></li>' for name, text in data["how"])
    faq = "".join(f'<details class="sn-faq__item"><summary>{_e(question)}</summary><p>{_e(answer)}</p></details>'
                  for question, answer in data["faq"])
    left = advent.DOORS - len(days)
    status = (f"{len(days)} of {advent.DOORS} doors open" if left else f"All {advent.DOORS} doors are open")
    member = ('<section class="sn-progress ad-progress" data-advent-progress aria-labelledby="ad-progress-title" hidden>'
              '<p class="eyebrow">YOUR CALENDAR</p><h2 id="ad-progress-title" data-advent-progress-title>Your calendar</h2>'
              f'<div class="sn-meter" role="progressbar" aria-valuemin="0" aria-valuemax="{advent.DOORS}" aria-valuenow="0" '
              'aria-labelledby="ad-progress-title" data-advent-meter><span class="sn-meter__fill" data-advent-meter-fill></span></div>'
              '<p class="sn-progress__text" data-advent-progress-text></p>'
              + ('<div class="ad-remind"><button type="button" class="button button--ghost" data-advent-remind aria-pressed="false">'
                 'Remind me each morning</button><p class="ad-remind__note" data-advent-remind-note role="status" aria-live="polite"></p></div>'
                 if signed_in else
                 f'<p class="ad-progress__guest">Your opened doors are kept in this browser. <a href="/?next={SIGNUP_NEXT}#signup" '
                 'data-advent-signup>Sign up free</a> to keep them, earn the Door Opener badge and get a reminder each morning.</p>')
              + '</section>')
    notice = ('<p class="ad-preview" role="note">Preview for site admins: every door is open and the page is hidden from '
              f'search until {_e(_long_date(advent.opens(year)))}.</p>') if preview else ""
    parts = [
        f'<article class="trail-guide sn-hub ad-calendar" data-season-theme="holiday" data-advent-year="{year}" '
        f'data-advent-member="{"1" if signed_in else "0"}" data-advent-total="{advent.DOORS}">',
        notice,
        '<header class="hero hero--guide sn-hero ad-hero"><span class="sn-hero__moon" aria-hidden="true"></span>',
        f'<p class="eyebrow">SEASONAL · DECEMBER {year}</p>',
        f'<h1>{_e(data["headline"])}</h1><p class="guide-deck">{_e(data["deck"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{_e(data["reviewed"])}">{_e(_long_date(date.fromisoformat(data["reviewed"])))}</time> · '
        f'{status}, across {_e(", ".join(FORMAT_PLURALS[kind] for kind in formats))}</p>',
        '<nav class="guide-jump" aria-label="On this page"><a href="#calendar">The calendar</a><a href="#doors">Behind the doors</a>'
        '<a href="#how">How it works</a><a href="#faq">Questions</a></nav>',
        '<p class="sn-companion__parent">Part of the <a href="/holidays">holiday picks</a>.</p></header>',
        member,
        f'<div class="guide-intro">{_paragraphs(data["intro"])}</div>',
        '<section id="calendar" class="ad-board" aria-labelledby="calendar-heading">',
        '<h2 id="calendar-heading" class="ad-board__title">The calendar</h2>',
        '<p class="ad-board__lede">Tap a door to open it. Locked doors show what is coming.</p>',
        _grid(year, days), '</section>',
    ]
    if not signed_in:
        parts.append('<p class="yl-section-intro sn-guest-note">Save any pick to a list as you go, no account needed. '
                     'Your list moves into a free library when you sign up.</p>')
    parts.append('<section id="doors" class="ad-doors" aria-labelledby="doors-heading"><p class="eyebrow">NEWEST FIRST</p>'
                 '<h2 id="doors-heading">Behind the doors</h2><div class="ad-doors__list">')
    parts.extend(door_html(year, item, details, signed_in) for item in shown)
    parts.append('</div></section>')
    if not signed_in:
        parts.append('<div class="yl-bar sn-bar" data-guest-bar hidden><p class="yl-bar__count" data-guest-count role="status" aria-live="polite"></p>'
                     f'<a class="button" href="/?next={SIGNUP_NEXT}#signup" data-advent-signup>Save my list, free →</a></div>')
    parts.extend([
        f'<section id="how" class="editorial sn-plan" aria-labelledby="how-heading"><p class="eyebrow">HOW IT WORKS</p>'
        f'<h2 id="how-heading">Twenty-four doors, one a day</h2><ul class="sn-nights">{how}</ul></section>',
        f'<section id="faq" class="editorial sn-faq" aria-labelledby="faq-heading"><h2 id="faq-heading">Questions</h2>{faq}</section>',
        _related(today),
        '<section class="guide-sources yl-method" aria-labelledby="method-heading"><h2 id="method-heading">How we chose</h2>',
        _paragraphs(data["method"]),
        f'<p class="muted">First published {_e(_long_date(date.fromisoformat(data["published"])))}. '
        f'Checked {_e(_long_date(date.fromisoformat(data["reviewed"])))}. '
        '<a href="/contact">Suggest a pick or send a correction</a> · <a href="/content-quality">Editorial standards</a></p>'
        '</section></article>',
    ])
    return "".join(parts)


def _structured(year: int, days: list[int]) -> dict:
    data = advent.edition(year)
    url = advent.SITE_URL + advent.BASE_PATH
    return {"@context": "https://schema.org", "@graph": [
        {
            "@type": "Article", "headline": data["headline"], "description": data["summary"],
            "datePublished": data["published"], "dateModified": data["reviewed"],
            "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
            "author": {"@type": "Organization", "name": "OmniTrackr", "url": advent.SITE_URL + "/about"},
            "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": advent.SITE_URL + "/"},
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(days), "itemListElement": [
                {"@type": "ListItem", "position": day, "name": advent.door(year, day)["title"],
                 "url": f"{url}#{advent.door_anchor(day)}"} for day in days
            ]},
        },
        {
            "@type": "FAQPage", "url": url + "#faq", "mainEntity": [
                {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
                for question, answer in data["faq"]
            ],
        },
    ]}


def _head(signed_in: bool, indexable: bool) -> str:
    head = (f'<link rel="stylesheet" href="{LIKED_CSS}"><link rel="stylesheet" href="{SEASONAL_CSS}">'
            f'<link rel="stylesheet" href="/static/advent-calendar.css?v={CSS_VERSION}">')
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
        if indexable:
            head += '<script src="/static/ad-loader.js" defer></script>'
    head += f'<script src="/static/advent-calendar.js?v={JS_VERSION}" defer></script>'
    return head


@router.get(advent.BASE_PATH, include_in_schema=False)
def calendar_page(request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    from .discover import page
    year = advent.current_year()
    preview = False
    if year is None and _preview(user):
        year, preview = min(advent.EDITIONS), True
    if year is None:
        raise HTTPException(status_code=404, detail="The advent calendar opens on December 1.")
    signed_in = user is not None
    days = _unlocked(year, user)
    data = advent.edition(year)
    indexable = not preview
    content = page_content(year, days, _details(db, year), signed_in, preview=preview)
    response = page(data["search_title"], data["summary"], advent.BASE_PATH, content,
                    structured_data=_structured(year, days), head=_head(signed_in, indexable),
                    member=signed_in, indexable=indexable,
                    share_image=f"{advent.SITE_URL}{advent.door_path(year, days[-1])}/card.png" if days else None)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


# ---------------------------------------------------------------- one door, for sharing

def _door_or_404(year: int, day: int, user=None) -> dict:
    _year_or_404(year, user)
    item = advent.door(year, day)
    if item is None or day not in _unlocked(year, user):
        raise HTTPException(status_code=404, detail="That door hasn't opened yet.")
    return item


@router.get(advent.BASE_PATH + "/{year}/{day}", include_in_schema=False)
def door_page(year: int, day: int, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    from .discover import page
    item = _door_or_404(year, day, user)
    signed_in = user is not None
    if not signed_in:
        funnel.record("advent_door_link_opened", request)
    when = advent.door_date(year, day)
    days = _unlocked(year, user)
    cta = ('<section class="ad-door-cta"><div><h2>Open the rest of the calendar</h2>'
           f'<p>{len(days)} of {advent.DOORS} doors are open so far, a new pick every morning until Christmas Eve. '
           'Every format is in there: films, TV, anime, games, books, albums, manga, podcasts and audiobooks.</p></div>'
           f'<a class="button" href="{advent.BASE_PATH}#{advent.door_anchor(day)}">See the calendar →</a></section>')
    content = (
        f'<article class="trail-guide sn-hub ad-calendar ad-calendar--door" data-season-theme="holiday" data-advent-year="{year}" '
        f'data-advent-member="{"1" if signed_in else "0"}" data-advent-total="{advent.DOORS}" data-advent-single="1">'
        '<header class="hero hero--guide sn-hero ad-hero"><span class="sn-hero__moon" aria-hidden="true"></span>'
        f'<p class="eyebrow">THE ADVENT CALENDAR · DOOR {day} OF {advent.DOORS}</p>'
        f'<h1>Door {day}: {_e(item["title"])}</h1>'
        f'<p class="guide-deck">{_e(_day_label(when))}. {_e(item["hint"])}.</p>'
        '<p class="sn-companion__parent">From the <a href="/holidays/advent-calendar">December advent calendar</a>.</p></header>'
        f'{door_html(year, item, _details(db, year), signed_in, heading="h2", share=True)}{cta}</article>'
    )
    title = f"Door {day}: {item['title']} · The OmniTrackr advent calendar"
    description = f"Door {day} of the OmniTrackr December advent calendar: {item['title']} ({_meta_line(item)}). {item['hint']}."
    response = page(title, description, advent.door_path(year, day), content, head=_head(signed_in, False),
                    member=signed_in, indexable=False,
                    share_image=f"{advent.SITE_URL}{advent.door_path(year, day)}/card.png")
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


def render_door_card(year: int, item: dict) -> bytes:
    from PIL import Image, ImageDraw
    from .profiles import _fit, _font
    width, height = 1200, 630
    image = Image.new("RGB", (width, height), (12, 16, 34))
    draw = ImageDraw.Draw(image)
    # A field of small doors down the right side, the shared one lit.
    cols, rows, size, gap = 4, 6, 70, 12
    left = width - 84 - cols * size - (cols - 1) * gap
    top = (height - rows * size - (rows - 1) * gap) // 2
    number_font = _font(26, bold=True)
    for index in range(cols * rows):
        number = GRID_ORDER[index]
        row, col = divmod(index, cols)
        x, y = left + col * (size + gap), top + row * (size + gap)
        lit = number == item["day"]
        fill = (251, 191, 36) if lit else ((34, 30, 64) if number > item["day"] else (52, 26, 40))
        outline = (253, 230, 138) if lit else (70, 64, 120)
        draw.rounded_rectangle((x, y, x + size, y + size), radius=10, fill=fill, outline=outline, width=2)
        label = str(number)
        ink = (31, 19, 0) if lit else (196, 181, 253)
        draw.text((x + (size - draw.textlength(label, font=number_font)) / 2, y + 20), label, font=number_font, fill=ink)
    text_width = left - 84 - 48
    draw.text((84, 74), "OmniTrackr · the December advent calendar", font=_font(28, bold=True), fill=(251, 191, 36))
    when = advent.door_date(year, item["day"]).strftime("%B %d").replace(" 0", " ")
    draw.text((84, 132), f"Door {item['day']} · {when}", font=_font(40, bold=True), fill=(248, 113, 113))
    title_font = _font(62, bold=True)
    words, lines, line = item["title"].split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=title_font) <= text_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    y = 200
    for text in lines[:3]:
        draw.text((84, y), _fit(draw, text, title_font, text_width), font=title_font, fill=(245, 243, 255))
        y += 74
    draw.text((84, y + 10), _fit(draw, _meta_line(item), _font(28), text_width), font=_font(28), fill=(196, 181, 253))
    draw.text((84, y + 56), _fit(draw, item["hint"], _font(26), text_width), font=_font(26), fill=(167, 160, 199))
    host = advent.SITE_URL.replace("https://", "").replace("http://", "")
    draw.text((84, height - 92), f"{host}{advent.BASE_PATH}", font=_font(24), fill=(167, 160, 199))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


@router.get(advent.BASE_PATH + "/{year}/{day}/card.png", include_in_schema=False)
def door_card(year: int, day: int, request: Request, user=Depends(get_optional_current_user)):
    item = _door_or_404(year, day, user)
    key = (year, f"advent:{year}:{day}:{advent.door_date(year, day).isoformat()}")
    png = _CARDS.get(key)
    if png is None:
        try:
            png = render_door_card(year, item)
        except Exception:
            raise HTTPException(status_code=404, detail="Card unavailable")
        _CARDS.put(key, png)
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff",
    })


# ---------------------------------------------------------------- member API

def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _has_device(db: Session, user_id: int) -> bool:
    return db.query(models.PushSubscription.id).filter(models.PushSubscription.user_id == user_id).first() is not None


def _state(db: Session, user: models.User, year: int) -> dict:
    days = _unlocked(year, user)
    opened = advent.opened_days(db, user.id, year)
    owned = advent.library(db, user.id, year, days)
    return {
        "year": year, "total": advent.DOORS, "unlocked": days, "opened": opened,
        "reminder": advent.reminder(db, user.id, year) is not None, "has_device": _has_device(db, user.id),
        "library": {str(day): value for day, value in owned.items()},
        "badge": badges.badge_row(badges.BY_KEY["advent"], advent.most_doors(db, user.id)),
    }


@router.get("/api/advent-calendar")
def advent_card(request: Request, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The dashboard card: today's door and how many the member opened ({"show": false} outside December)."""
    _no_store(response)
    return advent.card(db, user)


@router.get("/api/advent-calendar/{year}")
def advent_state(year: int, request: Request, response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    _year_or_404(year, user)
    return _state(db, user, year)


class OpenBody(BaseModel):
    days: list[int] = Field(..., min_length=1, max_length=advent.DOORS)


@router.post("/api/advent-calendar/{year}/open")
def advent_open(year: int, body: OpenBody, request: Request, response: Response,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mark doors as opened: one tap, or every door a visitor opened before signing up."""
    _no_store(response)
    _year_or_404(year, user)
    fresh = advent.open_doors(db, user.id, year, body.days, _unlocked(year, user))
    if fresh:
        funnel.record("advent_door_opened", request)
        try:
            badges.record(db, user, badges.counts(db, user))
        except Exception:
            db.rollback()
    return {**_state(db, user, year), "newly_opened": fresh}


@router.post("/api/advent-calendar/{year}/doors/{day}/add")
def advent_add(year: int, day: int, request: Request, response: Response,
               user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a door's pick to the library as not started (title, year and creator only)."""
    from ..progress import lock_progress_owner
    _no_store(response)
    item = _door_or_404(year, day, user)
    lock_progress_owner(db, user.id)
    if day in advent.library(db, user.id, year, [day]):
        return {"state": "existing", "title": item["title"], **_state(db, user, year)}
    chosen = advent.entry_for(item)
    image = _details(db, year).get(day, {}).get("image")
    if "browse_kind" in chosen:
        state, record = browse.add_to_library(db, user, chosen["browse_kind"], chosen, image)
    else:
        state, record = pick.add_to_library(db, user, chosen, image)
    db.commit()
    if state == "created":
        funnel.record("advent_saved", request)
    return {"state": state, "title": record.title, **_state(db, user, year)}


class ReminderBody(BaseModel):
    on: bool


@router.put("/api/advent-calendar/{year}/reminder")
def advent_reminder(year: int, body: ReminderBody, request: Request, response: Response,
                    user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    _year_or_404(year, user)
    if not advent.is_public(year):
        raise HTTPException(status_code=409, detail="Reminders start once the calendar opens.")
    was_on = advent.reminder(db, user.id, year) is not None
    advent.set_reminder(db, user.id, year, body.on)
    if body.on and not was_on:
        funnel.record("advent_reminder_on", request)
    return _state(db, user, year)
