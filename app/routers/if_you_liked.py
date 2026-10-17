"""Public "If you liked..." guides (/if-you-liked and /if-you-liked/<slug>).

Hand-written recommendations for after a well-loved title, across formats. Pages
read completely without scripts or an account. Saving a pick reuses Pick for me:
members add it through POST /api/pick/add, visitors keep it in their browser-only
guest list until they sign up.
"""
from __future__ import annotations

from datetime import date
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import if_you_liked, pick, title_pages, title_search
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_db
from ..if_you_liked_guides import GUIDES
from .discover import page

router = APIRouter(tags=["if-you-liked"])
CSS_VERSION = "20261016-liked-1"
JS_VERSION = "20261016-liked-1"
GUEST_LIST_JS = "/static/guest-list.js?v=20261012-hero-search-1"
SITE = "https://omnitrackr.xyz"
FIRST_PUBLISHED = "2026-10-16"
HUB_TITLE = "If you liked it: what to watch, play and read next"
HUB_DESCRIPTION = ("Finished something you loved? Guides to what to watch, play, read or hear next "
                   "after Interstellar, Stranger Things, Breaking Bad, Jujutsu Kaisen, Frieren and more.")
GROUP_HEADINGS = {"movie": "After a movie", "tv": "After a TV show", "anime": "After an anime",
                  "game": "After a game", "book": "After a book", "album": "After an album"}
