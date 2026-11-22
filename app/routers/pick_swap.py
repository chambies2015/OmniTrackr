"""Pick swap (/swap): Secret Santa where everyone gives one recommendation."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import funnel, models, pick_swap
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..integer_bounds import PositiveDatabaseId
from .discover import page

router = APIRouter(tags=["pick-swap"])
CSS_VERSION = "20261123-swap-1"
JS_VERSION = "20261123-swap-sweep-1"
DESCRIPTION = ("Secret Santa for recommendations: start a swap, send the link, draw names, and everyone picks one "
               "film, show, book, game or album for the person they drew, with a note on why. Everything opens on "
               "unwrap day. Free.")
Tz = Query(0, ge=-14 * 60, le=14 * 60)


def _e(value) -> str:
    # Braces too, so text from a member can never look like a page template placeholder.
    return escape(str(value if value is not None else ""), quote=True).replace("{", "&#123;").replace("}", "&#125;")


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _fail(error: pick_swap.SwapError):
    raise HTTPException(error.status, str(error))


# ------------------------------------------------------------------ payloads

class SwapCreate(BaseModel):
    name: str = Field(..., max_length=pick_swap.NAME_MAX * 2)
    note: Optional[str] = Field(None, max_length=pick_swap.NOTE_MAX * 2)
    kinds: list[str] = Field(default_factory=list, max_length=9)
    draw_on: Optional[date] = None
    reveal_on: date
    wish: Optional[str] = Field(None, max_length=pick_swap.WISH_MAX * 2)
    friend_ids: list[PositiveDatabaseId] = Field(default_factory=list, max_length=50)


class SwapUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=pick_swap.NAME_MAX * 2)
    note: Optional[str] = Field(None, max_length=pick_swap.NOTE_MAX * 2)
    kinds: Optional[list[str]] = Field(None, max_length=9)
    draw_on: Optional[date] = None
    clear_draw: bool = False
    reveal_on: Optional[date] = None


class Wish(BaseModel):
    wish: Optional[str] = Field(None, max_length=pick_swap.WISH_MAX * 2)


class Gift(BaseModel):
    kind: str = Field(..., max_length=10)
    title: str = Field(..., max_length=300)
    year: Optional[int] = Field(None, ge=1800, le=2100)
    image: Optional[str] = Field(None, max_length=500)
    slug: Optional[str] = Field(None, max_length=140)
    creator: Optional[str] = Field(None, max_length=200)
    note: Optional[str] = Field(None, max_length=pick_swap.GIFT_NOTE_MAX * 2)
    anyway: bool = False


class GiftAdd(BaseModel):
    queue: bool = False


class Thanks(BaseModel):
    reaction: str = Field(..., max_length=12)


class Invite(BaseModel):
    friend_ids: list[PositiveDatabaseId] = Field(..., min_length=1, max_length=50)


# ------------------------------------------------------------------ pages

def _shell(title: str, path: str, content: str, *, member: bool, indexable: bool = False, structured_data=None,
           description: str = DESCRIPTION, share_image: Optional[str] = None):
    head = (f'<link rel="stylesheet" href="/static/pick-swap.css?v={CSS_VERSION}">'
            f'<script src="/static/pick-swap.js?v={JS_VERSION}" defer></script>')
    title = title.replace("{", "(").replace("}", ")")
    description = description.replace("{", "(").replace("}", ")")
    response = page(title, description, path, content, indexable=indexable, head=head, member=member,
                    structured_data=structured_data, share_image=share_image)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


def _message(title: str, heading: str, message: str, actions, status: int = 404):
    from ..csp import strict_html_response
    from ..site_chrome import message_page
    response = strict_html_response(message_page(title, heading, message, actions=actions), status_code=status)
    _private(response)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _sample() -> str:
    """A static picture of unwrap day for visitors: one opened pick and the group's boxes."""
    boxes = "".join(
        f'<li class="ps-box{" ps-box--open" if opened else ""}"><span class="ps-box__lid" aria-hidden="true"></span>'
        f'<span class="ps-box__body" aria-hidden="true"></span><small>{name}</small></li>'
        for name, opened in (("You", True), ("Sam", True), ("Priya", True), ("Jo", False), ("Lee", True)))
    return (
        '<figure class="ps-sample" aria-label="An example: unwrap day in a swap of five">'
        '<div class="ps-gift ps-gift--sample">'
        '<span class="ps-art ps-art--big"><span class="ps-art__empty" aria-hidden="true">A</span></span>'
        '<div class="ps-gift__copy"><p class="ps-gift__from">From Priya</p>'
        '<h3>Arcane</h3><p class="ps-gift__facts">TV show · 2021</p>'
        '<blockquote class="ps-gift__note">You said you wanted something animated that doesn\'t feel like it\'s for '
        'kids. Watch the first three episodes in one go, they\'re written as one act.</blockquote></div></div>'
        f'<ul class="ps-boxes ps-boxes--sample">{boxes}</ul>'
        '<figcaption>Four picks open, one still wrapped. Jo had until 8 a.m. and is about to hear about it.</figcaption>'
        '</figure>')


