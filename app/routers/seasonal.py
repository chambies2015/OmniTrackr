"""Seasonal hubs (/halloween, /holidays, /valentines-day), the guides beside the holiday hub, each member's
progress and the dashboard card.

The hub reads completely without scripts or an account. Members add one pick or
a whole shelf to their library (title, year and creator only) and see which picks
they already have; visitors keep picks in their browser-only guest list until
they sign up. The dashboard card appears only while the season is running.
"""
from __future__ import annotations

from datetime import date
from html import escape
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import browse, challenges, funnel, pick, seasonal, title_pages, title_search
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_current_user, get_db
from ..progress import lock_progress_owner
from ..seasonal_guides import SEASONS
from .discover import page

router = APIRouter(tags=["seasonal"])
CSS_VERSION = "20261121-valentines-1"
JS_VERSION = "20261022-holidays-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261122-shelf-1"
SITE = "https://omnitrackr.xyz"
MAX_ADD = 30
# Pages that sit beside a hub, shown on its dashboard card and in its "More for the season" cards.
EXTRA_LINKS = {
    "holidays": [{"path": "/holidays/gifts", "name": "Gift guide",
                  "tagline": "Gift ideas for every kind of fan, and a gift list you can send the family."},
                 {"path": "/holidays/black-friday", "name": "Black Friday guide",
                  "tagline": "What tends to get cheaper on Black Friday, what rarely does, and what to check first."}]
    + [{"path": entry["path"], "name": entry["name"], "tagline": entry["card"]}
       for _, entry in seasonal.companions_of("holidays")],
    "valentines": [{"path": "/discover/one-evening-well-spent", "name": "One evening, well spent",
                    "tagline": "Four things to finish in a single night, from Before Sunset to Florence, a short game about a first love."},
                   {"path": "/discover/weather-and-windows", "name": "Weather and windows",
                    "tagline": "Quiet, rainy stories to watch and read alone, among them In the Mood for Love and The Garden of Words."}],
}


def extra_links(slug: str) -> list[dict]:
    """EXTRA_LINKS for a hub, with the advent calendar first while it is open (December on)."""
    links = list(EXTRA_LINKS.get(slug, []))
    if slug == "holidays":
        from .. import advent_calendar
        year = advent_calendar.current_year()
        if year is not None:
            links.insert(0, {"path": advent_calendar.BASE_PATH, "name": "Advent calendar",
                             "tagline": advent_calendar.edition(year)["card"]})
    return links