FORMAT_PLURALS = {"movie": "movies", "tv": "TV shows", "anime": "anime", "game": "games", "book": "books", "album": "albums"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


def _details(db: Session) -> dict:
    """{pool id: {"url", "image"}} for picks with a public title page (never raises)."""
    try:
        return pick.title_details(title_search.index(db))
    except Exception:
        return {}


def _anchor_page(db: Session, anchor: dict):
    """The anchor's own title page (url, image) when members track it."""
    try:
        wanted = (anchor["kind"], title_pages.slugify(anchor["title"]))
        best = None
        for entry in title_search.index(db):
            if (entry["kind"], entry["base"]) == wanted and (best is None or entry["members"] > best["members"]):
                best = entry
        return (f"/titles/{best['kind']}/{best['slug']}", best.get("image")) if best else (None, None)
    except Exception:
        return None, None


def _meta_line(item: dict) -> str:
    parts = [title_pages.KINDS[item["kind"]][3]]
    if item["year"]:
        parts.append(str(item["year"]))
    if item["creator"]:
        parts.append(item["creator"])
    return " · ".join(parts)


def _save_button(entry: dict, signed_in: bool) -> str:
    if signed_in:
        return (f'<button type="button" class="button yl-save" data-liked-add="{_e(entry["id"])}">'
                'Add to my library</button>')
    return (f'<button type="button" class="button yl-save" aria-pressed="false" data-guest-kind="{_e(entry["kind"])}" '
            f'data-guest-slug="{_e(entry["slug"])}" data-guest-title="{_e(entry["title"])}">'
            '<span class="yl-when-off">Save to my list</span><span class="yl-when-on">Saved to your list ✓</span></button>')


def _pick_html(index: int, item: dict, threads: list, details: dict, signed_in: bool) -> str:
    entry = if_you_liked.pool_entry(item)
    detail = details.get(entry["id"], {}) if entry else {}
    image = title_pages._safe_image(detail.get("image"))
    art = (f'<img class="yl-pick__art" src="{_e(image)}" alt="" width="96" height="144" loading="lazy" '
           'decoding="async" referrerpolicy="no-referrer">' if image else "")
    title_link = (f'<a class="yl-pick__link" href="{_e(detail["url"])}">See the title page</a>'
                  if detail.get("url") else "")
    save = _save_button(entry, signed_in) if entry else ""
    thread = threads[item["match"]][0]
    anchor_id = "pick-" + title_pages.slugify(item["title"])
    return (
        f'<article class="pick yl-pick" id="{_e(anchor_id)}">'
        f'<div class="yl-pick__head">{art}<div><p class="eyebrow">{index:02d} / {_e(_meta_line(item))}</p>'
        f'<h3>{_e(item["title"])}</h3><p class="yl-pick__match">Matches: {_e(thread)}</p></div></div>'
        f'<p class="yl-pick__why">{_e(item["why"])}</p><p>{_e(item["note"])}</p>'
        f'<p class="caveat">{_e(item["caveat"])}</p>'
        f'<div class="yl-pick__actions">{save}{title_link}</div>'
        '<p class="yl-pick__status" data-liked-status role="status" aria-live="polite"></p></article>'
    )


def _guest_bar(signed_in: bool) -> str:
    if signed_in:
        return ""
    return ('<div class="yl-bar" data-guest-bar hidden><p class="yl-bar__count" data-guest-count role="status" aria-live="polite"></p>'
            '<a class="button" href="/#signup" data-liked-signup>Save my list, free →</a></div>')


def _head(signed_in: bool, ads: bool) -> str:
    head = f'<link rel="stylesheet" href="/static/if-you-liked.css?v={CSS_VERSION}">'
    if not signed_in:
        head += f'<script src="{GUEST_LIST_JS}" defer></script>'
    head += f'<script src="/static/if-you-liked.js?v={JS_VERSION}" defer></script>'
    if ads and not signed_in:
        head += '<script src="/static/ad-loader.js" defer></script>'
    return head


def guide_content(slug: str, entry: dict, details: dict, anchor_url, signed_in: bool) -> str:
    anchor = entry["anchor"]
    kind_label = title_pages.KINDS[anchor["kind"]][3]
    reviewed = entry["reviewed"]
    threads = entry["threads"]
    anchor_link = (f' · <a href="{_e(anchor_url)}">{_e(anchor["title"])} on OmniTrackr</a>' if anchor_url else "")
    formats = ", ".join(FORMAT_PLURALS[kind] for kind in if_you_liked.formats(entry))
    parts = [
        '<article class="trail-guide yl-guide">',
        f'<header class="hero hero--guide"><a href="{if_you_liked.BASE_PATH}">← Every "If you liked" guide</a>',
        f'<p class="eyebrow">IF YOU LIKED · {_e(kind_label.upper())}</p>',
        f'<h1>If you liked {_e(anchor["title"])}</h1><p class="guide-deck">{_e(entry["summary"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time>{anchor_link}</p>',
        '<nav class="guide-jump" aria-label="On this page"><a href="#what-it-did">What made it work</a>',
        '<a href="#picks">The picks</a><a href="#where-to-start">Where to start</a><a href="#method">How we chose</a></nav></header>',
        f'<div class="guide-intro">{_paragraphs(entry["lead"])}</div>',
        '<section id="what-it-did" class="yl-threads" aria-labelledby="threads-heading">',
        f'<p class="eyebrow">WHAT WE MATCHED ON</p><h2 id="threads-heading">Three things {_e(anchor["title"])} does well</h2><ol>',
    ]
    for name, text in threads:
        parts.append(f'<li><strong>{_e(name)}</strong><span>{_e(text)}</span></li>')
    parts.extend([
        '</ol></section>',
        '<section id="picks" aria-labelledby="picks-heading"><p class="eyebrow">THE PICKS</p>',
        f'<h2 id="picks-heading">{len(entry["picks"])} things to try next</h2>',
        f'<p class="yl-section-intro">Across {_e(formats)}. Each pick says which of the three it matches, what it does '
        'differently, and one thing to know before you start.'
        + ('' if signed_in else ' Save any of them to a list, no account needed.') + '</p>',
        '<div class="picks yl-picks">',
    ])
    for index, item in enumerate(entry["picks"], 1):
        parts.append(_pick_html(index, item, threads, details, signed_in))
    parts.extend([
        '</div></section>', _guest_bar(signed_in),
        '<section id="where-to-start" class="editorial yl-start"><h2>Where to start</h2>', _paragraphs(entry["start"]),
        '<p>Whatever you pick, give it a fair start: the first half hour of a film, two episodes of a show, the opening '
        'chapters of a book or the first hour of a game. Then decide.</p></section>',
        '<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE GUIDES</p>',
        '<h2 id="related-heading">If you liked something else</h2><div class="guide-related-grid">',
    ])
    for other in if_you_liked.related(slug):
        target = GUIDES[other]
        parts.append(f'<article><h3><a href="{if_you_liked.path(other)}">If you liked {_e(target["anchor"]["title"])}</a></h3>'
                     f'<p>{_e(target["summary"])}</p></article>')
    parts.extend([
        '</div></section>',
        '<section id="method" class="guide-sources yl-method" aria-labelledby="method-heading">',
        '<h2 id="method-heading">How we chose</h2>',
        f'<p>Prepared by OmniTrackr with AI assistance. We started from what makes {_e(anchor["title"])} '
        'work for the people who love it, then looked for titles that share at least one of those qualities, '
        'deliberately across formats, because a game or a book can carry the same feeling in a different way. '
        'Facts were checked against public sources; the comparisons and caveats are editorial opinion.</p>',
        '<p>These picks are not rankings, sponsored placements or anyone\'s private ratings. Running times, episode counts and '
        'availability vary by edition and region. Links go to OmniTrackr title pages, not shops.</p>',
        f'<p class="muted">First published {_e(_long_date(FIRST_PUBLISHED))}. Checked {_e(_long_date(reviewed))}. '
        '<a href="/contact">Suggest a pick or send a correction</a> · <a href="/content-quality">Editorial standards</a> · '
        '<a href="/pick">Pick for me</a></p></section></article>',
    ])
    return "".join(parts)


def _structured(slug: str, entry: dict) -> dict:
    url = SITE + if_you_liked.path(slug)
    return {
        "@context": "https://schema.org", "@type": "Article",
        "headline": f"If you liked {entry['anchor']['title']}", "description": entry["summary"],
        "datePublished": FIRST_PUBLISHED, "dateModified": entry["reviewed"],
        "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
        "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
        "about": {"@type": "CreativeWork", "name": entry["anchor"]["title"]},
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(entry["picks"]), "itemListElement": [
            {"@type": "ListItem", "position": index, "name": item["title"],
             "url": f"{url}#pick-{title_pages.slugify(item['title'])}"}
            for index, item in enumerate(entry["picks"], 1)
        ]},
    }


