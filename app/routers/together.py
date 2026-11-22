"""Watch together (/together): one title, a weekly pace, a shared track and notes that wait for you."""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import funnel, models, title_pages, together
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..integer_bounds import PositiveDatabaseId
from .discover import page

router = APIRouter(tags=["together"])
CSS_VERSION = "20261122-together-1"
JS_VERSION = "20261122-together-sweep-1"
DESCRIPTION = ("Watch a show, read a book or get through a podcast with friends at the same pace, even from different "
               "cities. Everyone's place on one track, a few episodes or chapters a week, and notes that stay hidden "
               "until you get there. Free.")
Tz = Query(0, ge=-14 * 60, le=14 * 60)


def _e(value) -> str:
    # Braces too, so text from a member can never look like a page template placeholder.
    return escape(str(value if value is not None else ""), quote=True).replace("{", "&#123;").replace("}", "&#125;")


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _fail(error: together.TogetherError):
    raise HTTPException(error.status, str(error))


# ------------------------------------------------------------------ payloads

class PlanCreate(BaseModel):
    category: Optional[str] = Field(None, max_length=16)
    item_id: Optional[PositiveDatabaseId] = None
    # A title from search instead of the library: added to the library first.
    kind: Optional[str] = Field(None, max_length=10)
    title: Optional[str] = Field(None, max_length=200)
    year: Optional[int] = Field(None, ge=1800, le=2100)
    image: Optional[str] = Field(None, max_length=500)
    slug: Optional[str] = Field(None, max_length=140)
    season: Optional[int] = Field(None, ge=1, le=200)
    total: int = Field(..., ge=1, le=together.TOTAL_MAX)
    pace: int = Field(..., ge=1, le=together.TOTAL_MAX)
    starts_on: date
    position: int = Field(0, ge=0, le=together.TOTAL_MAX)
    remind_email: bool = True
    friend_ids: list[PositiveDatabaseId] = Field(default_factory=list, max_length=50)


class Move(BaseModel):
    position: int = Field(..., ge=0, le=together.TOTAL_MAX)
    library: bool = True


class NoteWrite(BaseModel):
    part: int = Field(..., ge=0, le=together.TOTAL_MAX)
    body: str = Field(..., max_length=together.NOTE_MAX * 2)


class MeUpdate(BaseModel):
    remind_email: Optional[bool] = None
    follow_library: Optional[bool] = None


class PlanUpdate(BaseModel):
    pace: Optional[int] = Field(None, ge=1, le=together.TOTAL_MAX)
    total: Optional[int] = Field(None, ge=1, le=together.TOTAL_MAX)


class Invite(BaseModel):
    friend_ids: list[PositiveDatabaseId] = Field(..., min_length=1, max_length=50)


class Join(BaseModel):
    position: Optional[int] = Field(None, ge=0, le=together.TOTAL_MAX)
    add_to_library: bool = True
    remind_email: bool = True


class Finish(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=10)


# ------------------------------------------------------------------ pages

def _shell(title: str, path: str, content: str, *, member: bool, indexable: bool = False, structured_data=None,
           description: str = DESCRIPTION, share_image: Optional[str] = None):
    head = (f'<link rel="stylesheet" href="/static/together.css?v={CSS_VERSION}">'
            f'<script src="/static/together.js?v={JS_VERSION}" defer></script>')
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


SAMPLE_PEOPLE = (("You", "ME", 3, "you"), ("Sam", "SA", 4, ""), ("Priya", "PR", 2, ""))