FORMAT_PLURALS = {"movie": "movies", "tv": "TV shows", "anime": "anime", "game": "games", "book": "books", "album": "music",
                  "manga": "manga", "podcast": "podcasts", "audiobook": "audiobooks"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


def _day_month(day: date) -> str:
    return f"{day:%B} {day.day}"


def _release_line(item: dict, today: date) -> str:
    """"Out December 4 · Netflix" on a pick with a release date (new titles in the Christmas guide)."""
    release = item.get("release")
    if not release:
        return ""
    day = date.fromisoformat(release["date"])
    label = f'{"Released" if day <= today else "Out"} {_day_month(day)}'
    return (f'<p class="sn-pick__release"><time datetime="{_e(release["date"])}">{_e(label)}</time>'
            f' · {_e(release["where"])}</p>')


def _details(db: Session) -> dict:
    """{pool id: {"url", "image"}} for picks with a public title page (never raises)."""
    try:
        return pick.title_details(title_search.index(db))
    except Exception:
        return {}


def _meta_line(item: dict) -> str:
    parts = [title_pages.KINDS[item["kind"]][3], str(item["year"])]
    if item["creator"]:
        parts.append(item["creator"])
    return " · ".join(parts)


def _level(entry: dict, level: int) -> str:
    label = seasonal.level_label(entry, level)
    marks = "".join(f'<span class="sn-fright__mark{" sn-fright__mark--on" if index <= level else ""}"></span>'
                    for index in range(1, 6))
    return (f'<p class="sn-fright sn-fright--{level}"><span class="sn-fright__marks" aria-hidden="true">{marks}</span>'
            f'<span>{_e(entry["scale_name"])} {level} of 5 · {_e(label)}</span></p>')


def _save_button(entry: dict, signed_in: bool) -> str:
    if signed_in:
        return (f'<button type="button" class="button sn-save" data-season-add="{_e(entry["id"])}">'
                'Add to my library</button>')
    return (f'<button type="button" class="button sn-save" aria-pressed="false" data-guest-kind="{_e(entry["kind"])}" '
            f'data-guest-slug="{_e(entry["slug"])}" data-guest-title="{_e(entry["title"])}">'
            '<span class="sn-when-off">Save to my list</span><span class="sn-when-on">Saved to your list ✓</span></button>')


def _pick_html(entry: dict, item: dict, details: dict, signed_in: bool, today: date) -> str:
    pooled = seasonal.pool_entry(item)
    detail = details.get(pooled["id"], {}) if pooled else {}
    image = title_pages._safe_image(detail.get("image"))
    art = (f'<img class="sn-pick__art" src="{_e(image)}" alt="" width="96" height="144" loading="lazy" '
           'decoding="async" referrerpolicy="no-referrer">' if image
           else f'<span class="sn-pick__art sn-pick__art--letter" aria-hidden="true">{_e(item["title"][:1])}</span>')
    title_link = (f'<a class="sn-pick__link" href="{_e(detail["url"])}">See the title page</a>'
                  if detail.get("url") else "")
    save = _save_button(pooled, signed_in) if pooled else ""
    pick_id = _e(pooled["id"]) if pooled else ""
    return (
        f'<article class="pick sn-pick" id="{_e(seasonal.anchor_id(item))}" data-season-pick="{pick_id}">'
        f'<div class="sn-pick__head">{art}<div><p class="eyebrow">{_e(_meta_line(item))}</p>'
        f'<h3>{_e(item["title"])}</h3>{_level(entry, item["level"]) if "level" in item else ""}'
        f'{_release_line(item, today)}<p class="sn-pick__time">{_e(item["time"])}</p></div></div>'
        f'<p class="sn-pick__why">{_e(item["why"])}</p><p>{_e(item["note"])}</p>'
        f'<p class="caveat"><strong>Before you start:</strong> {_e(item["caveat"])}</p>'
        f'<div class="sn-pick__actions">{save}{title_link}'
        '<span class="sn-pick__owned" data-season-owned hidden></span></div>'
        '<p class="sn-pick__status" data-season-status role="status" aria-live="polite"></p></article>'
    )


def _shelf_html(entry: dict, shelf: dict, details: dict, signed_in: bool, today: date) -> str:
    ids = [pooled["id"] for pooled in (seasonal.pool_entry(item) for item in shelf["picks"]) if pooled]
    shelf_action = (f'<button type="button" class="button button--ghost sn-shelf__all" data-season-add-shelf="{_e(" ".join(ids))}">'
                    f'Add all {len(ids)} to my library</button>' if signed_in else "")
    if shelf.get("when"):
        eyebrow = shelf["when"]
    else:
        levels = [item["level"] for item in shelf["picks"]]
        eyebrow = f'{entry["scale_name"].upper()} {min(levels)} TO {max(levels)}'
    parts = [
        f'<section class="sn-shelf sn-shelf--{_e(shelf["key"])}" id="{_e(shelf["key"])}" aria-labelledby="shelf-{_e(shelf["key"])}">',
        f'<header class="sn-shelf__head"><p class="eyebrow">{_e(eyebrow)}</p>',
        f'<h2 id="shelf-{_e(shelf["key"])}">{_e(shelf["name"])}</h2><p class="sn-shelf__tagline">{_e(shelf["tagline"])}</p>',
        f'<div class="sn-shelf__intro">{_paragraphs(shelf["intro"])}</div>{shelf_action}',
        '<p class="sn-shelf__status" data-season-shelf-status role="status" aria-live="polite"></p></header>',
        '<div class="sn-picks">',
    ]
    parts.extend(_pick_html(entry, item, details, signed_in, today) for item in shelf["picks"])
    parts.append('</div></section>')
    return "".join(parts)


def _guest_bar(signed_in: bool) -> str:
    if signed_in:
        return ""
    return ('<div class="yl-bar sn-bar" data-guest-bar hidden><p class="yl-bar__count" data-guest-count role="status" aria-live="polite"></p>'
            '<a class="button" href="/#signup" data-season-signup>Save my list, free →</a></div>')


def _head(signed_in: bool) -> str:
    head = (f'<link rel="stylesheet" href="/static/if-you-liked.css?v={CSS_VERSION}">'
            f'<link rel="stylesheet" href="/static/seasonal.css?v={CSS_VERSION}">')
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
        head += '<script src="/static/ad-loader.js" defer></script>'
    head += f'<script src="/static/seasonal.js?v={JS_VERSION}" defer></script>'
    return head


def _related(slug: str, entry: dict, today: date) -> str:
    from ..discover_catalog import published_editions
    editions = published_editions(today)
    links = []
    public = challenges.public_months(today)
    year = seasonal.season_year(entry, today)
    for number in entry["related_months"]:
        name = date(year, int(number), 1).strftime("%B").lower()
        edition = f"{name}-{year}"
        if edition in editions:
            note = entry["edition_notes"].get(number) or "This month's Discover edition: six picks around one idea, across formats."
            links.append((f"/discover/monthly/{edition}", editions[edition]["name"], note))
        month = f"{year}-{number}"
        if month in public:
            links.append((f"/challenges/{challenges.slug_for(month)}", f"The {challenges.month_label(month)} challenge",
                          challenges.CHALLENGES[month]["tagline"]))
    links[:0] = [(extra["path"], extra["name"], extra["tagline"]) for extra in extra_links(slug)]
    links.extend((other["path"], f"{other['name']} picks", other["card"])
                 for other_slug, other in SEASONS.items() if other_slug != slug)
    links.extend([
        ("/if-you-liked", "If you liked…", "What to watch, play and read after a title you loved, across every format."),
        ("/pick", "Pick for me", f"Still undecided? Get one suggestion at a time, including these {entry['name']} picks."),
    ])
    cards = "".join(f'<article><h3><a href="{_e(href)}">{_e(name)}</a></h3><p>{_e(text)}</p></article>'
                    for href, name, text in links)
    return ('<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE TO READ</p>'
            f'<h2 id="related-heading">{_e(entry["related_heading"])}</h2><div class="guide-related-grid">{cards}</div></section>')


def hub_content(slug: str, entry: dict, details: dict, signed_in: bool, today: date) -> str:
    items = seasonal.picks(entry)
    formats = sorted({item["kind"] for item in items}, key=list(title_pages.KINDS).index)
    calendar = entry.get("calendar")
    jump = ""
    for shelf in entry["shelves"]:
        jump += f'<a href="#{_e(shelf["key"])}">{_e(shelf["name"])}</a>'
        if calendar and calendar["after"] == shelf["key"]:
            jump += f'<a href="#{_e(calendar["key"])}">{_e(calendar["label"])}</a>'
    progress = ('<section class="sn-progress" data-season-progress="' + _e(slug) + '" data-season-name="' + _e(entry["name"]) + '" aria-labelledby="sn-progress-title" hidden>'
                f'<p class="eyebrow">YOUR {_e(entry["name"].upper())}</p><h2 id="sn-progress-title" data-season-progress-title>Your progress</h2>'
                f'<div class="sn-meter" role="progressbar" aria-valuemin="0" aria-valuemax="{len(items)}" aria-valuenow="0" '
                'aria-labelledby="sn-progress-title" data-season-meter><span class="sn-meter__fill" data-season-meter-fill></span></div>'
                '<p class="sn-progress__text" data-season-progress-text></p></section>') if signed_in else ""
    scale = "".join(f'<li>{_level(entry, value)}<span class="sn-scale__text">{_e(text)}</span></li>'
                    for value, _, text in entry["scale"])
    nights = "".join(f'<li><h3>{_e(night["name"])}</h3><p>{_e(night["plan"])}</p></li>' for night in entry["nights"])
    faq = "".join(f'<details class="sn-faq__item"><summary>{_e(question)}</summary><p>{_e(answer)}</p></details>'
                  for question, answer in entry["faq"])
    reviewed = entry["reviewed"]
    parts = [
        f'<article class="trail-guide sn-hub" data-season-theme="{_e(entry["theme"])}">',
        '<header class="hero hero--guide sn-hero"><span class="sn-hero__moon" aria-hidden="true"></span>',
        f'<p class="eyebrow">SEASONAL · {_e(entry["name"].upper())} {seasonal.season_year(entry, today)}</p>',
        f'<h1>{_e(entry["headline"])}</h1><p class="guide-deck">{_e(entry["deck"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time> · '
        f'{len(items)} picks across {_e(", ".join(FORMAT_PLURALS[kind] for kind in formats))}</p>',
        f'<nav class="guide-jump" aria-label="Shelves">{jump}<a href="#plan">{_e(entry["plan_label"])}</a><a href="#faq">Questions</a></nav></header>',
        progress,
        f'<div class="guide-intro">{_paragraphs(entry["intro"])}</div>',
        f'<section class="sn-scale" aria-labelledby="scale-heading"><p class="eyebrow">{_e(entry["scale_eyebrow"])}</p>',
        f'<h2 id="scale-heading">{_e(entry["scale_heading"])}</h2><ol class="sn-scale__list">{scale}</ol></section>',
    ]
    if not signed_in:
        parts.append('<p class="yl-section-intro sn-guest-note">Save any pick to a list as you go, no account needed. '
                     'Your list moves into a free library when you sign up.</p>')
    for shelf in entry["shelves"]:
        parts.append(_shelf_html(entry, shelf, details, signed_in, today))
        if calendar and calendar["after"] == shelf["key"]:
            parts.append(_calendar_html(entry, today))
    sources = "".join(_source_link(label, url) for label, url in entry.get("sources", ()))
    parts.extend([
        _guest_bar(signed_in),
        f'<section id="plan" class="editorial sn-plan" aria-labelledby="plan-heading"><p class="eyebrow">{_e(entry["plan_label"].upper())}</p>'
        f'<h2 id="plan-heading">{_e(entry["plan_heading"])}</h2><ul class="sn-nights">{nights}</ul></section>',
        f'<section id="faq" class="editorial sn-faq" aria-labelledby="faq-heading"><h2 id="faq-heading">Questions</h2>{faq}</section>',
        _related(slug, entry, today),
        '<section class="guide-sources yl-method" aria-labelledby="method-heading"><h2 id="method-heading">How we chose</h2>',
        _paragraphs(entry["method"]),
        f'<h3>Sources we checked</h3><ul class="sn-sources">{sources}</ul>' if sources else "",
        f'<p class="muted">First published {_e(_long_date(entry["published"]))}. Checked {_e(_long_date(reviewed))}. '
        '<a href="/contact">Suggest a pick or send a correction</a> · <a href="/content-quality">Editorial standards</a></p>'
        '</section></article>',
    ])
    return "".join(parts)


def _companion_related(slug: str, entry: dict, today: date) -> str:
    """Cards under a guide beside a hub: the hub, its other guides, then this month's edition and challenge."""
    from ..discover_catalog import published_editions
    parent_slug = entry["parent"]
    parent = SEASONS[parent_slug]
    links = [(parent["path"], f"{parent['name']} picks", parent["card"])]
    links.extend((extra["path"], extra["name"], extra["tagline"]) for extra in extra_links(parent_slug)
                 if extra["path"] != entry["path"])
    editions = published_editions(today)
    public = challenges.public_months(today)
    year = seasonal.season_year(parent, today)
    number = f"{today.month:02d}" if f"{today.month:02d}" in parent["related_months"] else parent["related_months"][0]
    edition = f'{date(year, int(number), 1).strftime("%B").lower()}-{year}'
    if edition in editions:
        links.append((f"/discover/monthly/{edition}", editions[edition]["name"],
                      "This month's Discover edition: six picks around one idea, across formats."))
    month = f"{year}-{number}"
    if month in public:
        links.append((f"/challenges/{challenges.slug_for(month)}", f"The {challenges.month_label(month)} challenge",
                      challenges.CHALLENGES[month]["tagline"]))
    links.append(("/pick", "Pick for me", "Still undecided? Get one suggestion at a time from every guide on the site."))
    cards = "".join(f'<article><h3><a href="{_e(href)}">{_e(name)}</a></h3><p>{_e(text)}</p></article>'
                    for href, name, text in links)
    return ('<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE TO READ</p>'
            f'<h2 id="related-heading">{_e(entry["related_heading"])}</h2><div class="guide-related-grid">{cards}</div></section>')


def _calendar_html(entry: dict, today: date) -> str:
    """A guide's dated list of new releases (the Christmas guide, the Valentine's hub), grouped by month.

    A row links to its pick on the page when there is one, else to its write-up elsewhere (``href``), if any.
    """
    calendar = entry["calendar"]
    anchors = {item["title"]: seasonal.anchor_id(item) for item in seasonal.picks(entry)}
    months: dict[str, list[dict]] = {}
    for row in sorted(calendar["items"], key=lambda row: row["date"]):
        months.setdefault(row["date"][:7], []).append(row)
    groups = []
    for month, rows in months.items():
        items = []
        for row in rows:
            day = date.fromisoformat(row["date"])
            out = day <= today
            out_tag = ' <span class="sn-calendar__out">Out now</span>' if out else ""
            if row["title"] in anchors:
                title = f'<a href="#{_e(anchors[row["title"]])}">{_e(row["title"])}</a>'
            elif row.get("href"):
                title = f'<a href="{_e(row["href"])}">{_e(row["title"])}</a>'
            else:
                title = _e(row["title"])
            items.append(
                f'<li class="sn-calendar__row{" sn-calendar__row--out" if out else ""}">'
                f'<time class="sn-calendar__date" datetime="{_e(row["date"])}"><span>{day:%a}</span>'
                f'<strong>{day:%b} {day.day}</strong></time><div class="sn-calendar__body">'
                f'<p class="sn-calendar__title"><strong>{title}</strong> <span class="sn-calendar__format">{_e(row["format"])}</span>'
                f'{out_tag}</p>'
                f'<p class="sn-calendar__where">{_e(row["where"])}</p><p class="sn-calendar__note">{_e(row["note"])}</p></div></li>')
        name = date.fromisoformat(month + "-01").strftime("%B %Y")
        groups.append(f'<h3 class="sn-calendar__month">{_e(name)}</h3><ol class="sn-calendar__list">{"".join(items)}</ol>')
    return (f'<section id="{_e(calendar["key"])}" class="editorial sn-calendar" aria-labelledby="{_e(calendar["key"])}-heading">'
            f'<p class="eyebrow">{_e(calendar["eyebrow"])}</p><h2 id="{_e(calendar["key"])}-heading">{_e(calendar["heading"])}</h2>'
            f'<div class="sn-calendar__intro">{_paragraphs(calendar["intro"])}</div>{"".join(groups)}</section>')


def _source_link(label: str, url: str) -> str:
    host = urlsplit(url).hostname or ""
    return (f'<li><a href="{_e(url)}" rel="noopener" target="_blank">{_e(label)}</a>'
            f' <span class="muted">({_e(host.removeprefix("www."))})</span></li>')


def companion_content(slug: str, entry: dict, details: dict, signed_in: bool, today: date) -> str:
    """A guide beside a hub: the hub's shelves, plans and questions, without the festive scale."""
    items = seasonal.picks(entry)
    formats = sorted({item["kind"] for item in items}, key=list(title_pages.KINDS).index)
    parent = SEASONS[entry["parent"]]
    calendar = entry.get("calendar")
    jump = ""
    for shelf in entry["shelves"]:
        jump += f'<a href="#{_e(shelf["key"])}">{_e(shelf["name"])}</a>'
        if calendar and calendar["after"] == shelf["key"]:
            jump += f'<a href="#{_e(calendar["key"])}">{_e(calendar["label"])}</a>'
    progress = ('<section class="sn-progress" data-season-progress="' + _e(slug) + '" data-season-name="' + _e(entry["short"]) + '" aria-labelledby="sn-progress-title" hidden>'
                f'<p class="eyebrow">YOUR {_e(entry["short"].upper())} LIST</p><h2 id="sn-progress-title" data-season-progress-title>Your progress</h2>'
                f'<div class="sn-meter" role="progressbar" aria-valuemin="0" aria-valuemax="{len(items)}" aria-valuenow="0" '
                'aria-labelledby="sn-progress-title" data-season-meter><span class="sn-meter__fill" data-season-meter-fill></span></div>'
                '<p class="sn-progress__text" data-season-progress-text></p></section>') if signed_in else ""
    nights = "".join(f'<li><h3>{_e(night["name"])}</h3><p>{_e(night["plan"])}</p></li>' for night in entry["nights"])
    faq = "".join(f'<details class="sn-faq__item"><summary>{_e(question)}</summary><p>{_e(answer)}</p></details>'
                  for question, answer in entry["faq"])
    days = "".join(f'<li><a href="#{_e(shelf["key"])}"><span>{_e(shelf.get("day") or shelf["when"].title())}</span>'
                   f'<strong>{_e(shelf["name"])}</strong></a></li>' for shelf in entry["shelves"])
    reviewed = entry["reviewed"]
    parts = [
        f'<article class="trail-guide sn-hub sn-companion" data-season-theme="{_e(entry["theme"])}">',
        '<header class="hero hero--guide sn-hero"><span class="sn-hero__moon" aria-hidden="true"></span>',
        f'<p class="eyebrow">SEASONAL · {_e(entry["eyebrow"])}</p>',
        f'<h1>{_e(entry["headline"])}</h1><p class="guide-deck">{_e(entry["deck"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time> · '
        f'{len(items)} picks across {_e(", ".join(FORMAT_PLURALS[kind] for kind in formats))}</p>',
        f'<nav class="guide-jump" aria-label="Shelves">{jump}<a href="#plan">{_e(entry["plan_label"])}</a><a href="#faq">Questions</a></nav>',
        f'<p class="sn-companion__parent">Part of the <a href="{_e(parent["path"])}">{_e(parent["name"].lower())} picks</a>.</p></header>',
        progress,
        f'<div class="guide-intro">{_paragraphs(entry["intro"])}</div>',
        f'<ol class="sn-days" aria-label="The shelves in order">{days}</ol>',
    ]
    if not signed_in:
        parts.append('<p class="yl-section-intro sn-guest-note">Save any pick to a list as you go, no account needed. '
                     'Your list moves into a free library when you sign up.</p>')
    for shelf in entry["shelves"]:
        parts.append(_shelf_html(entry, shelf, details, signed_in, today))
        if calendar and calendar["after"] == shelf["key"]:
            parts.append(_calendar_html(entry, today))
    sources = "".join(_source_link(label, url) for label, url in entry.get("sources", ()))
    parts.extend([
        _guest_bar(signed_in),
        f'<section id="plan" class="editorial sn-plan" aria-labelledby="plan-heading"><p class="eyebrow">{_e(entry["plan_label"].upper())}</p>'
        f'<h2 id="plan-heading">{_e(entry["plan_heading"])}</h2><ul class="sn-nights">{nights}</ul></section>',
        f'<section id="faq" class="editorial sn-faq" aria-labelledby="faq-heading"><h2 id="faq-heading">Questions</h2>{faq}</section>',
        _companion_related(slug, entry, today),
        '<section class="guide-sources yl-method" aria-labelledby="method-heading"><h2 id="method-heading">How we chose</h2>',
        _paragraphs(entry["method"]),
        f'<h3>Sources we checked</h3><ul class="sn-sources">{sources}</ul>' if sources else "",
        f'<p class="muted">First published {_e(_long_date(entry["published"]))}. Checked {_e(_long_date(reviewed))}. '
        '<a href="/contact">Suggest a pick or send a correction</a> · <a href="/content-quality">Editorial standards</a></p>'
        '</section></article>',
    ])
    return "".join(parts)


def _structured(entry: dict) -> dict:
    url = SITE + entry["path"]
    return {"@context": "https://schema.org", "@graph": [
        {
            "@type": "Article", "headline": entry["headline"], "description": entry["summary"],
            "datePublished": entry["published"], "dateModified": entry["reviewed"],
            "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
            "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
            "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(seasonal.picks(entry)), "itemListElement": [
                {"@type": "ListItem", "position": index, "name": item["title"], "url": f"{url}#{seasonal.anchor_id(item)}"}
                for index, item in enumerate(seasonal.picks(entry), 1)
            ]},
        },
        {
            "@type": "FAQPage", "url": url + "#faq", "mainEntity": [
                {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
                for question, answer in entry["faq"]
            ],
        },
    ]}


