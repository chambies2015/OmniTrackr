"""Top nine maker (/top-nine), shared grids (/top-nine/<token>) and their pictures (see app/top_nine.py)."""
from __future__ import annotations

import asyncio
import threading
import time
from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import funnel, image_sizes, tier_list, title_pages, top_nine, top_nine_card
from ..auth import AUTH_COOKIE_NAME
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..visitor_identity import set_visitor_cookie, visitor_identity
from .discover import page

router = APIRouter(tags=["top-nine"])
CSS_VERSION = "20261128-top-nine-sweep-1"
JS_VERSION = "20261128-top-nine-sweep-1"
SITE = "https://omnitrackr.xyz"
POSTER_SECONDS = 8.0
PICTURE_NAMES = {"post": "post.jpg", "story": "story.jpg", "card": "card.png"}
DESCRIPTION = ("Make your top nine of the year: the nine films, shows, games, albums and books you loved most, "
               "in one 3x3 grid. Get a picture for Instagram, a story version and a link. Free, no account needed.")
# Outside cover lookups for titles the site has never seen, across every visitor. Each one can
# reach Wikidata, which rate-limits the whole site, so the budget is small.
LOOKUPS_PER_HOUR = 240
_lookups = {"hour": 0, "count": 0}
_lookups_lock = threading.Lock()


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


def _fail(error: top_nine.TopNineError):
    raise HTTPException(error.status, error.message)


def _grid_or_404(db: Session, token: str, *, lock: bool = False):
    grid = top_nine.by_token(db, token, lock=lock)
    if grid is None:
        raise HTTPException(404, "This top nine isn't here anymore")
    return grid


def _person(request: Request) -> bool:
    from .tier_list import _person as person
    return person(request)


# ---------------------------------------------------------------- request bodies

class Tile(BaseModel):
    title: str = Field(..., max_length=300)
    kind: str = Field(..., max_length=10)
    year: Optional[int] = None
    slug: Optional[str] = Field(None, max_length=140)
    creator: Optional[str] = Field(None, max_length=200)
    image: Optional[str] = Field(None, max_length=1000)