@router.get(if_you_liked.BASE_PATH, include_in_schema=False)
def if_you_liked_index(request: Request, db: Session = Depends(get_db)):
    groups = []
    for kind in if_you_liked.KIND_ORDER:
        slugs = [slug for slug, entry in GUIDES.items() if entry["anchor"]["kind"] == kind]
        if not slugs:
            continue
        cards = []
        for slug in slugs:
            entry = GUIDES[slug]
            _, image = _anchor_page(db, entry["anchor"])
            image = title_pages._safe_image(image)
            art = (f'<img src="{_e(image)}" alt="" width="72" height="108" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
                   if image else f'<span class="yl-card__initial" aria-hidden="true">{_e(entry["anchor"]["title"][:1])}</span>')
            picks = " · ".join(item["title"] for item in entry["picks"][:4])
            cards.append(
                f'<li><a class="yl-card" href="{if_you_liked.path(slug)}"><span class="yl-card__art">{art}</span>'
                f'<span class="yl-card__text"><strong>If you liked {_e(entry["anchor"]["title"])}</strong>'
                f'<span>{len(entry["picks"])} picks, including {_e(picks)}</span></span></a></li>'
            )
        groups.append(f'<section class="yl-group" aria-labelledby="yl-{kind}"><h2 id="yl-{kind}">{_e(GROUP_HEADINGS[kind])}</h2>'
                      f'<ul class="yl-cards">{"".join(cards)}</ul></section>')
    content = (
        '<header class="hero"><p class="eyebrow">IF YOU LIKED</p><h1>Loved it? Here is what to try next.</h1>'
        '<p>Guides to what to watch, play, read or hear after a title you loved. Each one names what made it '
        'work, then picks things that share it, across movies, shows, anime, games, books and music.</p></header>'
        + "".join(groups)
        + '<section class="editorial yl-why"><h2>Why mix formats?</h2><p>The feeling you are chasing after a great story is rarely tied to '
          'its format. The awe of Interstellar can come back in a puzzle game, and the grief at the heart of Frieren lives '
          'in a novel about an English butler. Every guide includes at least three formats, with a caveat for each pick so '
          'you know what you are getting into.</p><p>Not sure where to begin at all? <a href="/pick">Pick for me</a> '
          'suggests one title at a time from these guides and the <a href="/discover">Discover trails</a>.</p></section>'
    )
    structured = {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": HUB_TITLE, "description": HUB_DESCRIPTION,
        "url": SITE + if_you_liked.BASE_PATH, "inLanguage": "en-US",
        "isPartOf": {"@type": "WebSite", "name": "OmniTrackr", "url": SITE + "/"},
        "mainEntity": {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": index, "name": f"If you liked {entry['anchor']['title']}",
             "url": SITE + if_you_liked.path(slug)}
            for index, (slug, entry) in enumerate(GUIDES.items(), 1)
        ]},
    }
    response = page(HUB_TITLE, HUB_DESCRIPTION, if_you_liked.BASE_PATH, content, structured_data=structured,
                    head=f'<link rel="stylesheet" href="/static/if-you-liked.css?v={CSS_VERSION}">')
    response.headers["Cache-Control"] = "public, max-age=600"
    return response


@router.get(if_you_liked.BASE_PATH + "/{slug}", include_in_schema=False)
def if_you_liked_guide(slug: str, request: Request, db: Session = Depends(get_db)):
    entry = if_you_liked.guide(slug)
    if entry is None:
        raise HTTPException(404, "Guide not found")
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    anchor_url, _ = _anchor_page(db, entry["anchor"])
    content = guide_content(slug, entry, _details(db), anchor_url, signed_in)
    response = page(entry["search_title"], entry["summary"], if_you_liked.path(slug), content,
                    structured_data=_structured(slug, entry), head=_head(signed_in, ads=True))
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response