STEPS = ('<ol class="ps-steps">'
         '<li><strong>Start a swap</strong><span>Name it, pick an unwrap day, and say what counts: anything, or only '
         'books, films, games, albums.</span></li>'
         '<li><strong>Send the link</strong><span>Friends join in one tap. Anyone new makes a free account and the link '
         'brings them straight back.</span></li>'
         '<li><strong>Draw names</strong><span>Press the button when everyone is in, or set a draw day. Each person '
         'learns only who they drew.</span></li>'
         '<li><strong>Pick and wrap</strong><span>One title for the person you drew, and a line on why. You see their '
         'wish and a few things they loved.</span></li>'
         '<li><strong>Unwrap together</strong><span>Everything opens at 8 a.m. on unwrap day. Save yours to your list '
         'in one tap, and see what everyone gave.</span></li></ol>')


def _themes_html() -> str:
    items = "".join(
        f'<li><strong>{_e(theme["name"])}</strong><span>{_e(theme["note"])}</span></li>'
        for theme in pick_swap.THEMES[1:])
    return f'<ul class="ps-themes">{items}</ul>'


GUIDE = (
    '<section class="ps-guide editorial" aria-labelledby="psGuideTitle">'
    '<h2 id="psGuideTitle">How to run a recommendation swap</h2>'
    '<p>A recommendation swap works like Secret Santa, with one change: instead of buying something, you give the '
    'person you drew one thing to watch, read, play or listen to, and you tell them why you picked it. Nobody spends '
    'money, it works for a group spread across cities, and the note ends up mattering more than the title. Most '
    'people remember the friend who handed them a book with "you\'ll see why by chapter four" written inside.</p>'
    '<h3>Pick a theme, or don\'t</h3>'
    '<p>"Anything goes" is fine for a first swap. A theme makes it easier for people who freeze when the choice is '
    'everything ever made, and it makes unwrap day more fun because you can compare picks. A few that work well:</p>'
    + _themes_html() +
    '<p>If you set a format, the swap only takes picks of that kind. Write any other rules in the swap\'s note, '
    'like "something under two hours" or "nothing you\'ve recommended to me before".</p>'
    '<h3>Write a good note</h3>'
    '<p>The note is the gift. Say why this one is for this person, not why it\'s good in general: "you loved the '
    'heist bits of Ocean\'s Eleven" beats "it has great reviews". Then say how to start it. Which episode it gets '
    'good, whether to read the introduction, which track to wait for, whether the sequel is worth it. One honest '
    'warning helps too: "the first twenty minutes are slow" saves a lot of people from giving up.</p>'
    '<h3>Check what they\'ve already seen</h3>'
    '<p>Nothing deflates unwrap day like "oh, I watched that last year". Once names are drawn, the swap shows you '
    'the wish line the person wrote when they joined and a few titles they rated highly on shelves they share. If '
    'your pick is already in their library, the swap asks before wrapping it. Shelves someone keeps private or '
    'hidden are never shown and never checked.</p>'
    '<h3>Dates that work</h3>'
    '<p>Give people about a week between the draw and unwrap day. Less than that and the person who drew the hardest '
    'name panics. More than two weeks and people forget. Put unwrap day on a day the group already shares: Christmas '
    'morning, the last day before a break, the office party, the next book club. Everything opens at 8 a.m. in the '
    'host\'s time zone, and anyone who hasn\'t picked gets a reminder two days before.</p>'
    '<h3>How many people</h3>'
    '<p>Two to thirty, and it\'s more of a surprise with four or more. Two people simply trade picks. With three, '
    'whoever you didn\'t draw must have drawn you, so only the pick itself is a secret. From four up, nobody can work '
    'out who drew them until unwrap day, which is the point. The draw goes in one loop through everyone, so no two '
    'people end up just swapping with each other. If someone drops out after the draw, the person who drew them picks '
    'for whoever they had drawn, and the swap tells them.</p>'
    '<h3>Questions people ask</h3>'
    '<dl class="ps-faq">'
    '<dt>Do my friends need an account?</dt><dd>Yes, a free one, so the swap can tell them who they drew and keep '
    'their pick secret. The invite link brings them straight back to join after signing up, and they become friends '
    'with whoever sent it.</dd>'
    '<dt>Can I see who drew me?</dt><dd>Not before unwrap day. The swap only shows how many picks are wrapped. On '
    'unwrap day everyone sees every pick, who gave it and the note.</dd>'
    '<dt>Is it only for Christmas?</dt><dd>No. It works for a book club\'s summer swap, a birthday month, a group '
    'chat that never agrees on what to watch, or two friends who want to trade one pick a month.</dd>'
    '<dt>What happens to my pick afterwards?</dt><dd>You can save it to your library or put it at the top of your '
    'Up next queue in one tap. The library remembers who recommended it, so you can thank them properly once you\'ve '
    'finished it.</dd></dl>'
    '</section>'
)