def _hub(slug: str):
    def view(request: Request, db: Session = Depends(get_db)):
        entry = SEASONS[slug]
        signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
        content = hub_content(slug, entry, _details(db), signed_in, date.today())
        response = page(entry["search_title"], entry["summary"], entry["path"], content,
                        structured_data=_structured(entry), head=_head(signed_in))
        response.headers["Cache-Control"] = "private, no-cache"
        response.headers["Vary"] = "Cookie"
        return response
    view.__name__ = f"seasonal_{slug}"
    return view


def _companion(slug: str):
    def view(request: Request, db: Session = Depends(get_db)):
        entry = seasonal.companion(slug)
        signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
        content = companion_content(slug, entry, _details(db), signed_in, date.today())
        response = page(entry["search_title"], entry["summary"], entry["path"], content,
                        structured_data=_structured(entry), head=_head(signed_in))
        response.headers["Cache-Control"] = "private, no-cache"
        response.headers["Vary"] = "Cookie"
        return response
    view.__name__ = f"holiday_guide_{slug.replace('-', '_')}"
    return view


for _slug, _entry in SEASONS.items():
    router.add_api_route(_entry["path"], _hub(_slug), methods=["GET"], include_in_schema=False)
for _slug, _entry in seasonal.COMPANIONS.items():
    router.add_api_route(_entry["path"], _companion(_slug), methods=["GET"], include_in_schema=False)