class GridBody(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    theme: Optional[str] = Field(None, max_length=12)
    tiles: list[Optional[Tile]] = Field(default_factory=list, max_length=top_nine.SLOTS)
    source: Optional[str] = Field(None, max_length=40)
    key: Optional[str] = Field(None, max_length=80)


class GridKey(BaseModel):
    key: Optional[str] = Field(None, max_length=80)


class ClaimLink(BaseModel):
    token: str = Field(..., max_length=40)
    key: str = Field(..., max_length=80)


class ClaimBody(BaseModel):
    links: list[ClaimLink] = Field(default_factory=list, max_length=top_nine.CLAIM_MAX)


class AnswerBody(BaseModel):
    seen: int = Field(..., ge=0, le=top_nine.SLOTS)


def _payload(body: GridBody) -> dict:
    data = body.model_dump()
    data["tiles"] = [tile for tile in data["tiles"]]
    return data


# ---------------------------------------------------------------- the maker

def _kind_chips() -> str:
    chips = ['<button type="button" class="tn-chip" data-tn-kind="" aria-pressed="true">All</button>']
    for kind in top_nine.KIND_ORDER:
        chips.append(f'<button type="button" class="tn-chip" data-tn-kind="{kind}" aria-pressed="false">'
                     f'{_e(top_nine.KIND_PLURAL[kind].capitalize())}</button>')
    return "".join(chips)


def _kind_options() -> str:
    return "".join(f'<option value="{kind}">{_e(top_nine.KIND_SHORT[kind])}</option>' for kind in top_nine.KIND_ORDER)


def _frame(year: int, name: str, theme: str, cells: str, *, editable: bool) -> str:
    name_html = (f'<input class="tn-frame__name" type="text" maxlength="{top_nine.MAX_NAME}" value="{_e(name)}" '
                 'aria-label="Name at the top of your top nine" autocomplete="off" spellcheck="false" data-tn-name>'
                 if editable else f'<p class="tn-frame__name">{_e(name)}</p>')
    return (f'<div class="tn-frame tn-theme--{_e(theme)}" data-tn-frame>'
            f'<p class="tn-frame__eyebrow">TOP NINE · {_e(year)}</p>{name_html}'
            f'<ol class="tn-grid" data-tn-grid>{cells}</ol>'
            '<p class="tn-frame__foot"><span>Made on OmniTrackr</span><span>omnitrackr.xyz/top-nine</span></p></div>')


def _empty_cells() -> str:
    return "".join(
        f'<li><button type="button" class="tn-cell tn-cell--empty" data-tn-cell="{index}" '
        f'aria-label="Square {index + 1}, empty. Choose a title"><span class="tn-cell__num">{index + 1}</span>'
        '<span class="tn-cell__add" aria-hidden="true">+</span></button></li>' for index in range(top_nine.SLOTS))


def _guide(when: str) -> str:
    """The tips under the maker. ``when`` is "this year", or "in 2026" during the January after."""
    return (
    '<section class="editorial tn-guide" aria-labelledby="tnHow"><h2 id="tnHow">How to pick nine</h2>'
    '<p>Nine is a small number for a whole year, and that is the point. Start with the titles you brought up in '
    'conversation without being asked: the show you kept telling people to start, the game you lost a weekend to, the '
    'album that was on in the car for a month. Those usually fill four or five squares on their own.</p>'
    '<p>For the rest, think about what the grid says when someone scrolls past it. A top nine that is all films reads '
    'as a film list. Mixing in one book and one album says more about your year than a tenth film would. It is also '
    f'fine to break the rule about release dates. The question is what you loved {when}, and the old film you '
    'finally saw in March counts.</p>'
    '<p>Order matters less than you think, but the eye goes to the top left square first and the centre square '
    'second, so put your favourite in one of those. Tap a filled square to move it earlier or later.</p></section>'
    '<section class="editorial tn-guide" aria-labelledby="tnIdeas"><h2 id="tnIdeas">Grids worth trying</h2><ul>'
    '<li>One of each: a film, a show, an anime, a game, an album, a book, a manga, a podcast and an audiobook.</li>'
    f'<li>Only things you finished for the first time {when}.</li>'
    '<li>Nine you would hand to a friend who asks "what should I start?"</li>'
    '<li>The year in order: January in the top left, December in the bottom right.</li>'
    '<li>Comfort picks: what you went back to when the week was too long.</li>'
    '<li>The ones that surprised you: titles you expected nothing from.</li></ul>'
    '<p>Made one already? Make another. Each grid gets its own link and pictures, and friends can open any of them.</p>'
    '</section>'
    '<section class="editorial tn-guide" aria-labelledby="tnFaq"><h2 id="tnFaq">Questions</h2><dl class="tn-faq">'
    '<dt>Do I need an account?</dt><dd>No. Anyone can make a top nine and share it. Without an account the link '
    f'lasts {top_nine.GUEST_DAYS} days and stays tied to the browser that made it. A free account keeps it for good '
    'and can put the nine titles into your library.</dd>'
    '<dt>Where do the posters come from?</dt><dd>From the covers members use in their libraries and the title details '
    'the site already keeps (Wikipedia, TVmaze, RAWG, MyAnimeList, Open Library and Apple). A title with no cover gets '
    'a square in its format\'s colour with the name written on it.</dd>'
    '<dt>Can I change it after posting?</dt><dd>Yes. Changes made in the same browser, or while signed in, update the '
    'link and the pictures. A picture you already posted stays as it was, so save it again if you want the new one.</dd>'
    '<dt>What do friends see when they open the link?</dt><dd>Your nine squares and their names. They can tap the ones '
    'they have seen too and start their own grid from those. Nobody sees your library, your scores or who else opened '
    'it.</dd>'
    '<dt>Which picture should I post?</dt><dd>The square-ish picture is 1080 by 1440 pixels, the 3:4 shape '
    'Instagram\'s profile grid shows, and it works on X, Threads and Bluesky too. The story picture is 1080 by 1920 '
    'with room left for Instagram\'s top and bottom bars, so you can add a link sticker with your top nine\'s link.</dd>'
    '</dl></section>'
    )


@router.get("/top-nine", include_in_schema=False)
def top_nine_page(request: Request, source: str = Query("", alias="from", max_length=40),
                  have: str = Query("", max_length=40), edit: str = Query("", max_length=40),
                  db: Session = Depends(get_db)):
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    year = top_nine.season_year()
    source = source if top_nine.valid_token(source) else ""
    edit = edit if top_nine.valid_token(edit) else ""
    have = ",".join(part for part in have.split(",") if part.isdigit() and int(part) < top_nine.SLOTS)[:40]
    themes = "".join(
        f'<label class="tn-theme-pick tn-theme-pick--{theme}"><input type="radio" name="tnTheme" value="{theme}"'
        f'{" checked" if theme == top_nine.THEMES[0] else ""} data-tn-theme><span>{label}</span></label>'
        for theme, label in (("night", "Night"), ("paper", "Paper"), ("berry", "Berry")))
    guest_cta = '' if signed_in else (
        '<aside class="tn-cta" data-tn-cta hidden><p><strong>Keep your nine.</strong> This link lasts '
        f'{top_nine.GUEST_DAYS} days. With a free account it stays up for good and the nine titles go into your '
        'library as finished.</p>'
        '<a class="button" href="/?next=%2Ftop-nine#signup" data-tn-signup>Keep my nine, free</a></aside>')
    member_keep = ('<aside class="tn-cta tn-cta--member" data-tn-keep-box hidden><p><strong>Put these in your '
                   'library?</strong> Titles you don\'t have yet go in as finished. Titles you already have stay as '
                   'they are.</p><button type="button" class="button button--ghost" data-tn-keep>Add the nine to my '
                   'library</button></aside>' if signed_in else '')
    mine = ('<section class="tn-mine" data-tn-mine hidden aria-labelledby="tnMineTitle"><h2 id="tnMineTitle">Your top '
            'nines</h2><ul class="tn-mine__list" data-tn-mine-list></ul></section>' if signed_in else '')
    content = (
        f'<header class="hero tn-hero"><p class="eyebrow">TOP NINE · {_e(year)}</p>'
        f'<h1>Your {_e(year)} in nine squares</h1>'
        f'<p>Pick the nine things you loved most {top_nine.year_words(year)}: films, shows, games, albums, books, '
        'anything. You get a picture sized for Instagram, a story version, and a link friends can open to see how many they\'ve seen too. '
        'Free, and no account needed.</p></header>'
        f'<section class="tn-tool" id="topNine" data-year="{_e(year)}" data-signed-in="{"true" if signed_in else "false"}" '
        f'data-from="{_e(source)}" data-have="{_e(have)}" data-edit="{_e(edit)}" aria-label="Top nine maker">'
        '<div class="tn-stage">'
        f'{_frame(year, top_nine.default_name(year), top_nine.THEMES[0], _empty_cells(), editable=True)}'
        '<div class="tn-cellbar" data-tn-cellbar hidden role="group" aria-label="Move or remove the chosen square">'
        '<span class="tn-cellbar__label" data-tn-cellbar-label></span>'
        '<button type="button" class="button button--ghost" data-tn-move="-1">Earlier</button>'
        '<button type="button" class="button button--ghost" data-tn-move="1">Later</button>'
        '<button type="button" class="button button--ghost" data-tn-remove>Remove</button></div>'
        f'<fieldset class="tn-themes"><legend>Colours</legend>{themes}</fieldset>'
        '<noscript><p class="tn-noscript">The top nine maker needs JavaScript. The tips below work without it.</p></noscript>'
        '</div>'
        '<div class="tn-side">'
        '<div class="tn-picker" data-tn-picker id="tnPicker">'
        '<h2 class="tn-picker__title" data-tn-picker-title>Square 1</h2>'
        '<form class="tn-search" role="search" data-tn-search><label for="tnSearch">Search films, shows, games, '
        'albums, books and more</label><div class="tn-search__row"><input id="tnSearch" type="search" maxlength="80" '
        'autocomplete="off" spellcheck="false" placeholder="Try The Pitt or Hades II"></div></form>'
        f'<div class="tn-chips" role="group" aria-label="Format">{_kind_chips()}</div>'
        '<p class="tn-results__head" data-tn-results-head></p>'
        '<div class="tn-results" data-tn-results aria-live="polite"></div>'
        '<form class="tn-custom" data-tn-custom hidden><p class="tn-custom__lead" data-tn-custom-lead></p>'
        '<div class="tn-row"><label class="sr-only" for="tnCustomKind">Format</label>'
        f'<select id="tnCustomKind" data-tn-custom-kind>{_kind_options()}</select>'
        '<button type="submit" class="button button--ghost">Add it</button></div></form>'
        '</div>'
        '<div class="tn-done" data-tn-done><h2>Post it</h2>'
        f'<p class="tn-done__hint" data-tn-done-hint>Fill at least {top_nine.MIN_FILLED} squares to make the '
        'pictures. Nine looks best.</p>'
        '<div class="tn-row"><button type="button" class="button" data-tn-make disabled>Make my pictures</button></div>'
        '<div class="tn-ready" data-tn-ready hidden>'
        '<img class="tn-preview" data-tn-preview alt="Your top nine picture" width="1080" height="1440" hidden>'
        '<div class="tn-row tn-row--save">'
        '<a class="button" data-tn-save="post" href="#" download>Save picture</a>'
        '<a class="button button--ghost" data-tn-save="story" href="#" download>Story size</a>'
        '<button type="button" class="button button--ghost" data-tn-share-image hidden>Share picture</button></div>'
        '<p class="tn-appnote" data-tn-appnote hidden>Saving may not work inside Instagram or TikTok. Press and hold the '
        'picture and choose Save, or open this page in Safari or Chrome.</p>'
        '<div class="tn-link"><label for="tnLink">Your link</label><div class="tn-row">'
        '<input id="tnLink" type="text" readonly data-tn-link-url>'
        '<button type="button" class="button button--ghost" data-tn-copy>Copy link</button>'
        '<button type="button" class="button button--ghost" data-tn-share hidden>Share link</button></div>'
        '<p class="tn-note muted" data-tn-note></p></div>'
        f'{guest_cta}{member_keep}'
        '<p class="tn-restart"><button type="button" class="tn-textbtn" data-tn-clear>Start a new top nine</button></p>'
        '</div>'
        '<p class="tn-status" data-tn-status role="status" aria-live="polite"></p></div>'
        f'{mine}</div>'
        '<div class="tn-dock" data-tn-dock hidden><span data-tn-dock-text></span>'
        '<button type="button" class="tn-textbtn" data-tn-dock-up>See the grid</button></div>'
        '</section>'
        + _guide(top_nine.year_words(year))
    )
    head = (f'<link rel="stylesheet" href="/static/top-nine.css?v={CSS_VERSION}">'
            f'<script src="/static/top-nine.js?v={JS_VERSION}" defer></script>')
    response = page(f"Top nine of {year} maker: your year in a 3x3 grid", DESCRIPTION, "/top-nine", content,
                    indexable=not (source or edit or have), head=head, member=signed_in,
                    share_image=f"{SITE}/static/top-nine-card.png?v={CSS_VERSION}",
                    structured_data={
                        "@context": "https://schema.org", "@type": "WebApplication",
                        "name": f"OmniTrackr top nine of {year}", "description": DESCRIPTION,
                        "url": f"{SITE}/top-nine", "applicationCategory": "EntertainmentApplication",
                        "operatingSystem": "Any", "inLanguage": "en-US", "isAccessibleForFree": True,
                        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                        "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": f"{SITE}/"},
                    })
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