@router.get("/swap", include_in_schema=False)
def swap_page(request: Request, user=Depends(get_optional_current_user)):
    title = "Pick swap: Secret Santa for movie, book and game recommendations"
    if user is None:
        back = quote("/swap", safe="")
        content = (
            '<header class="hero ps-hero"><p class="eyebrow">PICK SWAP · SECRET SANTA FOR RECOMMENDATIONS</p>'
            '<h1>Secret Santa, but everyone gives a recommendation</h1>'
            '<p>Start a swap, send the link to the group chat and draw names. Everyone picks one film, show, book, game '
            'or album for the person they drew, with a line on why. On unwrap day you all find out what you got and who '
            'picked it.</p>'
            f'<div class="ps-hero__actions"><a class="button" rel="nofollow" href="/?next={back}#signup" '
            'data-swap-signup>Start a swap free</a>'
            f'<a class="button button--ghost" rel="nofollow" href="/?next={back}#login">I have an account</a></div>'
            '</header>'
            f'<section class="ps-intro" aria-label="What unwrap day looks like">{_sample()}'
            f'<div class="ps-intro__steps">{STEPS}</div></section>'
            + GUIDE)
        return _shell(title, "/swap", content, member=False, indexable=True, structured_data={
            "@context": "https://schema.org", "@type": "WebPage", "name": title, "description": DESCRIPTION,
            "url": "https://omnitrackr.xyz/swap", "inLanguage": "en-US",
            "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"},
        })
    content = (
        '<header class="hero ps-hero ps-hero--member"><p class="eyebrow">PICK SWAP · SECRET SANTA FOR RECOMMENDATIONS</p>'
        '<h1>Pick swap</h1>'
        '<p>Draw names, give the person you drew one thing to watch, read, play or hear, and open everything together '
        'on unwrap day.</p></header>'
        '<section class="ps-app" id="swapApp" data-view="hub">'
        '<section class="ps-mine" aria-labelledby="psMineTitle"><h2 id="psMineTitle">Your swaps</h2>'
        '<div data-swap-mine><p class="ps-muted">Loading…</p></div></section>'
        '<section class="ps-start" id="start" aria-labelledby="psStartTitle"><h2 id="psStartTitle">Start a swap</h2>'
        '<div data-swap-start><p class="ps-muted">Loading…</p></div></section>'
        '<noscript><p>Pick swap needs JavaScript.</p></noscript></section>'
        + GUIDE
    )
    return _shell("Pick swap", "/swap", content, member=True, indexable=True)