def _sample() -> str:
    """A static picture of a plan for visitors: ten episodes, two a week, three people on the track."""
    cells = []
    for part in range(1, 11):
        week = (part - 1) // 2
        classes = ["tg-cell", f"tg-cell--w{week % 2}"]
        if week == 1:
            classes.append("tg-cell--now")
        pin = ('<span class="tg-pin tg-pin--locked" aria-hidden="true"></span>' if part == 6 else
               '<span class="tg-pin" aria-hidden="true"></span>' if part == 2 else '')
        cells.append(f'<li class="{" ".join(classes)}"><span class="tg-cell__n">{part}</span>{pin}</li>')
    people = "".join(
        f'<li class="tg-sample__person"><span class="tg-avatar{" tg-avatar--you" if you else ""}" aria-hidden="true">'
        f'{initials}</span><span><strong>{name}</strong> <small>episode {at}</small></span>'
        f'<span class="tg-sample__bar" aria-hidden="true"><span style="--tg-share:{at * 10}%"></span></span></li>'
        for name, initials, at, you in SAMPLE_PEOPLE)
    return (
        '<figure class="tg-sample" aria-label="An example: three friends watching a season together">'
        '<p class="tg-sample__head"><strong>Severance, season 1</strong><span>2 episodes a week · week 2 of 5</span></p>'
        f'<ol class="tg-cells tg-cells--sample">{"".join(cells)}</ol>'
        f'<ul class="tg-sample__people">{people}</ul>'
        '<p class="tg-sample__note"><span class="tg-pin tg-pin--locked" aria-hidden="true"></span>'
        'Sam left a note at episode 6. You\'ll see it when you get there.</p>'
        '<figcaption>This week is episodes 3 and 4. Sam is done with them, you\'re halfway, and Priya has one '
        'to catch up on.</figcaption></figure>')


GUIDE = (
    '<section class="tg-guide editorial" aria-labelledby="tgGuideTitle">'
    '<h2 id="tgGuideTitle">How to watch or read something together when you live apart</h2>'
    '<p>Most people have a friend they used to watch things with: a roommate from college, a sibling who moved away, '
    'the coworker who got you into anime. Watching at the same moment is hard once you have different schedules and '
    'time zones. Watching at the same pace is easy. You agree on a stretch for the week, do it whenever suits you, '
    'and talk about it when you both get there. Book clubs have always worked this way.</p>'
    '<h3>Pick a pace you will actually keep</h3>'
    '<p>Two episodes a week is about right for an hour-long drama, and three or four suits a half-hour comedy or a '
    'twenty-minute anime. For books, a few chapters a week beats a page count, because different editions put the '
    'same scene on different pages. Start slower than you think. Everyone catches up on a slow week, while a fast '
    'pace loses people by week three and they quietly stop.</p>'
    '<h3>Agree on spoilers once</h3>'
    '<p>The usual rule is simple: talk about anything up to where the slowest person is, and nothing past it. The '
    'notes on a plan follow that rule for you. A note left at episode 6 stays folded for everyone who is still on '
    'episode 5 or earlier. It opens on its own when you mark episode 6 as watched, so you can react to the big '
    'moment as it happens and your friend reads it right when they get there.</p>'
    '<h3>Let the week carry it</h3>'
    '<p>The plan splits the title into weeks. Each week has its own stretch ("episodes 3 and 4") and a start day. '
    'When someone gets through the week before you, you hear about it, which is usually all the push anyone needs. '
    'If you fall a week behind, nothing breaks. You catch up, or the person who runs the plan slows the pace for '
    'everyone.</p>'
    '<h3>Keep it in step with your library</h3>'
    '<p>If you already log episodes or chapters on OmniTrackr, your place on the plan follows what you log, and '
    'moving forward on the plan moves your library forward too. It never moves your library back, so a rewatch '
    'with a friend leaves your own progress alone. You can switch that off for any plan.</p>'
    '<h3>What it works for</h3>'
    '<p>A season of a TV show or an anime, a long manga, a novel by chapter, a podcast series from the first '
    'episode, an audiobook. It\'s best for two to four people. A plan can hold six, and anyone can join with the '
    'link, so it also works for a small online book club. For a single film or album, a '
    '<a href="/tonight">group poll</a> or a <a href="/lists">watch club</a> on a shared list is the better fit.</p>'
    '</section>'
)

STEPS = ('<ol class="tg-steps">'
         '<li><strong>Pick something</strong><span>A show, anime, book, manga, podcast or audiobook from your library, '
         'or search for anything.</span></li>'
         '<li><strong>Set a pace</strong><span>How many episodes or chapters a week, and the day you start.</span></li>'
         '<li><strong>Send the link</strong><span>Friends join in one tap. Everyone sees where everyone is, and notes '
         'wait until you reach them.</span></li></ol>')