# ---------------------------------------------------------------- finding titles

@router.get("/api/top-nine/search")
def search_titles(request: Request, response: Response, q: str = Query("", max_length=200),
                  kind: str = Query("", max_length=10), db: Session = Depends(get_db)):
    """Titles to put in a square: members' titles, then the editors'. Anyone can use it."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return {"results": top_nine.search(db, q, kind or None)}


@router.get("/api/top-nine/suggest")
def suggest_titles(request: Request, response: Response, kind: str = Query("", max_length=10),
                   user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    """What the picker shows before anything is typed: the year's big releases, and a member's own titles."""
    response.headers["Cache-Control"] = "private, no-store"
    kind = kind if kind in title_pages.KINDS else None
    year = top_nine.season_year()
    mine = {"year": [], "loved": []}
    if user is not None:
        try:
            mine = top_nine.member_options(db, user, year)
        except Exception:
            db.rollback()
        if kind:
            mine = {group: [row for row in rows if row["kind"] == kind] for group, rows in mine.items()}
    return {"year": year, "big": top_nine.big_ones(db, year, kind), "mine": mine}


def _lookup_allowed() -> bool:
    hour = int(time.time() // 3600)
    with _lookups_lock:
        if _lookups["hour"] != hour:
            _lookups.update(hour=hour, count=0)
        if _lookups["count"] >= LOOKUPS_PER_HOUR:
            return False
        _lookups["count"] += 1
        return True


@router.get("/api/top-nine/art")
async def title_art(request: Request, response: Response, kind: str = Query(..., max_length=10),
                    title: str = Query(..., min_length=1, max_length=200), year: Optional[int] = Query(None, ge=1000, le=2200),
                    creator: str = Query("", max_length=120), db: Session = Depends(get_db)):
    """A cover for a square that has none: the site's cache first, an outside lookup within a small budget."""
    if kind not in title_pages.KINDS:
        raise HTTPException(404, "Unknown format")
    display = " ".join(title.split())
    if not display or not top_nine.text_allowed(display):
        raise HTTPException(422, "That title can't go on a top nine")

    def cached():
        from .. import explore_art
        return explore_art.cached_posters(db, [(kind, display, year)]).get((kind, display, year))
    image = await run_in_threadpool(cached)
    if not image and _lookup_allowed():
        from .. import title_metadata
        client = getattr(request.app.state, "external_api_client", None)
        data = await title_metadata.get_or_fetch(db, client, kind, title_pages.normalize(display), display, year,
                                                 creator or None, wait=6)
        image = title_pages._safe_image((data or {}).get("poster"))
    if not (tier_list.image_allowed(image) and str(image).startswith("https://")):
        image = None
    response.headers["Cache-Control"] = "public, max-age=86400" if image else "no-store"
    return {"image": image, "thumb": image_sizes.sized(image, 420) if image else None}