@router.get("/swap/join/{token}", include_in_schema=False)
def join_page(token: str, request: Request, tz: int = Tz, user=Depends(get_optional_current_user),
              db: Session = Depends(get_db)):
    swap = pick_swap.by_token(db, token)
    if swap is None:
        return _message("Link expired", "This link doesn't work anymore",
                        "Whoever sent it may have made a new one. Ask them for the latest link, or start your own swap.",
                        (("Start a swap", "/swap"), ("See what OmniTrackr does", "/about")))
    pick_swap.advance(db, swap)
    info = pick_swap.preview(db, swap, pick_swap.local_today(tz))
    path = pick_swap.invite_path(swap)
    member = pick_swap.member_of(db, swap.id, user.id) if user is not None else None
    owner = info["owner"] or "A friend"
    people = ", ".join(_e(name) for name in info["people"][:12])
    if len(info["people"]) > 12:
        people += f" and {len(info['people']) - 12} more"
    if member is not None:
        actions = f'<a class="button" href="{_e(pick_swap.link_for(swap))}">Open the swap</a>'
    elif info["state"] == "cancelled":
        actions = '<p class="ps-muted">This swap was called off. Start your own with the button below.</p>'
    elif info["state"] != "open":
        actions = ('<p class="ps-muted">Names have been drawn for this one, so it\'s closed to new people. '
                   'Start your own, it takes a minute.</p><a class="button" href="/swap">Start a swap</a>')
    elif info["full"]:
        actions = '<p class="ps-muted">This swap is full. Ask whoever runs it to make room.</p>'
    elif user is not None and pick_swap.removed_from(db, swap.id, user.id):
        actions = f'<p class="ps-muted">{_e(pick_swap.REMOVED_MESSAGE)}</p>'
    elif user is not None:
        actions = (f'<div class="ps-join" data-swap-join data-token="{_e(swap.token)}">'
                   '<p class="ps-muted">Loading…</p></div>')
    else:
        funnel.record("swap_link_opened", request)
        back = quote(path, safe="")
        invite = db.query(models.FriendInvite).filter(models.FriendInvite.user_id == swap.owner_id).first()
        join = (f"/?invite={quote(invite.token)}&next={back}#signup" if invite is not None else f"/?next={back}#signup")
        actions = (f'<a class="button" rel="nofollow" href="{_e(join)}" data-swap-signup>Join free</a>'
                   f'<a class="button button--ghost" rel="nofollow" href="/?next={back}#login">I have an account</a>'
                   '<p class="ps-muted ps-invite__small">OmniTrackr is a free tracker for films, shows, anime, books, '
                   f'games and music. Make an account and you and {_e(owner)} become friends, and this link brings you '
                   'straight back here to join.</p>')
    draw = (f'Names drawn {_e(info["draw_label"])}' if info["draw_label"] and info["state"] == "open"
            else ("Names drawn" if info["state"] != "open" else f'{_e(owner)} draws names when everyone is in'))
    note = f'<p class="ps-invite__note">{_e(info["note"])}</p>' if info["note"] else ""
    content = (
        '<section class="ps-invite" id="swapApp" data-view="join">'
        f'<p class="eyebrow">{_e(owner).upper()} INVITED YOU TO A PICK SWAP</p>'
        '<div class="ps-invite__card"><span class="ps-invite__bow" aria-hidden="true"></span>'
        f'<div class="ps-invite__copy"><h1>{_e(info["name"])}</h1>'
        f'<p class="ps-invite__facts">{_e(info["kinds_label"])}</p>'
        f'<p class="ps-invite__dates"><strong>Unwrap day {_e(info["reveal_label"])}</strong> · {draw}</p>'
        f'{note}<p class="ps-invite__who">In it so far: {people}</p></div></div>'
        '<p class="ps-invite__lead">It\'s Secret Santa with recommendations. Everyone draws a name and picks one thing '
        'for that person to watch, read, play or hear, with a line on why. Nobody sees what they got, or who it came '
        'from, until unwrap day.</p>'
        f'<div class="ps-invite__actions">{actions}</div>'
        '<p class="ps-status" data-swap-status role="status" aria-live="polite"></p>'
        '</section>'
    )
    version = hashlib.sha256(json.dumps(pick_swap.card_facts(db, swap), sort_keys=True).encode()).hexdigest()[:10]
    from ..digest import app_url
    response = _shell(f"Join {info['name']}: a pick swap", path, content, member=user is not None,
                      description=f"{owner} invited you to {info['name']}, a Secret Santa where everyone gives one "
                                  f"recommendation. Unwrap day is {info['reveal_label']}.",
                      share_image=f"{app_url()}{path}/card.png?v={version}")
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cache-Control"] = "private, no-store"
    return response