@router.get("/together", include_in_schema=False)
def together_page(request: Request, user=Depends(get_optional_current_user)):
    if user is None:
        back = quote("/together", safe="")
        content = (
            '<header class="hero tg-hero"><p class="eyebrow">WATCH TOGETHER · READ TOGETHER</p>'
            '<h1>Same show, same pace, different couches</h1>'
            '<p>Pick a season, a book or a podcast, agree on a few episodes or chapters a week, and send the link. '
            'Everyone sees where everyone is. Notes stay hidden until you get to the part they\'re about.</p>'
            f'<div class="tg-hero__actions"><a class="button" rel="nofollow" href="/?next={back}#signup" '
            'data-together-signup>Start one free</a>'
            f'<a class="button button--ghost" rel="nofollow" href="/?next={back}#login">I have an account</a></div>'
            '</header>'
            f'<section class="tg-intro" aria-label="What a plan looks like">{_sample()}'
            f'<div class="tg-intro__steps">{STEPS}</div></section>'
            + GUIDE)
        return _shell("Watch together: a show or book with friends at the same pace", "/together", content,
                      member=False, indexable=True, structured_data={
                          "@context": "https://schema.org", "@type": "WebPage",
                          "name": "Watch together: a show or book with friends at the same pace",
                          "description": DESCRIPTION, "url": "https://omnitrackr.xyz/together", "inLanguage": "en-US",
                          "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"},
                      })
    content = (
        '<header class="hero tg-hero tg-hero--member"><p class="eyebrow">WATCH TOGETHER · READ TOGETHER</p>'
        '<h1>Watch it together</h1>'
        '<p>One title, a few episodes or chapters a week, and friends on the same track. Notes stay hidden until '
        'each person gets there.</p></header>'
        '<section class="tg-app" id="togetherApp" data-view="hub">'
        '<section class="tg-mine" aria-labelledby="tgMineTitle"><h2 id="tgMineTitle">Your plans</h2>'
        '<div data-together-mine><p class="tg-muted">Loading…</p></div></section>'
        '<section class="tg-start" id="start" aria-labelledby="tgStartTitle"><h2 id="tgStartTitle">Start one</h2>'
        '<div data-together-start><p class="tg-muted">Loading your library…</p></div></section>'
        '<noscript><p>Watch together needs JavaScript.</p></noscript></section>'
        + GUIDE
    )
    return _shell("Watch together", "/together", content, member=True, indexable=True)