# ---------------------------------------------------------------- making and changing a grid

@router.post("/api/top-nine")
def create_grid(body: GridBody, request: Request, response: Response,
                user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    """Turn the squares into a link and pictures. Works without an account (the link then lasts GUEST_DAYS)."""
    _private(response)
    visitor, new_cookie = None, None
    if user is None:
        visitor, new_cookie, _ = visitor_identity(request)
    try:
        grid, key = top_nine.create(db, user, visitor, _payload(body))
    except top_nine.TopNineError as error:
        _fail(error)
    set_visitor_cookie(response, new_cookie)
    funnel.record("top_nine_made", request)
    if grid.source_id:
        funnel.record("top_nine_remixed", request)
    return top_nine.owner_reply(grid, key)


@router.get("/api/top-nine/mine")
def my_grids(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return {"grids": top_nine.mine(db, user)}


@router.post("/api/top-nine/claim")
def claim_grids(body: ClaimBody, request: Request, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Grids this browser made before signing up move into the account and stop expiring."""
    _private(response)
    claimed = top_nine.claim(db, user, [link.model_dump() for link in body.links])
    if claimed:
        funnel.record("top_nine_claimed", request)
    return {"claimed": claimed}


@router.get("/api/top-nine/{token}")
def get_grid(token: str, request: Request, response: Response, user=Depends(get_optional_current_user),
             db: Session = Depends(get_db)):
    _private(response)
    grid = _grid_or_404(db, token)
    # "yours" lets the maker open a signed-in member's own grid for changes (?edit=) and no one else's.
    return {**top_nine.public_state(db, grid), "yours": user is not None and grid.owner_id == user.id}


@router.put("/api/top-nine/{token}")
def update_grid(token: str, body: GridBody, request: Request, response: Response,
                user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    _private(response)
    grid = _grid_or_404(db, token, lock=True)
    try:
        grid = top_nine.update(db, grid, user, _payload(body))
    except top_nine.TopNineError as error:
        _fail(error)
    return top_nine.owner_reply(grid)


@router.delete("/api/top-nine/{token}", status_code=204)
def delete_grid(token: str, request: Request, body: Optional[GridKey] = None,
                user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    grid = _grid_or_404(db, token, lock=True)
    try:
        top_nine.delete(db, grid, user, body.key if body else None)
    except top_nine.TopNineError as error:
        _fail(error)
    response = Response(status_code=204)
    _private(response)
    return response


@router.post("/api/top-nine/{token}/keep")
def keep_grid(token: str, request: Request, response: Response, user=Depends(get_current_user),
              db: Session = Depends(get_db)):
    """The owner puts the nine into their library, finished. Titles they already have are left alone."""
    _private(response)
    grid = _grid_or_404(db, token)
    if grid.owner_id != user.id:
        raise HTTPException(403, "Only the person who made this top nine can add it to their library.")
    result = top_nine.keep(db, user, grid)
    if result["added"]:
        funnel.record("top_nine_kept", request)
    return result


@router.post("/api/top-nine/{token}/answer")
def answer_grid(token: str, body: AnswerBody, request: Request, response: Response,
                user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    """Someone said how many of the nine they've seen. Only the count goes up; nothing about them is kept."""
    _private(response)
    grid = _grid_or_404(db, token)
    visitor, _, retained = visitor_identity(request)
    own = (user is not None and grid.owner_id == user.id) or (retained and grid.owner_id is None and grid.visitor == visitor)
    answers = grid.answers or 0  # read before counting: the commit reloads the row
    if not own:
        top_nine.count_answer(db, grid)
        funnel.record("top_nine_answered", request)
        answers += 1
    return {"answers": answers}


# ---------------------------------------------------------------- the shared page

def _not_found():
    from ..csp import strict_html_response
    from ..site_chrome import message_page
    response = strict_html_response(message_page(
        "Top nine not found", "This top nine isn't here anymore",
        f"Whoever made it may have deleted it, or it was made without an account and its {top_nine.GUEST_DAYS} days ran "
        "out. You can make your own in a couple of minutes.",
        actions=(("Make my top nine", "/top-nine"), ("See what OmniTrackr does", "/about"))), status_code=404)
    _private(response)
    return response


def _shared_cell(index: int, tile: Optional[dict]) -> str:
    if not tile:
        return (f'<li><span class="tn-cell tn-cell--empty tn-cell--static" aria-hidden="true">'
                f'<span class="tn-cell__num">{index + 1}</span></span></li>')
    meta = " · ".join(str(part) for part in (tile["label"], tile.get("year")) if part)
    if tile.get("image"):
        lazy = "" if index < 6 else ' loading="lazy"'
        art = (f'<img src="{_e(image_sizes.sized(tile["image"], 420))}" alt="" decoding="async" '
               f'referrerpolicy="no-referrer" width="300" height="400"{lazy}>')
        cls = "tn-cell tn-cell--art"
    else:
        art = (f'<span class="tn-cell__kind">{_e(tile["label"])}</span>'
               f'<span class="tn-cell__name">{_e(tile["title"])}</span>')
        cls = f"tn-cell tn-cell--text tn-kind--{_e(tile['kind'])}"
    return (f'<li><button type="button" class="{cls}" data-tn-seen="{index}" aria-pressed="false" '
            f'aria-label="{_e(tile["title"])}, {_e(meta)}. Seen it too?">{art}'
            '<span class="tn-cell__tick" aria-hidden="true">✓</span></button></li>')


def _shared_list(tiles: list) -> str:
    rows = []
    for index, tile in enumerate(tiles):
        if not tile:
            continue
        name = (f'<a href="{_e(tile["url"])}">{_e(tile["title"])}</a>' if tile.get("url") else _e(tile["title"]))
        meta = " · ".join(str(part) for part in (tile["label"], tile.get("creator"), tile.get("year")) if part)
        rows.append(f'<li value="{index + 1}"><strong>{name}</strong><span>{_e(meta)}</span></li>')
    return f'<ol class="tn-list__items">{"".join(rows)}</ol>'


@router.get("/top-nine/{token}", include_in_schema=False)
def shared_grid(token: str, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    grid = top_nine.by_token(db, token)
    if grid is None:
        return _not_found()
    visitor, _, retained = visitor_identity(request)
    made_here = retained and grid.owner_id is None and grid.visitor == visitor
    owner = (user is not None and grid.owner_id == user.id) or made_here
    # Chat apps fetch the page to unfurl it and browsers prefetch it; neither is someone opening the link.
    if not owner and _person(request):
        top_nine.count_view(db, grid)
        if user is None:
            funnel.record("top_nine_link_opened", request)
    state = top_nine.public_state(db, grid)
    by_html = (f'<a href="{_e(state["by_url"])}">{_e(state["by"])}</a>' if state["by"] else
               ("an OmniTrackr member" if state["member"] else "someone on OmniTrackr"))
    filled = [tile for tile in state["tiles"] if tile]
    counts = []
    if state["views"] >= 3:
        counts.append(f'opened {state["views"]:,} times')
    if state["remixes"]:
        counts.append(f'{state["remixes"]:,} made their own from it')
    cells = "".join(_shared_cell(index, tile) for index, tile in enumerate(state["tiles"]))
    names = ", ".join(tile["title"] for tile in filled[:3])
    description = (f'{grid.name}: a top nine of {grid.year} with {names}'
                   + (f' and {len(filled) - 3} more' if len(filled) > 3 else '')
                   + '. How many have you seen? Make your own grid in a couple of minutes.')
    signed_in = user is not None
    guest_cta = '' if signed_in else (
        '<aside class="tn-cta tn-cta--shared"><p><strong>Keep track of next year as you go.</strong> OmniTrackr is a '
        'free library for films, shows, anime, games, books, albums, manga, podcasts and audiobooks. Rate what you '
        'finish and next December your Year in Review is already written.</p>'
        '<a class="button" href="/?next=%2Ftop-nine#signup" data-tn-signup>Create a free account</a> '
        '<a class="button button--ghost" href="/top-nine">Make a top nine without one</a></aside>')
    owner_box = (
        '<div class="tn-owner" data-tn-owner' + ('' if owner else ' hidden') + '><p><strong>This is your top nine.'
        '</strong> Changes you make in the maker update this link and its pictures.</p><div class="tn-row">'
        f'<a class="button button--ghost" href="/top-nine?edit={_e(grid.token)}">Change it</a>'
        f'<a class="button button--ghost" href="{_e(state["path"])}/post.jpg?download=1&amp;v={_e(state["version"])}" '
        'download data-tn-owner-save>Save picture</a>'
        f'<a class="button button--ghost" href="{_e(state["path"])}/story.jpg?download=1&amp;v={_e(state["version"])}" '
        'download data-tn-owner-save>Story size</a>'
        '<button type="button" class="button button--ghost" data-tn-delete>Delete this top nine</button></div></div>')
    content = (
        f'<article class="tn-shared" id="topNineShare" data-token="{_e(grid.token)}" data-owner="{"true" if owner else "false"}" '
        f'data-filled="{len(filled)}">'
        f'<header class="hero tn-hero tn-shared__head"><p class="eyebrow">TOP NINE · {_e(grid.year)}</p>'
        f'<h1>{_e(grid.name)}</h1><p class="tn-shared__by">By {by_html} · {len(filled)} titles'
        f'{" · " + _e(", ".join(counts)) if counts else ""}</p></header>'
        '<div class="tn-shared__body"><div class="tn-stage">'
        f'{_frame(grid.year, grid.name, grid.theme, cells, editable=False)}</div>'
        '<div class="tn-side"><section class="tn-ask" aria-labelledby="tnAskTitle">'
        '<h2 id="tnAskTitle">How many have you seen?</h2>'
        '<p>Tap the squares you\'ve seen, played, read or heard too.</p>'
        f'<p class="tn-ask__score" data-tn-score aria-live="polite">0 of {len(filled)}</p>'
        '<div class="tn-row">'
        f'<a class="button" href="/top-nine?from={_e(grid.token)}" data-tn-start>Make my top nine</a>'
        '<button type="button" class="button button--ghost" data-tn-copy>Copy link</button>'
        '<button type="button" class="button button--ghost" data-tn-share hidden>Share</button></div>'
        '<p class="muted tn-ask__hint" data-tn-start-hint>Your grid starts empty, so the year is yours to fill.</p>'
        '<p class="tn-status" data-tn-status role="status" aria-live="polite"></p></section>'
        f'<section class="tn-list" aria-labelledby="tnListTitle"><h2 id="tnListTitle">The nine</h2>{_shared_list(state["tiles"])}</section>'
        f'{owner_box}</div></div>{guest_cta}</article>'
    )
    head = (f'<link rel="stylesheet" href="/static/top-nine.css?v={CSS_VERSION}">'
            f'<script src="/static/top-nine.js?v={JS_VERSION}" defer></script>')
    card = f"{SITE}{state['path']}/card.png?v={state['version']}"
    response = page(f"{grid.name} · top nine of {grid.year}", description, state["path"], content,
                    indexable=False, head=head, member=signed_in, share_image=card)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Vary"] = "Cookie"
    return response


# ---------------------------------------------------------------- pictures

_PICTURES = None


def _pictures():
    global _PICTURES
    if _PICTURES is None:
        from .profiles import _CardCache
        _PICTURES = _CardCache(size=48)
    return _PICTURES


async def _posters(request: Request, tiles: list) -> dict:
    from .tier_list import _poster_bytes
    client = getattr(request.app.state, "external_api_client", None)
    wanted = {index: image_sizes.sized(tile["image"], 640) for index, tile in enumerate(tiles)
              if tile and tile.get("image") and tier_list.image_allowed(tile["image"])}
    if client is None or not wanted:
        return {}
    urls = list(dict.fromkeys(wanted.values()))
    tasks = {url: asyncio.ensure_future(_poster_bytes(client, url)) for url in urls}
    done, pending = await asyncio.wait(tasks.values(), timeout=POSTER_SECONDS)
    for task in pending:
        task.cancel()
    bodies = {}
    for url, task in tasks.items():
        if task in done and not task.cancelled() and task.exception() is None:
            bodies[url] = task.result()
    return {index: bodies[url] for index, url in wanted.items() if url in bodies}


async def _picture(token: str, which: str, request: Request, db: Session) -> Response:
    def facts():
        grid = top_nine.by_token(db, token)
        if grid is None:
            return None
        return grid.id, {"year": grid.year, "name": grid.name, "theme": grid.theme,
                         "tiles": top_nine.tiles_of(grid)}, top_nine.fingerprint(grid)
    found = await run_in_threadpool(facts)
    if found is None:
        raise HTTPException(404, "This top nine isn't here anymore")
    grid_id, data, version = found
    etag = f'"{version}-{which}"'
    # Short, like the other share pictures: a deleted grid's pictures shouldn't stay up in caches for long.
    headers = {"Cache-Control": "public, max-age=600", "ETag": etag, "X-Content-Type-Options": "nosniff",
               "X-Robots-Tag": "noindex"}
    if request.query_params.get("download") == "1":
        headers["Content-Disposition"] = f'attachment; filename="top-nine-{data["year"]}-{which}.{PICTURE_NAMES[which].rsplit(".", 1)[1]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    cache = _pictures()
    body = cache.get((grid_id, version, which))
    if body is None:
        posters = await _posters(request, data["tiles"])
        try:
            body = await run_in_threadpool(top_nine_card.RENDERERS[which], data, posters)
        except Exception:
            raise HTTPException(404, "Picture unavailable")
        cache.put((grid_id, version, which), body)
    media = "image/png" if which == "card" else "image/jpeg"
    return Response(content=body, media_type=media, headers=headers)


@router.get("/top-nine/{token}/post.jpg", include_in_schema=False)
async def post_picture(token: str, request: Request, db: Session = Depends(get_db)):
    """1080x1440, for a feed post."""
    return await _picture(token, "post", request, db)


@router.get("/top-nine/{token}/story.jpg", include_in_schema=False)
async def story_picture(token: str, request: Request, db: Session = Depends(get_db)):
    """1080x1920, for a story."""
    return await _picture(token, "story", request, db)


@router.get("/top-nine/{token}/card.png", include_in_schema=False)
async def card_picture(token: str, request: Request, db: Session = Depends(get_db)):
    """1200x630, what chat apps show for the link."""
    return await _picture(token, "card", request, db)