_CARDS = None


def _card_cache():
    global _CARDS
    if _CARDS is None:
        from .profiles import _CardCache
        _CARDS = _CardCache(size=96)
    return _CARDS


@router.get("/swap/join/{token}/card.png", include_in_schema=False)
def invite_card(token: str, request: Request, db: Session = Depends(get_db)):
    """The image chat apps show for an invite link."""
    swap = pick_swap.by_token(db, token)
    if swap is None:
        raise HTTPException(404, "This link doesn't work anymore")
    facts = pick_swap.card_facts(db, swap)
    fingerprint = hashlib.sha256(json.dumps(facts, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    etag = f'"{fingerprint}"'
    headers = {"Cache-Control": "private, max-age=300", "ETag": etag, "X-Content-Type-Options": "nosniff",
               "X-Robots-Tag": "noindex"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    cache = _card_cache()
    png = cache.get(("swap", swap.id, fingerprint))
    if png is None:
        from .. import pick_swap_card
        try:
            png = pick_swap_card.render(facts)
        except Exception:
            raise HTTPException(404, "Card unavailable")
        cache.put(("swap", swap.id, fingerprint), png)
    return Response(content=png, media_type="image/png", headers=headers)


@router.get("/swap/{swap_id}", include_in_schema=False)
def swap_detail_page(swap_id: PositiveDatabaseId, request: Request, user=Depends(get_optional_current_user),
                     db: Session = Depends(get_db)):
    path = f"/swap/{swap_id}"
    if user is None:
        back = quote(path, safe="")
        return _message("Log in to see this swap", "Log in to see this swap",
                        "Swaps are only shown to the people in them. Log in and you'll come straight back here.",
                        (("Log in", f"/?next={back}#login"), ("Create a free account", f"/?next={back}#signup")),
                        status=200)
    swap = db.get(models.PickSwap, swap_id)
    member = pick_swap.member_of(db, swap_id, user.id) if swap is not None else None
    if swap is None or member is None:
        return _message("Swap not found", "This swap isn't here",
                        "It may have been called off, or you're not in it. Ask whoever runs it for the invite link.",
                        (("Your swaps", "/swap"), ("Go to my library", "/")))
    if request.query_params.get("utm_campaign") == "swap" and request.query_params.get("utm_source") == "email":
        funnel.record("swap_back_from_email", request)
    content = (
        f'<section class="ps-app ps-swap" id="swapApp" data-view="swap" data-swap-id="{swap.id}">'
        '<p class="ps-back"><a href="/swap">← All your swaps</a></p>'
        '<header class="ps-swap__head"><p class="eyebrow">PICK SWAP</p>'
        f'<h1>{_e(swap.name)}</h1><p class="ps-swap__facts" data-swap-facts></p></header>'
        '<div data-swap-body><p class="ps-muted" role="status">Loading the swap…</p></div>'
        '<noscript><p>Pick swap needs JavaScript.</p></noscript></section>'
    )
    response = _shell(swap.name, path, content, member=True)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cache-Control"] = "private, no-store"
    return response


# ------------------------------------------------------------------ API

def _swap_for(db: Session, swap_id: int, user):
    try:
        return pick_swap.get_for_member(db, swap_id, user)
    except pick_swap.SwapError as error:
        _fail(error)


def _detail(db: Session, swap_id: int, user, tz: int) -> dict:
    swap, member = _swap_for(db, swap_id, user)
    return pick_swap.detail(db, swap, member, user, pick_swap.local_today(tz))


@router.get("/api/swaps")
def my_swaps(request: Request, response: Response, tz: int = Tz, user=Depends(get_current_user),
             db: Session = Depends(get_db)):
    _private(response)
    return pick_swap.mine(db, user, pick_swap.local_today(tz))


@router.get("/api/swaps/start")
def start_options(request: Request, response: Response, tz: int = Tz, user=Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """What the start form needs: themes, formats, friends to ask, and a sensible unwrap day."""
    _private(response)
    from datetime import timedelta
    from ..crud.friends import get_friends
    today = pick_swap.local_today(tz)
    christmas = date(today.year, 12, 25)
    suggested = christmas if today.month in (11, 12) and (christmas - today).days >= 5 else today + timedelta(days=14)
    friends = [{"id": friend.id, "username": friend.username} for friend in get_friends(db, user.id) if friend.is_active]
    return {"themes": list(pick_swap.THEMES), "kinds": [{"key": key, "label": label, "plural": pick_swap.KIND_PLURAL[key]}
                                                        for key, label in pick_swap.KIND_LABEL.items()],
            "friends": friends[:50], "reveal_on": suggested.isoformat(), "today": today.isoformat(),
            "latest": (today + timedelta(days=pick_swap.REVEAL_WITHIN_DAYS)).isoformat(),
            "active": pick_swap.active_count(db, user.id), "active_max": pick_swap.ACTIVE_MAX}


@router.post("/api/swaps", status_code=201)
def create_swap(payload: SwapCreate, request: Request, response: Response, tz: int = Tz,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    try:
        swap = pick_swap.create(db, user, name=payload.name, note=payload.note, kinds=payload.kinds,
                                draw_on=payload.draw_on, reveal_on=payload.reveal_on, tz=tz, wish=payload.wish,
                                today=pick_swap.local_today(tz))
    except pick_swap.SwapError as error:
        db.rollback()
        _fail(error)
    asked = pick_swap.invite_friends(db, swap, user, payload.friend_ids)
    db.commit()
    from .. import friend_invites
    friend_invites.link_for(db, user)  # Visitors who join from the invite become the host's friend.
    funnel.record("swap_created", request)
    return {"id": swap.id, "path": pick_swap.link_for(swap), "invite_url": pick_swap.invite_url(swap), "asked": asked}


@router.get("/api/swaps/join/{token}")
def join_preview(token: str, request: Request, response: Response, tz: int = Tz, user=Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _private(response)
    swap = pick_swap.by_token(db, token)
    if swap is None:
        raise HTTPException(404, "This link doesn't work anymore")
    info = pick_swap.preview(db, swap, pick_swap.local_today(tz))
    member = pick_swap.member_of(db, swap.id, user.id)
    return {**info, "member": member is not None,
            "path": pick_swap.link_for(swap) if member is not None else None}


@router.post("/api/swaps/join/{token}")
def join_swap(token: str, payload: Wish, request: Request, response: Response, user=Depends(get_current_user),
              db: Session = Depends(get_db)):
    _private(response)
    swap = pick_swap.by_token(db, token)
    if swap is None:
        raise HTTPException(404, "This link doesn't work anymore")
    try:
        _member, joined = pick_swap.join(db, swap, user, wish=payload.wish)
    except pick_swap.SwapError as error:
        db.rollback()
        _fail(error)
    return {"path": pick_swap.link_for(swap), "joined": joined}


@router.get("/api/swaps/{swap_id}")
def swap_detail(swap_id: PositiveDatabaseId, request: Request, response: Response, tz: int = Tz,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return _detail(db, swap_id, user, tz)


@router.patch("/api/swaps/{swap_id}")
def update_swap(swap_id: PositiveDatabaseId, payload: SwapUpdate, request: Request, response: Response, tz: int = Tz,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    swap, _member = _swap_for(db, swap_id, user)
    try:
        pick_swap.update(db, swap, user, name=payload.name, note=payload.note, kinds=payload.kinds,
                         draw_on=payload.draw_on, clear_draw=payload.clear_draw, reveal_on=payload.reveal_on,
                         today=pick_swap.local_today(tz))
    except pick_swap.SwapError as error:
        db.rollback()
        _fail(error)
    return _detail(db, swap_id, user, tz)


@router.patch("/api/swaps/{swap_id}/me")
def update_wish(swap_id: PositiveDatabaseId, payload: Wish, request: Request, response: Response, tz: int = Tz,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    swap, member = _swap_for(db, swap_id, user)
    try:
        pick_swap.set_wish(db, swap, member, payload.wish)
    except pick_swap.SwapError as error:
        _fail(error)
    return _detail(db, swap_id, user, tz)


@router.post("/api/swaps/{swap_id}/draw")
def draw_names(swap_id: PositiveDatabaseId, request: Request, response: Response, tz: int = Tz,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    swap, _member = _swap_for(db, swap_id, user)
    if swap.owner_id != user.id:
        raise HTTPException(403, "Only the host can draw names.")
    try:
        pick_swap.draw(db, swap)
    except pick_swap.SwapError as error:
        db.rollback()
        _fail(error)
    return _detail(db, swap_id, user, tz)


@router.put("/api/swaps/{swap_id}/gift")
def wrap_gift(swap_id: PositiveDatabaseId, payload: Gift, request: Request, response: Response, tz: int = Tz,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    swap, member = _swap_for(db, swap_id, user)
    try:
        result = pick_swap.set_gift(db, swap, member, user, kind=payload.kind, title=payload.title, year=payload.year,
                                    image=payload.image, slug=payload.slug, creator=payload.creator,
                                    note=payload.note, anyway=payload.anyway)
    except pick_swap.SwapError as error:
        db.rollback()
        _fail(error)
    if not result["saved"]:
        return result
    return {**result, "swap": _detail(db, swap_id, user, tz)}


@router.delete("/api/swaps/{swap_id}/gift")
def unwrap_own_gift(swap_id: PositiveDatabaseId, request: Request, response: Response, tz: int = Tz,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    swap, member = _swap_for(db, swap_id, user)
    try:
        pick_swap.clear_gift(db, swap, member)
    except pick_swap.SwapError as error:
        _fail(error)
    return _detail(db, swap_id, user, tz)


@router.post("/api/swaps/{swap_id}/unwrap")
def unwrap_early(swap_id: PositiveDatabaseId, request: Request, response: Response, tz: int = Tz,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The host opens everything before unwrap day, once every pick is wrapped."""
    _private(response)
    swap, _member = _swap_for(db, swap_id, user)
    try:
        pick_swap.reveal(db, swap, early_by=user)
    except pick_swap.SwapError as error:
        db.rollback()
        _fail(error)
    return _detail(db, swap_id, user, tz)


@router.post("/api/swaps/{swap_id}/received/open")
def open_received(swap_id: PositiveDatabaseId, request: Request, response: Response,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    swap, _member = _swap_for(db, swap_id, user)
    try:
        first = pick_swap.open_gift(db, swap, user)
    except pick_swap.SwapError as error:
        _fail(error)
    return {"first": first}


@router.post("/api/swaps/{swap_id}/received/add")
def add_received(swap_id: PositiveDatabaseId, payload: GiftAdd, request: Request, response: Response,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    swap, _member = _swap_for(db, swap_id, user)
    try:
        return pick_swap.add_gift(db, swap, user, queue=payload.queue)
    except pick_swap.SwapError as error:
        db.rollback()
        _fail(error)


@router.post("/api/swaps/{swap_id}/received/thanks")
def thank_giver(swap_id: PositiveDatabaseId, payload: Thanks, request: Request, response: Response, tz: int = Tz,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    swap, _member = _swap_for(db, swap_id, user)
    try:
        pick_swap.thank(db, swap, user, payload.reaction)
    except pick_swap.SwapError as error:
        _fail(error)
    return _detail(db, swap_id, user, tz)


@router.get("/api/swaps/{swap_id}/friends")
def friends_to_ask(swap_id: PositiveDatabaseId, request: Request, response: Response, user=Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _private(response)
    swap, _member = _swap_for(db, swap_id, user)
    from ..crud.friends import get_friends
    inside = {user_id for user_id, in db.query(models.PickSwapMember.user_id).filter_by(swap_id=swap.id)}
    if swap.owner_id != user.id:
        inside |= {user_id for user_id, in db.query(models.PickSwapRemoval.user_id).filter_by(swap_id=swap.id)}
    return {"friends": [{"id": friend.id, "username": friend.username}
                        for friend in get_friends(db, user.id) if friend.is_active and friend.id not in inside][:50]}


@router.post("/api/swaps/{swap_id}/invite")
def ask_friends(swap_id: PositiveDatabaseId, payload: Invite, request: Request, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    swap, _member = _swap_for(db, swap_id, user)
    if pick_swap.state_of(swap) != "open":
        raise HTTPException(409, "Names are drawn, so nobody new can join.")
    asked = pick_swap.invite_friends(db, swap, user, payload.friend_ids)
    db.commit()
    return {"asked": asked}


@router.post("/api/swaps/{swap_id}/link")
def reset_link(swap_id: PositiveDatabaseId, request: Request, response: Response, user=Depends(get_current_user),
               db: Session = Depends(get_db)):
    """A new invite link. The old one stops working; people already in stay in."""
    _private(response)
    swap, _member = _swap_for(db, swap_id, user)
    try:
        url = pick_swap.new_link(db, swap, user)
    except pick_swap.SwapError as error:
        _fail(error)
    return {"invite_url": url, "invite_path": pick_swap.invite_path(swap)}


@router.post("/api/swaps/{swap_id}/leave")
def leave_swap(swap_id: PositiveDatabaseId, request: Request, response: Response, user=Depends(get_current_user),
               db: Session = Depends(get_db)):
    _private(response)
    swap, member = _swap_for(db, swap_id, user)
    try:
        kept = pick_swap.leave(db, swap, member, user)
    except pick_swap.SwapError as error:
        db.rollback()
        _fail(error)
    return {"left": True, "swap_kept": kept}


@router.delete("/api/swaps/{swap_id}/members/{member_id}")
def take_out(swap_id: PositiveDatabaseId, member_id: PositiveDatabaseId, request: Request, response: Response,
             tz: int = Tz, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    swap, _member = _swap_for(db, swap_id, user)
    try:
        pick_swap.remove(db, swap, user, member_id)
    except pick_swap.SwapError as error:
        db.rollback()
        _fail(error)
    return _detail(db, swap_id, user, tz)


@router.post("/api/swaps/{swap_id}/cancel")
def call_off(swap_id: PositiveDatabaseId, request: Request, response: Response, user=Depends(get_current_user),
             db: Session = Depends(get_db)):
    _private(response)
    swap, _member = _swap_for(db, swap_id, user)
    try:
        pick_swap.cancel(db, swap, user)
    except pick_swap.SwapError as error:
        _fail(error)
    return {"cancelled": True}
