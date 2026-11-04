"""The holiday gift guide (/holidays/gifts) and members' shareable gift lists (/gifts/<token>).

The guide reads completely without scripts or an account. Signed-in members get it
sorted by what they track most, see which gifts they already have, and build a gift
list in the panel near the top (gift-guide.js). The shared list page shows the
member's wishes with Amazon search links and lets anyone with the link mark a gift as
taken; the member who owns the list is never shown which.
"""
from __future__ import annotations

from datetime import date
from html import escape
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import affiliate, funnel, gift_lists, models, title_pages, title_search
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..gift_guides import GIFTS, GUIDE, SECTIONS, SIZE_LABELS
from ..integer_bounds import PositiveDatabaseId
from ..progress import lock_progress_owner
from ..site_chrome import message_page
from .discover import page

router = APIRouter(tags=["gift-guide"])
CSS_VERSION = "20261104-gifts-1"
JS_VERSION = "20261104-gifts-1"
SITE = "https://omnitrackr.xyz"
SIGNUP_NEXT = quote(GUIDE["path"], safe="")
STORE_LABELS = {"audible": "Find it on Audible"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _paragraphs(values) -> str:
    return "".join(f"<p>{_e(value)}</p>" for value in values)


def _long_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


def _private(response: Response) -> Response:
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _head(*, ads: bool) -> str:
    head = (f'<link rel="stylesheet" href="/static/if-you-liked.css?v={CSS_VERSION}">'
            f'<link rel="stylesheet" href="/static/seasonal.css?v=20261022-holidays-1">'
            f'<link rel="stylesheet" href="/static/gift-guide.css?v={CSS_VERSION}">')
    if ads:
        head += '<script src="/static/ad-loader.js" defer></script>'
    return head + f'<script src="/static/gift-guide.js?v={JS_VERSION}" defer></script>'


# ---------------------------------------------------------------- title pages and art for guide gifts

def _title_pages(db: Session) -> dict[str, dict]:
    """{gift id: {"url", "image"}} for guide gifts that are titles with a public page (never raises)."""
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
    for gift_id, gift in GIFTS.items():
        if gift["kind"] not in title_pages.KINDS or not gift.get("title"):
            continue
        base = title_pages.slugify(gift["title"])
        match = by_slug.get((gift["kind"], f"{base}-{gift['year']}")) or by_base.get((gift["kind"], base))
        if match and (match["year"] is None or abs(match["year"] - gift["year"]) <= 1):
            found[gift_id] = {"url": f"/titles/{match['kind']}/{match['slug']}", "image": match.get("image")}
    return found


def _art(title: str, image: Optional[str], css: str) -> str:
    image = title_pages._safe_image(image)
    if image:
        return (f'<img class="{css}" src="{_e(image)}" alt="" width="96" height="144" loading="lazy" decoding="async" '
                'referrerpolicy="no-referrer">')
    return f'<span class="{css} gg-box" aria-hidden="true"><span>{_e(title[:1].upper())}</span></span>'


def _buy_button(links: list[dict], label: Optional[str] = None) -> str:
    return "".join(
        f'<a class="button gg-buy" href="{_e(link["url"])}" target="_blank" rel="sponsored noopener noreferrer" '
        f'data-gift-buy>{_e(label or link["label"])} <span aria-hidden="true">↗</span></a>'
        for link in links)


# ---------------------------------------------------------------- the guide

def _meta(gift: dict) -> str:
    if gift["kind"] in title_pages.KINDS and gift.get("title"):
        parts = [title_pages.KINDS[gift["kind"]][3], str(gift["year"])]
        if gift.get("creator"):
            parts.append(gift["creator"])
        return " · ".join(parts)
    return ""


def _gift_html(gift: dict, pages: dict, owned: dict, signed_in: bool) -> str:
    detail = pages.get(gift["id"], {})
    links = affiliate.search_links(gift["search"], gift["store"])
    buy = _buy_button(links, STORE_LABELS.get(gift["store"]))
    add = (f'<button type="button" class="button button--ghost gg-add" data-gift-add-guide="{_e(gift["id"])}">'
           'Add to my gift list</button>') if signed_in else ""
    title_link = (f'<a class="gg-gift__link" href="{_e(detail["url"])}">See the title page</a>'
                  if detail.get("url") else "")
    more = (f'<a class="gg-gift__link" href="{_e(gift["more"][0])}">{_e(gift["more"][1])}</a>'
            if gift.get("more") else "")
    have = ""
    if gift["id"] in owned:
        have = (f'<span class="gg-owned">{"You’ve finished this one" if owned[gift["id"]] else "In your library"}</span>')
    meta = _meta(gift)
    return (
        f'<article class="gg-gift" id="gift-{_e(gift["id"])}">'
        f'<div class="gg-gift__head">{_art(gift["name"], detail.get("image"), "gg-gift__art")}<div>'
        f'<p class="gg-size gg-size--{_e(gift["size"])}">{_e(SIZE_LABELS[gift["size"]])}</p>'
        f'<h3>{_e(gift["name"])}</h3>'
        + (f'<p class="gg-gift__meta">{_e(meta)}</p>' if meta else "")
        + f'{have}</div></div>'
        f'<p class="gg-gift__why">{_e(gift["why"])}</p>'
        f'<p class="gg-gift__for"><strong>Good for:</strong> {_e(gift["for"])}</p>'
        f'<p class="caveat"><strong>Before you buy:</strong> {_e(gift["check"])}</p>'
        f'<div class="gg-gift__actions">{buy}{add}{title_link}{more}</div>'
        '<p class="gg-gift__status" data-gift-status role="status" aria-live="polite"></p></article>'
    )


def _section_html(section: dict, pages: dict, owned: dict, signed_in: bool) -> str:
    gifts = "".join(_gift_html(gift, pages, owned, signed_in) for gift in section["gifts"])
    return (
        f'<section class="sn-shelf gg-section" id="{_e(section["key"])}" aria-labelledby="section-{_e(section["key"])}">'
        f'<header class="sn-shelf__head"><p class="eyebrow">{len(section["gifts"])} GIFT IDEAS</p>'
        f'<h2 id="section-{_e(section["key"])}">{_e(section["name"])}</h2>'
        f'<p class="sn-shelf__tagline">{_e(section["tagline"])}</p>'
        f'<div class="sn-shelf__intro">{_paragraphs(section["intro"])}</div></header>'
        f'<div class="gg-gifts">{gifts}</div></section>'
    )


def ordered_sections(counts: Optional[dict]) -> list[dict]:
    """The guide's sections, most-tracked format first for a member; page order otherwise."""
    if not counts or not any(counts.values()):
        return list(SECTIONS)
    return sorted(SECTIONS, key=lambda section: -counts.get(section["kind"], 0))


def _member_panel() -> str:
    return (
        '<section id="gift-list" class="gg-panel" data-gift-panel aria-labelledby="gift-list-title">'
        '<p class="eyebrow">YOUR GIFT LIST</p><h2 id="gift-list-title">Make a list for the family</h2>'
        '<p class="gg-panel__lead">Pick gifts from your library or from this guide, or type anything you like. Add a '
        'note such as "the 4K one, please", then send the link. Whoever opens it can mark a gift as theirs, and '
        'you never see which.</p>'
        '<div class="gg-panel__grid">'
        '<div class="gg-list"><h3>On your list <span class="gg-count" data-gift-count></span></h3>'
        '<ul class="gg-items" data-gift-items><li class="gg-muted">Loading your list…</li></ul>'
        '<form class="gg-text" data-gift-text><label for="giftText">Add something else</label>'
        '<div class="gg-text__row"><input id="giftText" name="text" type="text" maxlength="120" autocomplete="off" '
        'placeholder="A book light, Dune on 4K, a Steam gift card…" required>'
        '<button type="submit" class="button">Add</button></div></form>'
        '<div class="gg-share" data-gift-share hidden><h3>Send it</h3>'
        '<label for="giftLink">Your list\'s link</label><div class="gg-text__row">'
        '<input id="giftLink" type="text" readonly data-gift-link>'
        '<button type="button" class="button" data-gift-copy>Copy link</button></div>'
        '<p class="gg-share__actions"><a class="gg-gift__link" data-gift-open href="#" target="_blank" rel="noopener">See it as family will</a>'
        '<button type="button" class="gg-linkbutton" data-gift-native-share hidden>Share…</button></p>'
        '<label for="giftMessage">A note at the top <span class="gg-muted">(optional)</span></label>'
        '<div class="gg-text__row"><input id="giftMessage" type="text" maxlength="200" autocomplete="off" '
        'placeholder="Anything from here would be lovely. No socks!" data-gift-message>'
        '<button type="button" class="button button--ghost" data-gift-message-save>Save note</button></div>'
        '<label class="gg-check"><input type="checkbox" data-gift-shared> The link works (untick to switch it off)</label>'
        '<button type="button" class="gg-linkbutton" data-gift-reset>Make a new link and retire this one</button></div>'
        '<p class="gg-status" data-gift-panel-status role="status" aria-live="polite"></p></div>'
        '<div class="gg-ideas"><h3>Ideas from your library</h3>'
        '<p class="gg-muted" data-gift-ideas-empty hidden>Add titles to your library and the ones you haven\'t started will '
        'show up here.</p>'
        '<div data-gift-ideas="waiting"><h4>Still on your to-do list</h4><ul class="gg-ideas__list"></ul></div>'
        '<div data-gift-ideas="favourites"><h4>Favourites you might want to own</h4><ul class="gg-ideas__list"></ul></div>'
        '</div></div><noscript><p>The gift list needs JavaScript. The guide below works without it.</p></noscript></section>'
    )


def _guest_promo() -> str:
    return (
        '<section id="gift-list" class="gg-panel gg-promo" aria-labelledby="gift-promo-title">'
        '<p class="eyebrow">IF YOU\'RE THE FAN</p><h2 id="gift-promo-title">Send the family a gift list from your library</h2>'
        '<ol class="gg-steps">'
        '<li>Track what you watch, play, read and listen to on OmniTrackr, or bring it over from Letterboxd, Goodreads, '
        'Steam and other services.</li>'
        '<li>Pick gifts from the titles you haven\'t started, the favourites you\'d like to own, or this guide.</li>'
        '<li>Send one link. People mark what they\'re getting so nobody doubles up, and you never see which.</li></ol>'
        f'<p class="gg-promo__actions"><a class="button" href="/?next={SIGNUP_NEXT}#signup" data-gift-signup>'
        'Make my gift list, free</a>'
        f'<a class="gg-gift__link" href="/?next={SIGNUP_NEXT}#login">I already have an account</a></p></section>'
    )


def _related(today: date) -> str:
    links = [
        ("/holidays", "Holiday picks", "Twenty-four movies, shows, anime, games, books and albums for the break, "
                                       "sorted by how festive they are."),
    ]
    try:
        from .. import release_guides
        for slug, guide in release_guides.GUIDES.items():
            if guide["published"] <= today.isoformat() and guide.get("ends", "9999") >= today.isoformat():
                links.append((f"/new-releases/{slug}", guide["name"], guide["summary"]))
    except Exception:
        pass
    links.extend([
        ("/best-of", "The best of every format", "Our shortlists of the best movies, shows, anime, games, books and albums."),
        ("/if-you-liked", "If you liked…", "What to watch, play and read after a title you loved, across every format."),
    ])
    cards = "".join(f'<article><h3><a href="{_e(href)}">{_e(name)}</a></h3><p>{_e(text)}</p></article>'
                    for href, name, text in links[:5])
    return ('<section class="guide-related" aria-labelledby="related-heading"><p class="eyebrow">MORE TO READ</p>'
            f'<h2 id="related-heading">More for the season</h2><div class="guide-related-grid">{cards}</div></section>')


def guide_content(*, pages: dict, signed_in: bool, counts: Optional[dict] = None,
                  owned: Optional[dict] = None, today: Optional[date] = None) -> str:
    today = today or date.today()
    owned = owned or {}
    sections = ordered_sections(counts if signed_in else None)
    total = sum(len(section["gifts"]) for section in SECTIONS)
    def short(name: str) -> str:
        name = name.replace("For the ", "")
        return name[:1].upper() + name[1:]
    jump = "".join(f'<a href="#{_e(section["key"])}">{_e(short(section["name"]))}</a>' for section in sections)
    sizes = "".join(f'<li><span class="gg-size gg-size--{_e(key)}">{_e(label)}</span> <span>{_e(text)}</span></li>'
                    for key, label, text in GUIDE["sizes"])
    faq = "".join(f'<details class="sn-faq__item"><summary>{_e(question)}</summary><p>{_e(answer)}</p></details>'
                  for question, answer in GUIDE["faq"])
    sorted_note = ""
    if signed_in and counts and any(counts.values()) and sections[0] is not SECTIONS[0]:
        sorted_note = (f'<p class="gg-sorted">Sorted for you: {_e(sections[0]["name"].replace("For the ", "the ").lower())} '
                       'section comes first because that\'s what you track most.</p>')
    reviewed = GUIDE["reviewed"]
    parts = [
        '<article class="trail-guide sn-hub gg-guide" data-season-theme="holiday">',
        '<header class="hero hero--guide sn-hero"><span class="sn-hero__moon" aria-hidden="true"></span>',
        f'<p class="eyebrow">HOLIDAY GIFT GUIDE {today.year}</p>',
        f'<h1>{_e(GUIDE["headline"])}</h1><p class="guide-deck">{_e(GUIDE["deck"])}</p>',
        '<p class="guide-byline">By <a href="/about">OmniTrackr</a> · Updated ',
        f'<time datetime="{_e(reviewed)}">{_e(_long_date(reviewed))}</time> · {total} gift ideas for nine kinds of fan</p>',
        affiliate.disclosure_html("gg-disclosure"),
        f'<nav class="guide-jump" aria-label="Sections"><a href="#gift-list">Gift lists</a>{jump}<a href="#faq">Questions</a></nav></header>',
        f'<div class="guide-intro">{_paragraphs(GUIDE["intro"])}</div>',
        _member_panel() if signed_in else _guest_promo(),
        '<section class="gg-sizes" aria-labelledby="sizes-heading"><p class="eyebrow">HOW BIG A GIFT</p>'
        f'<h2 id="sizes-heading">Three sizes, no prices</h2><ul class="gg-sizes__list">{sizes}</ul></section>',
        sorted_note,
    ]
    parts.extend(_section_html(section, pages, owned, signed_in) for section in sections)
    parts.extend([
        f'<section id="faq" class="editorial sn-faq" aria-labelledby="faq-heading"><h2 id="faq-heading">Questions</h2>{faq}</section>',
        _related(today),
        '<section class="guide-sources yl-method" aria-labelledby="method-heading"><h2 id="method-heading">How we chose</h2>',
        _paragraphs(GUIDE["method"]),
        f'<p class="muted">First published {_e(_long_date(GUIDE["published"]))}. Checked {_e(_long_date(reviewed))}. '
        '<a href="/contact">Suggest a gift or send a correction</a> · <a href="/content-quality">Editorial standards</a></p>'
        '</section></article>',
    ])
    return "".join(parts)


def _structured() -> dict:
    url = SITE + GUIDE["path"]
    gifts = [gift for section in SECTIONS for gift in section["gifts"]]
    return {"@context": "https://schema.org", "@graph": [
        {
            "@type": "Article", "headline": GUIDE["headline"], "description": GUIDE["summary"],
            "datePublished": GUIDE["published"], "dateModified": GUIDE["reviewed"],
            "mainEntityOfPage": url, "url": url, "inLanguage": "en-US",
            "author": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/about"},
            "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": SITE + "/"},
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(gifts), "itemListElement": [
                {"@type": "ListItem", "position": index, "name": gift["name"], "url": f"{url}#gift-{gift['id']}"}
                for index, gift in enumerate(gifts, 1)
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
def gift_guide_page(request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    signed_in = user is not None
    counts = owned = None
    if signed_in:
        try:
            counts = gift_lists.library_counts(db, user.id)
            owned = gift_lists.owned_gifts(db, user.id)
        except Exception:
            counts = owned = None
    content = guide_content(pages=_title_pages(db), signed_in=signed_in, counts=counts, owned=owned)
    response = page(GUIDE["search_title"], GUIDE["summary"], GUIDE["path"], content,
                    structured_data=_structured(), head=_head(ads=not signed_in), member=signed_in)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


# ---------------------------------------------------------------- the shared list page

def _shared_item_html(item, *, owner_view: bool) -> str:
    data = gift_lists.item_dict(item, claims=not owner_view)
    meta = [data["label"]]
    if data["year"]:
        meta.append(str(data["year"]))
    if data["creator"]:
        meta.append(data["creator"])
    note = f'<p class="gg-wish__note"><strong>Note:</strong> {_e(data["note"])}</p>' if data["note"] else ""
    # A gift is bought now, so a game doesn't need the "Pre-order or buy" wording Release Radar uses.
    buy = _buy_button(data["buy"], STORE_LABELS.get(item.store or "") or ("Find it on Amazon" if item.kind == "game" else None))
    claim = ""
    if not owner_view:
        if data["claimed"]:
            claim = '<p class="gg-wish__taken" data-gift-taken>Someone’s getting this</p>'
        else:
            claim = (f'<button type="button" class="button button--ghost gg-claim" data-gift-claim="{item.id}">'
                     'I’m getting this</button>')
    classes = "gg-wish" + (" gg-wish--taken" if not owner_view and data["claimed"] else "")
    return (
        f'<li class="{classes}" data-gift-item="{item.id}">{_art(data["title"], data["image"], "gg-wish__art")}'
        f'<div class="gg-wish__body"><h3>{_e(data["title"])}</h3><p class="gg-gift__meta">{_e(" · ".join(meta))}</p>{note}'
        f'<div class="gg-gift__actions">{buy}{claim}</div>'
        '<p class="gg-gift__status" data-gift-status role="status" aria-live="polite"></p></div></li>'
    )


def _not_found() -> Response:
    response = strict_html_response(message_page(
        "Gift list not found", "This gift list link doesn't work anymore",
        "Whoever sent it may have made a new link or switched this one off. Ask them for the latest one.",
        actions=(("Read the holiday gift guide", GUIDE["path"]), ("See what OmniTrackr does", "/about"))), status_code=404)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return _private(response)


@router.get("/gifts/{token}", include_in_schema=False)
def gift_list_page(token: str, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    gift_list = gift_lists.by_token(db, token)
    if gift_list is None:
        return _not_found()
    owner = db.get(models.User, gift_list.owner_id)
    name = owner.username
    owner_view = user is not None and user.id == gift_list.owner_id
    if user is None:
        funnel.record("gift_list_link_opened", request)
    items = list(gift_list.items)
    open_count = sum(1 for item in items if item.claimed_at is None)
    if owner_view:
        intro = ('<p class="gg-owner-note">This is how your list looks to the people you send it to. Which gifts '
                 'they\'ve marked is hidden from you, so every gift shows as open here. '
                 f'<a href="{GUIDE["path"]}#gift-list">Edit your list</a></p>')
    elif items:
        intro = (f'<p class="gg-wish-lead">{len(items)} gift{"s" if len(items) != 1 else ""}, {open_count} still open. '
                 f'If you buy one, press "I’m getting this" so nobody else does. {_e(name)} won\'t see which you picked.</p>')
    else:
        intro = ""
    message = f'<blockquote class="gg-message"><p>{_e(gift_list.message)}</p></blockquote>' if gift_list.message else ""
    wishes = ("".join(_shared_item_html(item, owner_view=owner_view) for item in items)
              if items else f'<li class="gg-muted">{_e(name)} hasn\'t added anything yet. Check back soon.</li>')
    cta = "" if user is not None else (
        '<section class="gg-panel gg-promo gg-promo--small" aria-labelledby="gift-own-title">'
        '<h2 id="gift-own-title">Want a list like this?</h2>'
        '<p>OmniTrackr is a free tracker for movies, TV, anime, games, books, music and more. Make a gift list from '
        'your own library in a couple of minutes.</p>'
        f'<p class="gg-promo__actions"><a class="button" href="/?next={SIGNUP_NEXT}#signup" data-gift-signup>Make my own, free</a>'
        f'<a class="gg-gift__link" href="{GUIDE["path"]}">Read the gift guide</a></p></section>')
    content = (
        f'<article class="sn-hub gg-shared" data-season-theme="holiday" data-gift-token="{_e(gift_list.token)}">'
        '<header class="hero sn-hero gg-shared__hero"><span class="sn-hero__moon" aria-hidden="true"></span>'
        '<p class="eyebrow">GIFT LIST</p>'
        f'<h1>{_e(name)}’s gift list</h1>{message}{intro}'
        f'{affiliate.disclosure_html("gg-disclosure")}</header>'
        f'<ul class="gg-wishes">{wishes}</ul>{cta}</article>'
    )
    title = f"{name}'s gift list".replace("{", "(").replace("}", ")")
    response = page(title, "A holiday gift list made on OmniTrackr.", f"/gifts/{gift_list.token}", content,
                    indexable=False, head=_head(ads=False), member=user is not None)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Vary"] = "Cookie"
    return _private(response)


# ---------------------------------------------------------------- member API

def _fail(error: gift_lists.GiftListError):
    raise HTTPException(error.status, error.message)


def _owner_payload(db: Session, user) -> dict:
    return {"list": gift_lists.owner_view(gift_lists.get(db, user.id)),
            "suggestions": gift_lists.suggestions(db, user.id)}


@router.get("/api/gift-list")
def get_gift_list(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The member's gift list (never the claims) and gift ideas from their own library."""
    _private(response)
    return _owner_payload(db, user)


class GiftAdd(BaseModel):
    source: Literal["library", "guide", "text"]
    kind: Optional[str] = Field(None, max_length=12)
    item_id: Optional[PositiveDatabaseId] = None
    gift_id: Optional[str] = Field(None, max_length=60)
    text: Optional[str] = Field(None, max_length=200)


@router.post("/api/gift-list/items")
def add_gift(payload: GiftAdd, request: Request, response: Response,
             user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Put a title from the library, a gift from the guide, or a typed idea on the member's list."""
    _private(response)
    lock_progress_owner(db, user.id)
    created_list = gift_lists.get(db, user.id) is None
    try:
        if payload.source == "library":
            if not payload.kind or payload.item_id is None:
                raise gift_lists.GiftListError("Choose a title from your library.")
            state, item = gift_lists.add_from_library(db, user, payload.kind, payload.item_id)
        elif payload.source == "guide":
            state, item = gift_lists.add_from_guide(db, user, payload.gift_id or "")
        else:
            state, item = gift_lists.add_text(db, user, payload.text or "")
    except gift_lists.GiftListError as error:
        db.rollback()
        _fail(error)
    db.commit()
    if created_list:
        funnel.record("gift_list_started", request)
    return {"state": state, "item": item, **_owner_payload(db, user)}


class GiftNote(BaseModel):
    note: str = Field("", max_length=200)


@router.patch("/api/gift-list/items/{item_id}")
def note_gift(item_id: PositiveDatabaseId, payload: GiftNote, request: Request, response: Response,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    try:
        item = gift_lists.set_note(db, user, item_id, payload.note)
    except gift_lists.GiftListError as error:
        _fail(error)
    db.commit()
    return {"item": item}


@router.delete("/api/gift-list/items/{item_id}")
def remove_gift(item_id: PositiveDatabaseId, request: Request, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    try:
        gift_lists.remove(db, user, item_id)
    except gift_lists.GiftListError as error:
        _fail(error)
    db.commit()
    db.expire_all()
    return _owner_payload(db, user)


class GiftSettings(BaseModel):
    message: Optional[str] = Field(None, max_length=300)
    shared: Optional[bool] = None


@router.patch("/api/gift-list")
def update_gift_list(payload: GiftSettings, request: Request, response: Response,
                     user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Change the note at the top of the shared page, or switch the link off and on."""
    _private(response)
    gift_lists.update_settings(db, user, message=payload.message, shared=payload.shared)
    db.commit()
    return {"list": gift_lists.owner_view(gift_lists.get(db, user.id))}


@router.post("/api/gift-list/link")
def reset_gift_link(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Retire the current link and make a new one."""
    _private(response)
    gift_lists.reset_link(db, user)
    db.commit()
    return {"list": gift_lists.owner_view(gift_lists.get(db, user.id))}


# ---------------------------------------------------------------- claims on a shared list (no account needed)

def _shared_or_404(db: Session, token: str) -> models.GiftList:
    gift_list = gift_lists.by_token(db, token)
    if gift_list is None:
        raise HTTPException(404, "This gift list link doesn't work anymore.")
    return gift_list


class GiftUnclaim(BaseModel):
    key: str = Field(..., max_length=80)


@router.post("/api/gifts/{token}/items/{item_id}/claim")
def claim_gift(token: str, item_id: PositiveDatabaseId, request: Request, response: Response,
               user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    """Mark a gift as taken. The answer carries the key that undoes it; only its hash is kept."""
    _private(response)
    gift_list = _shared_or_404(db, token)
    if user is not None and user.id == gift_list.owner_id:
        raise HTTPException(403, "This is your own list, so the surprise is safe: you can't mark gifts on it.")
    db.query(models.GiftList).filter(models.GiftList.id == gift_list.id).with_for_update().first()
    try:
        key = gift_lists.claim(db, gift_list, item_id)
    except gift_lists.GiftListError as error:
        _fail(error)
    db.commit()
    funnel.record("gift_claimed", request)
    return {"claimed": True, "key": key}


@router.post("/api/gifts/{token}/items/{item_id}/unclaim")
def unclaim_gift(token: str, item_id: PositiveDatabaseId, payload: GiftUnclaim, request: Request, response: Response,
                 user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    _private(response)
    gift_list = _shared_or_404(db, token)
    if user is not None and user.id == gift_list.owner_id:
        raise HTTPException(403, "This is your own list, so the surprise is safe: you can't change marks on it.")
    try:
        gift_lists.unclaim(db, gift_list, item_id, payload.key)
    except gift_lists.GiftListError as error:
        _fail(error)
    db.commit()
    return {"claimed": False}