@router.get("/together/join/{token}", include_in_schema=False)
def join_page(token: str, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    plan = together.by_token(db, token)
    if plan is None:
        return _message("Link expired", "This link doesn't work anymore",
                        "Whoever sent it may have made a new one. Ask them for the latest link, or start your own plan.",
                        (("Start a plan", "/together"), ("See what OmniTrackr does", "/about")))
    info = together.preview(db, plan, together.local_today())
    path = together.invite_path(plan)
    member = together.member_of(db, plan.id, user.id) if user is not None else None
    owner = info["owner"] or "A friend"
    art = (f'<img src="{_e(info["image"])}" alt="" width="120" height="180" referrerpolicy="no-referrer" '
           f'data-letter="{_e(info["title"][:1].upper())}">'
           if info["image"] else f'<span class="tg-art__empty" aria-hidden="true">{_e(info["title"][:1].upper())}</span>')
    facts = " · ".join(part for part in (info["label"], info["scope"], info["length"]) if part)
    when = (f'Week {info["week"]} of {info["weeks"]} now' if info["started"] else f'Starts {info["starts_label"]}')
    people = ", ".join(_e(name) for name in info["people"])
    if member is not None:
        actions = f'<a class="button" href="/together/{plan.id}">Open the plan</a>'
    elif info["ended"]:
        actions = '<p class="tg-muted">This plan has finished. Start your own with the button below.</p>'
    elif info["full"]:
        actions = '<p class="tg-muted">This plan is full. Ask whoever runs it to make room.</p>'
    elif user is not None and together.removed_from(db, plan.id, user.id):
        actions = f'<p class="tg-muted">{_e(together.REMOVED_MESSAGE)}</p>'
    elif user is not None:
        actions = ('<div class="tg-join" data-together-join data-token="' + _e(plan.token) + '" data-total="'
                   + str(plan.total) + '" data-unit="' + _e(plan.unit) + '"><p class="tg-muted">Loading…</p></div>')
    else:
        funnel.record("together_link_opened", request)
        back = quote(path, safe="")
        invite = db.query(models.FriendInvite).filter(models.FriendInvite.user_id == plan.owner_id).first()
        join = (f"/?invite={quote(invite.token)}&next={back}#signup" if invite is not None else f"/?next={back}#signup")
        actions = (f'<a class="button" rel="nofollow" href="{_e(join)}" data-together-signup>Join free</a>'
                   f'<a class="button button--ghost" rel="nofollow" href="/?next={back}#login">I have an account</a>'
                   '<p class="tg-muted tg-invite__small">OmniTrackr is a free tracker for shows, anime, books, games '
                   f'and more. Make an account and you and {_e(owner)} become friends, and this link brings you '
                   'straight back here to join.</p>')
    content = (
        f'<section class="tg-invite" id="togetherApp" data-view="join">'
        f'<p class="eyebrow">{_e(owner).upper()} INVITED YOU</p>'
        f'<div class="tg-invite__card"><span class="tg-art tg-art--big">{art}</span>'
        f'<div class="tg-invite__copy"><h1>{_e(info["verb"])} {_e(info["title"])} together</h1>'
        f'<p class="tg-invite__facts">{_e(facts)}</p>'
        f'<p class="tg-invite__pace"><strong>{_e(info["pace"])}</strong> · {_e(when)} · ends {_e(info["ends_label"])}</p>'
        f'<p class="tg-invite__who">In it so far: {people}</p></div></div>'
        '<p class="tg-invite__lead">Everyone goes at the same pace and sees where everyone else is. Notes left at an '
        f'{_e(plan.unit)} stay hidden until you get there, so nobody spoils anything.</p>'
        f'<div class="tg-invite__actions">{actions}</div>'
        '<p class="tg-status" data-together-status role="status" aria-live="polite"></p>'
        '</section>'
    )
    version = hashlib.sha256(json.dumps(together.card_facts(db, plan), sort_keys=True).encode()).hexdigest()[:10]
    from ..digest import app_url
    response = _shell(f"{info['verb']} {info['title']} together", path, content, member=user is not None,
                      description=f"{owner} wants to {info['verb'].lower()} {info['title']} with you on OmniTrackr, "
                                  f"{info['pace']}. Notes stay hidden until you get there.",
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


@router.get("/together/join/{token}/card.png", include_in_schema=False)
def invite_card(token: str, request: Request, db: Session = Depends(get_db)):
    """The image chat apps show for an invite link."""
    plan = together.by_token(db, token)
    if plan is None:
        raise HTTPException(404, "This link doesn't work anymore")
    facts = together.card_facts(db, plan)
    fingerprint = hashlib.sha256(json.dumps(facts, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    etag = f'"{fingerprint}"'
    headers = {"Cache-Control": "private, max-age=300", "ETag": etag, "X-Content-Type-Options": "nosniff",
               "X-Robots-Tag": "noindex"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    cache = _card_cache()
    png = cache.get(("together", plan.id, fingerprint))
    if png is None:
        from .. import together_card
        try:
            png = together_card.render(facts)
        except Exception:
            raise HTTPException(404, "Card unavailable")
        cache.put(("together", plan.id, fingerprint), png)
    return Response(content=png, media_type="image/png", headers=headers)


@router.get("/together/{plan_id}", include_in_schema=False)
def plan_page(plan_id: PositiveDatabaseId, request: Request, user=Depends(get_optional_current_user),
              db: Session = Depends(get_db)):
    path = f"/together/{plan_id}"
    if user is None:
        back = quote(path, safe="")
        return _message("Log in to see this plan", "Log in to see this plan",
                        "Plans are only shown to the people in them. Log in and you'll come straight back here.",
                        (("Log in", f"/?next={back}#login"), ("Create a free account", f"/?next={back}#signup")),
                        status=200)
    try:
        plan, _member = together.get_for_member(db, plan_id, user)
    except together.TogetherError:
        return _message("Plan not found", "This plan isn't here",
                        "It may have ended, or you're not in it. Ask whoever made it for the invite link.",
                        (("Your plans", "/together"), ("Go to my library", "/")))
    if request.query_params.get("utm_campaign") == "together" and request.query_params.get("utm_source") == "email":
        funnel.record("together_back_from_email", request)
    art = (f'<img src="{_e(plan.image)}" alt="" width="96" height="144" referrerpolicy="no-referrer" '
           f'data-letter="{_e(plan.title[:1].upper())}">'
           if plan.image else f'<span class="tg-art__empty" aria-hidden="true">{_e(plan.title[:1].upper())}</span>')
    facts = " · ".join(part for part in (together.CATEGORIES[plan.category][2], together.scope_label(plan),
                                         together.pace_label(plan)) if part)
    content = (
        f'<section class="tg-app tg-plan" id="togetherApp" data-view="plan" data-plan-id="{plan.id}" '
        f'data-unit="{_e(plan.unit)}">'
        '<p class="tg-back"><a href="/together">← All your plans</a></p>'
        f'<header class="tg-plan__head"><span class="tg-art tg-art--head">{art}</span>'
        f'<div class="tg-plan__copy"><p class="eyebrow">{_e(together.verb(plan)).upper()} TOGETHER</p>'
        f'<h1>{_e(plan.title)}</h1><p class="tg-plan__facts">{_e(facts)}</p>'
        '<p class="tg-plan__headline" data-together-headline></p></div></header>'
        '<div data-together-plan><p class="tg-muted" role="status">Loading the plan…</p></div>'
        '<noscript><p>Watch together needs JavaScript.</p></noscript></section>'
    )
    response = _shell(plan.title, path, content, member=True)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cache-Control"] = "private, no-store"
    return response


# ------------------------------------------------------------------ API

def _plan_for(db: Session, plan_id: int, user):
    try:
        return together.get_for_member(db, plan_id, user)
    except together.TogetherError as error:
        _fail(error)


@router.get("/api/together")
def my_plans(request: Request, response: Response, tz: int = Tz, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return together.mine(db, user, together.local_today(tz))


@router.get("/api/together/titles")
def start_titles(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Titles to start a plan from, and friends to ask."""
    _private(response)
    from ..crud.friends import get_friends
    friends = [{"id": friend.id, "username": friend.username} for friend in get_friends(db, user.id) if friend.is_active]
    return {"titles": together.suggestions(db, user), "friends": friends[:50],
            "active": together.active_count(db, user.id), "active_max": together.ACTIVE_MAX,
            "total_max": together.TOTAL_MAX, "start_within_days": together.START_WITHIN_DAYS,
            "categories": {key: {"kind": kind, "unit": unit, "label": label, "verb": verb}
                           for key, (kind, unit, label, verb, _done) in together.CATEGORIES.items()}}


def _row_for_create(db: Session, user, payload: PlanCreate):
    """The library row a new plan starts from: the member's own, or a searched title added to the library."""
    from .. import pick
    from ..progress import lock_progress_owner
    if payload.item_id is not None:
        if payload.category not in together.CATEGORIES:
            raise HTTPException(422, "Watch together works for TV shows, anime, books, manga, podcasts and audiobooks.")
        row = together.library_row(db, user.id, payload.category, payload.item_id)
        if row is None:
            raise HTTPException(404, "That title isn't in your library anymore.")
        return payload.category, row
    kind = payload.kind
    title = " ".join((payload.title or "").split())
    if kind not in title_pages.KINDS or not title:
        raise HTTPException(422, "Pick a title first.")
    category = title_pages.KINDS[kind][2]
    if category not in together.CATEGORIES:
        raise HTTPException(422, "Watch together works for TV shows, anime, books, manga, podcasts and audiobooks.")
    lock_progress_owner(db, user.id)
    image = payload.image if isinstance(payload.image, str) and payload.image.startswith("https://") else None
    _state, row = pick.add_to_library(db, user, {"kind": kind, "title": title, "year": payload.year, "creator": None},
                                      image=image)
    return category, row


@router.post("/api/together", status_code=201)
def create_plan(payload: PlanCreate, request: Request, response: Response, tz: int = Tz,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    today = together.local_today(tz)
    category, row = _row_for_create(db, user, payload)
    try:
        plan = together.create(db, user, row, category, total=payload.total, pace=payload.pace,
                               starts_on=payload.starts_on, today=today, season=payload.season,
                               position=payload.position, remind_email=payload.remind_email)
    except together.TogetherError as error:
        db.rollback()
        _fail(error)
    asked = together.invite_friends(db, plan, user, payload.friend_ids)
    db.commit()
    from .. import friend_invites
    friend_invites.link_for(db, user)  # Visitors who join from the invite become the owner's friend.
    funnel.record("together_created", request)
    return {"id": plan.id, "path": together.link_for(plan), "invite_url": together.invite_url(plan), "asked": asked}


@router.get("/api/together/join/{token}")
def join_preview(request: Request, token: str, response: Response, tz: int = Tz, user=Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """The join form: the plan, and where the member's own library puts them."""
    _private(response)
    plan = together.by_token(db, token)
    if plan is None:
        raise HTTPException(404, "This link doesn't work anymore")
    info = together.preview(db, plan, together.local_today(tz))
    row = together.find_library_row(db, user.id, plan.category, plan.title)
    at = together.placed(plan, together.checkpoint(db, user.id, plan.category, row.id)) if row is not None else None
    member = together.member_of(db, plan.id, user.id)
    return {**info, "in_library": row is not None, "library_at": at, "member": member is not None,
            "path": together.link_for(plan) if member is not None else None, "unit": plan.unit,
            "unit_plural": together.unit_words(plan)[1]}


@router.post("/api/together/join/{token}")
def join_plan(token: str, payload: Join, request: Request, response: Response, user=Depends(get_current_user),
              db: Session = Depends(get_db)):
    _private(response)
    plan = together.by_token(db, token)
    if plan is None:
        raise HTTPException(404, "This link doesn't work anymore")
    try:
        _member, joined = together.join(db, plan, user, position=payload.position,
                                        add_to_library=payload.add_to_library, remind_email=payload.remind_email)
    except together.TogetherError as error:
        db.rollback()
        _fail(error)
    return {"path": together.link_for(plan), "joined": joined}


@router.get("/api/together/{plan_id}")
def plan_detail(request: Request, plan_id: PositiveDatabaseId, response: Response, tz: int = Tz, user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    _private(response)
    plan, member = _plan_for(db, plan_id, user)
    return together.detail(db, plan, member, user, together.local_today(tz))


@router.put("/api/together/{plan_id}/position")
def move_place(request: Request, plan_id: PositiveDatabaseId, payload: Move, response: Response, tz: int = Tz,
               card: bool = Query(False), user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Move the member's place. From the home card (?card=1) the answer is the home list, and nothing is
    marked as read, since the notes weren't on screen."""
    _private(response)
    plan, member = _plan_for(db, plan_id, user)
    today = together.local_today(tz)
    try:
        moved = together.move(db, plan, member, user, payload.position, today, library=payload.library)
    except together.TogetherError as error:
        db.rollback()
        _fail(error)
    if card:
        return {**together.mine(db, user, today), **moved}
    plan, member = _plan_for(db, plan_id, user)
    return {**together.detail(db, plan, member, user, today), **moved}


@router.post("/api/together/{plan_id}/notes", status_code=201)
def write_note(request: Request, plan_id: PositiveDatabaseId, payload: NoteWrite, response: Response, tz: int = Tz,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    plan, member = _plan_for(db, plan_id, user)
    try:
        together.add_note(db, plan, member, user, payload.part, payload.body)
    except together.TogetherError as error:
        db.rollback()
        _fail(error)
    plan, member = _plan_for(db, plan_id, user)
    return together.detail(db, plan, member, user, together.local_today(tz))


@router.delete("/api/together/{plan_id}/notes/{note_id}")
def remove_note(request: Request, plan_id: PositiveDatabaseId, note_id: PositiveDatabaseId, response: Response, tz: int = Tz,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    plan, member = _plan_for(db, plan_id, user)
    try:
        together.delete_note(db, plan, user, note_id)
    except together.TogetherError as error:
        _fail(error)
    return together.detail(db, plan, member, user, together.local_today(tz))


@router.patch("/api/together/{plan_id}/me")
def update_me(request: Request, plan_id: PositiveDatabaseId, payload: MeUpdate, response: Response, tz: int = Tz,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    plan, member = _plan_for(db, plan_id, user)
    together.set_reminder(db, member, payload.remind_email, payload.follow_library)
    plan, member = _plan_for(db, plan_id, user)
    return together.detail(db, plan, member, user, together.local_today(tz))


@router.patch("/api/together/{plan_id}")
def update_plan(request: Request, plan_id: PositiveDatabaseId, payload: PlanUpdate, response: Response, tz: int = Tz,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    plan, member = _plan_for(db, plan_id, user)
    try:
        together.update_plan(db, plan, user, pace=payload.pace, total=payload.total)
    except together.TogetherError as error:
        db.rollback()
        _fail(error)
    plan, member = _plan_for(db, plan_id, user)
    return together.detail(db, plan, member, user, together.local_today(tz))


@router.post("/api/together/{plan_id}/end")
def end_plan(request: Request, plan_id: PositiveDatabaseId, response: Response, tz: int = Tz, user=Depends(get_current_user),
             db: Session = Depends(get_db)):
    _private(response)
    plan, member = _plan_for(db, plan_id, user)
    try:
        together.end(db, plan, user)
    except together.TogetherError as error:
        _fail(error)
    return together.detail(db, plan, member, user, together.local_today(tz))


@router.post("/api/together/{plan_id}/link")
def reset_link(request: Request, plan_id: PositiveDatabaseId, response: Response, user=Depends(get_current_user),
               db: Session = Depends(get_db)):
    """A new invite link. The old one stops working; people already in the plan stay in."""
    _private(response)
    plan, _ = _plan_for(db, plan_id, user)
    try:
        url = together.new_link(db, plan, user)
    except together.TogetherError as error:
        _fail(error)
    return {"invite_url": url, "invite_path": together.invite_path(plan)}


@router.get("/api/together/{plan_id}/friends")
def friends_to_ask(request: Request, plan_id: PositiveDatabaseId, response: Response, user=Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _private(response)
    plan, _ = _plan_for(db, plan_id, user)
    from ..crud.friends import get_friends
    inside = {user_id for user_id, in db.query(models.TogetherMember.user_id).filter_by(plan_id=plan.id)}
    if plan.owner_id != user.id:
        # Only whoever runs the plan can ask back someone they took out.
        inside |= {user_id for user_id, in db.query(models.TogetherRemoval.user_id).filter_by(plan_id=plan.id)}
    return {"friends": [{"id": friend.id, "username": friend.username}
                        for friend in get_friends(db, user.id) if friend.is_active and friend.id not in inside][:50]}


@router.post("/api/together/{plan_id}/invite")
def ask_friends(request: Request, plan_id: PositiveDatabaseId, payload: Invite, response: Response, user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    _private(response)
    plan, _ = _plan_for(db, plan_id, user)
    if plan.ended_at is not None:
        raise HTTPException(409, "This plan has finished.")
    asked = together.invite_friends(db, plan, user, payload.friend_ids)
    db.commit()
    return {"asked": asked}


@router.post("/api/together/{plan_id}/leave")
def leave_plan(request: Request, plan_id: PositiveDatabaseId, response: Response, user=Depends(get_current_user),
               db: Session = Depends(get_db)):
    _private(response)
    plan, member = _plan_for(db, plan_id, user)
    kept = together.leave(db, plan, member)
    return {"left": True, "plan_kept": kept}


@router.delete("/api/together/{plan_id}/members/{member_id}")
def remove_member(request: Request, plan_id: PositiveDatabaseId, member_id: PositiveDatabaseId, response: Response, tz: int = Tz,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    plan, _ = _plan_for(db, plan_id, user)
    try:
        together.remove(db, plan, user, member_id)
    except together.TogetherError as error:
        _fail(error)
    plan, member = _plan_for(db, plan_id, user)
    return together.detail(db, plan, member, user, together.local_today(tz))


@router.post("/api/together/{plan_id}/finish")
def finish_in_library(request: Request, plan_id: PositiveDatabaseId, payload: Finish, response: Response, tz: int = Tz,
                      user=Depends(get_current_user), db: Session = Depends(get_db)):
    """At the end of a plan: tick the title off in the member's own library, with a score if they give one."""
    _private(response)
    from .. import check_in
    plan, member = _plan_for(db, plan_id, user)
    if (member.position or 0) < plan.total:
        raise HTTPException(409, f"Get to the last {plan.unit} first.")
    if not member.item_id:
        raise HTTPException(404, "This title isn't linked to your library.")
    card = check_in.answer(db, user, plan.category, member.item_id, "finished", payload.rating)
    if card is None:
        raise HTTPException(404, "This title isn't in your library anymore.")
    plan, member = _plan_for(db, plan_id, user)
    return together.detail(db, plan, member, user, together.local_today(tz))