# ---------------------------------------------------------------- member API

def _season_or_404(slug: str) -> dict:
    entry = seasonal.season(slug)
    if entry is None:
        raise HTTPException(404, "Season not found")
    return entry


@router.get("/api/seasonal/current")
def seasonal_current(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The season running today, with the member's progress, for the dashboard card ({"season": null} otherwise)."""
    response.headers["Cache-Control"] = "private, no-store"
    slug = seasonal.current()
    if slug is None:
        return {"season": None}
    entry = SEASONS[slug]
    progress = seasonal.progress(db, user.id, slug)
    return {
        "season": slug, "name": entry["name"], "theme": entry["theme"], "path": entry["path"],
        "year": date.today().year, "card": entry["card"], "cta": entry["card_cta"], "days_left": seasonal.days_left(entry),
        "shelves": [{"key": shelf["key"], "name": shelf["name"], "tagline": shelf["tagline"]} for shelf in entry["shelves"]],
        "total": progress["total"], "tracked": progress["tracked"], "done": progress["done"],
        "links": extra_links(slug),
    }


@router.get("/api/seasonal/{slug}/progress")
def seasonal_progress(slug: str, request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Which of the season's picks are in the member's library, read from the library itself."""
    response.headers["Cache-Control"] = "private, no-store"
    _season_or_404(slug)
    return seasonal.progress(db, user.id, slug)


class SeasonalAdd(BaseModel):
    ids: list[str] = Field(..., min_length=1, max_length=MAX_ADD)


@router.post("/api/seasonal/{slug}/add")
def seasonal_add(slug: str, payload: SeasonalAdd, request: Request, response: Response,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add picks from a season to the member's library as not started (title, year and creator only)."""
    response.headers["Cache-Control"] = "private, no-store"
    entry = _season_or_404(slug)
    known = {pooled["id"]: pooled for pooled in (seasonal.pool_entry(item) for item in seasonal.picks(entry)) if pooled}
    if any(pick_id not in known for pick_id in payload.ids):
        raise HTTPException(404, "Pick not found")
    lock_progress_owner(db, user.id)
    owned = seasonal.progress(db, user.id, slug)["entries"]
    details = _details(db)
    added, existing = [], []
    for pick_id in dict.fromkeys(payload.ids):
        if pick_id in owned:
            existing.append({"id": pick_id, "title": known[pick_id]["title"]})
            continue
        chosen = known[pick_id]
        if "browse_kind" in chosen:  # A manga, podcast or audiobook pick: straight to its tracker.
            state, record = browse.add_to_library(db, user, chosen["browse_kind"], chosen, details.get(pick_id, {}).get("image"))
        else:
            state, record = pick.add_to_library(db, user, chosen, details.get(pick_id, {}).get("image"))
        (added if state == "created" else existing).append({"id": pick_id, "title": record.title})
    db.commit()
    if added:
        funnel.record("seasonal_saved", request)
    return {"added": added, "existing": existing, "progress": seasonal.progress(db, user.id, slug)}
