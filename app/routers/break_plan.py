"""Plan your break (/break): the guide and planner page, the share page and the API (see app/break_plan.py)."""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import break_plan, funnel, models
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..integer_bounds import PositiveDatabaseId
from .discover import page

router = APIRouter(tags=["break plan"])
CSS_VERSION = "20261123-break-1"
JS_VERSION = "20261123-break-1"
TITLE = "Plan your break: fill your days off from your own list"
DESCRIPTION = ("Tell OmniTrackr which days you have off and about how much time each one has, and it fills them "
               "from your own list: the show you're halfway through, the film you keep saving, a book in real "
               "sittings. Free, for Thanksgiving, winter break or any weekend.")
TODAY = Query(None, max_length=10)


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True).replace("{", "&#123;").replace("}", "&#125;")


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _fail(error: break_plan.BreakError):
    raise HTTPException(error.status, str(error))


def _today(value: Optional[str]) -> date:
    return break_plan.local_today(value)


# ------------------------------------------------------------------ payloads

Minutes = dict[str, int]


class Today(BaseModel):
    today: Optional[str] = Field(None, max_length=10)


class PlanCreate(Today):
    starts_on: date
    ends_on: date
    minutes: Minutes = Field(default_factory=dict, max_length=break_plan.MAX_DAYS + 2)
    preset: Optional[str] = Field(None, max_length=32)
    name: Optional[str] = Field(None, max_length=120)
    games: bool = True
    emails: bool = False
    tz: int = Field(0, ge=-14 * 60, le=14 * 60)


class PlanUpdate(Today):
    minutes: Optional[Minutes] = Field(None, max_length=break_plan.MAX_DAYS + 2)
    ends_on: Optional[date] = None
    name: Optional[str] = Field(None, max_length=120)
    games: Optional[bool] = None
    emails: Optional[bool] = None


class Fill(Today):
    day: Optional[date] = None


class AddItem(Today):
    category: str = Field(..., max_length=16)
    item_id: PositiveDatabaseId
    day: date


class MoveItem(Today):
    day: date


class Score(Today):
    rating: Optional[int] = Field(None, ge=1, le=10)


class Rating(Today):
    rating: int = Field(..., ge=1, le=10)


class Demo(BaseModel):
    starts_on: date
    ends_on: date
    minutes: Minutes = Field(default_factory=dict, max_length=break_plan.MAX_DAYS + 2)


def _check_minutes(minutes: Optional[dict]) -> None:
    for key, value in (minutes or {}).items():
        try:
            date.fromisoformat(key)
        except ValueError:
            raise HTTPException(422, "Times are given per day, as YYYY-MM-DD.")
        if not 0 <= int(value) <= 24 * 60:
            raise HTTPException(422, "A day has 24 hours.")


# ------------------------------------------------------------------ pages

def _shell(title: str, path: str, content: str, *, member: bool, indexable: bool = False, structured_data=None,
           description: str = DESCRIPTION, share_image: Optional[str] = None):
    head = (f'<link rel="stylesheet" href="/static/break-plan.css?v={CSS_VERSION}">'
            f'<script src="/static/break-plan.js?v={JS_VERSION}" defer></script>')
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


def _demo_days(today: date) -> tuple[dict, list[dict]]:
    """The preset the guide page opens on and its sample plan, so the page reads without JavaScript."""
    offer = next((entry for entry in break_plan.presets(today) if entry["slug"] != "weekend"), None) \
        or break_plan.presets(today)[0]
    days = break_plan.days_of(offer["starts_on"], offer["ends_on"])
    minutes = break_plan.default_minutes(days, break_plan.DEFAULT_MINUTES, offer["light"])
    return offer, break_plan.demo(offer["starts_on"], minutes)


def _board_html(days: list[dict]) -> str:
    columns = []
    for day in days:
        items = "".join(
            f'<li class="bp-chip" data-category="{_e(entry["category"])}"><span class="bp-chip__kind">'
            f'{_e(entry["kind_label"])}</span><strong>{_e(entry["title"])}</strong>'
            f'<span class="bp-chip__what">{_e(break_plan.what_line(entry))}</span></li>'
            for entry in day["items"])
        if not items:
            items = '<li class="bp-chip bp-chip--rest">A rest day</li>'
        hours = break_plan.hours_words(day["budget"]) if day["budget"] else "Busy"
        columns.append(f'<li class="bp-col"><p class="bp-col__day">{_e(day["label"])}</p>'
                       f'<p class="bp-col__time">{_e(hours)}</p><ul class="bp-col__items">{items}</ul></li>')
    return f'<ol class="bp-board bp-board--demo">{"".join(columns)}</ol>'


STEPS = ('<ol class="bp-steps">'
         '<li><strong>Pick your days</strong><span>Thanksgiving, Christmas to New Year\'s, a long weekend, or any '
         'dates up to 16 days.</span></li>'
         '<li><strong>Say how much time</strong><span>About how long you have on each day. Busy days can be '
         'zero.</span></li>'
         '<li><strong>Get a plan from your list</strong><span>What you\'re halfway through comes first, then '
         'your Up next queue, then things you saved and never started.</span></li>'
         '<li><strong>Tick it off as you go</strong><span>Your library moves along with you, and anything you '
         'don\'t get to can move to another day.</span></li></ol>')

GUIDE = (
    '<section class="bp-guide editorial" aria-labelledby="bpGuideTitle">'
    '<h2 id="bpGuideTitle">How to plan a long weekend of shows, films, books and games</h2>'
    '<p>A four-day weekend feels like a lot of time until Sunday night, when it turns out most of it went on '
    'deciding what to watch. The fix is boring and it works: decide before the break starts, write it down by '
    'day, and keep the list short enough to finish. Here is how we think about it, and how the planner on this '
    'page fills the days for you.</p>'
    '<h3>Count the hours honestly</h3>'
    '<p>A day off is not twelve free hours. Thanksgiving Day is mostly cooking, travel and family, and Christmas '
    'Day is the same for most people, so the planner starts those days at one hour. On an ordinary day off, two '
    'to four hours of screen or reading time is realistic once meals, errands and other people are counted. '
    'Pick a number per day and change any day that is busier. A day set to zero gets nothing.</p>'
    '<h3>Finish what you started first</h3>'
    '<p>The show you stopped halfway through in October is the easiest win of the break, because you already '
    'know you like it and the hardest part (starting) is behind you. The planner puts titles you have progress '
    'on first, then your Up next queue, then titles you saved and never started. A new title only goes on the '
    'plan if the break can finish it, or its first season for a show with several, so the plan ends with things '
    'done instead of five things half-watched.</p>'
    '<h3>Give films and books a real sitting</h3>'
    '<p>A two-hour film wants an evening with nothing else in it, so films and albums go whole onto the day with '
    'the most room. Shows split into stretches of episodes that fit a day. Books get sittings of at least half an '
    'hour (at about forty pages an hour), and games get at least an hour at a time, because nobody gets anywhere '
    'in a game in fifteen minutes.</p>'
    '<h3>One game, at most</h3>'
    '<p>Games are long. A typical one takes twenty hours or more, so a new game takes no more than about two '
    'fifths of the break on its own, and only one goes in unless you add more. If you would rather spend the whole '
    'weekend in one game, add it yourself and the plan works around it. You can also switch games off.</p>'
    '<h3>Leave room for things to go sideways</h3>'
    '<p>Plans slip. Family visits run long, someone wants to watch the parade, a book turns out slower than '
    'expected. Anything you don\'t get to can move to another day, swap for something else on your list, or come '
    'off the plan. If you finish early, the planner fills the free time again.</p>'
    '<h3>Where the lengths come from</h3>'
    '<p>Running times, episode lengths and page counts come from the same sources as your library\'s time '
    'estimates: Wikidata, TVmaze, MyAnimeList and Open Library, and average playtimes from RAWG, once a title page '
    'has looked them up. When we don\'t know a length, the plan says "about" and uses a typical one: 42 minutes '
    'for a TV episode, 24 for anime, 320 pages for a book and 20 hours for a game.</p>'
    '</section>'
)

FAQ = (
    ("Does a plan change my library?",
     "Only when you tick something. Ticking the last part of a film, show, book or manga marks it finished in your "
     "library, the same as ticking it there. Ticking an earlier part moves your saved place forward, never back. "
     "Making, changing or deleting a plan changes nothing in your library."),
    ("What if I log progress in my library instead?",
     "The plan follows it. Mark an episode watched or save a page in your library and the matching parts of the "
     "plan tick themselves."),
    ("Can I plan just a weekend?",
     "Yes. Pick \"This weekend\" or any dates from one day to sixteen. The holiday choices appear in the weeks "
     "before each one: Thanksgiving, Christmas to New Year's and the US long weekends."),
    ("Will you email me about it?",
     "Only if you ask, with the switch on your plan. Then you get two emails: the morning the break starts, with "
     "day one, and the morning after it ends, with how it went."),
    ("Can other people see my plan?",
     "No, unless you make a share link. A shared plan shows titles from the shelves you share on your profile, and "
     "you can turn the link off at any time."),
    ("Is it free?", "Yes, like everything else on OmniTrackr."),
)


def _faq_html() -> str:
    entries = "".join(f'<details class="bp-faq__item"><summary>{_e(question)}</summary><p>{_e(answer)}</p></details>'
                      for question, answer in FAQ)
    return f'<section class="bp-faq" aria-labelledby="bpFaqTitle"><h2 id="bpFaqTitle">Questions</h2>{entries}</section>'


def _structured() -> list[dict]:
    return [
        {"@context": "https://schema.org", "@type": "WebPage", "name": TITLE, "description": DESCRIPTION,
         "url": "https://omnitrackr.xyz/break", "inLanguage": "en-US",
         "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"}},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}}
            for question, answer in FAQ]},
    ]


@router.get("/break", include_in_schema=False)
def break_page(request: Request, user=Depends(get_optional_current_user)):
    today = date.today()
    if request.query_params.get("utm_campaign") == "break" and request.query_params.get("utm_source") == "email":
        funnel.record("break_back_from_email", request)
    if user is None:
        back = quote("/break", safe="")
        offer, sample = _demo_days(today)
        presets = json.dumps([{"key": entry["key"], "name": entry["name"], "starts_on": entry["starts_on"].isoformat(),
                               "ends_on": entry["ends_on"].isoformat(),
                               "span": break_plan.span_label(entry["starts_on"], entry["ends_on"]),
                               "light": [day.isoformat() for day in entry["light"]]}
                              for entry in break_plan.presets(today)])
        content = (
            '<header class="hero bp-hero"><p class="eyebrow">BREAK PLANNER</p>'
            '<h1>Plan your days off from your own list</h1>'
            '<p>Say which days you have and about how much time each one has. The planner fills them from your '
            'list: the show you\'re halfway through, the film you keep saving, a book in real sittings. Then tick '
            'things off as the days go.</p>'
            f'<div class="bp-hero__actions"><a class="button" rel="nofollow" href="/?next={back}#signup" '
            'data-break-signup>Plan mine free</a>'
            f'<a class="button button--ghost" rel="nofollow" href="/?next={back}#login">I have an account</a></div>'
            '</header>'
            f'<section class="bp-demo" id="breakDemo" aria-labelledby="bpDemoTitle" data-presets="{_e(presets)}" '
            f'data-preset="{_e(offer["key"])}">'
            '<div class="bp-demo__head"><h2 id="bpDemoTitle">Try it with a sample list</h2>'
            '<p class="bp-muted">Twelve well-known titles stand in for your library, and you\'re halfway '
            'through Severance. <span data-break-demo-span>This is '
            f'{_e(offer["name"])}, {_e(break_plan.span_label(offer["starts_on"], offer["ends_on"]))}, with 3 '
            'hours a day.</span></p></div>'
            '<div class="bp-demo__controls" data-break-demo-controls hidden></div>'
            f'<div class="bp-demo__board" data-break-demo-board>{_board_html(sample)}</div>'
            '<p class="bp-demo__cta"><a class="button" rel="nofollow" href="/?next='
            f'{back}#signup" data-break-signup>Do this with my list</a></p></section>'
            f'<section class="bp-how" aria-label="How it works">{STEPS}</section>'
            + GUIDE + _faq_html())
        return _shell(TITLE, "/break", content, member=False, indexable=True, structured_data=_structured())
    content = (
        '<header class="hero bp-hero bp-hero--member"><p class="eyebrow">BREAK PLANNER</p>'
        '<h1>Plan your break</h1>'
        '<p>Pick your days and how much time each one has. The plan fills them from your list, and ticking things '
        'off moves your library along.</p></header>'
        '<section class="bp-app" id="breakApp" aria-live="polite">'
        '<p class="bp-muted" role="status">Loading your plan…</p>'
        '<noscript><p>The break planner needs JavaScript.</p></noscript></section>'
        + GUIDE + _faq_html())
    return _shell("Plan your break", "/break", content, member=True, indexable=True, structured_data=_structured())


def _share_board(view: dict) -> str:
    columns = []
    for day in view["days"]:
        items = []
        for entry in day["items"]:
            art = (f'<img src="{_e(entry["image"])}" alt="" width="48" height="72" loading="lazy" '
                   'referrerpolicy="no-referrer">' if entry["image"] else
                   f'<span class="bp-art__empty" aria-hidden="true">{_e(entry["title"][:1].upper())}</span>')
            done = ' bp-chip--done' if entry["done"] else ''
            tick = '<span class="bp-chip__tick" aria-label="Done">✓</span>' if entry["done"] else ''
            items.append(f'<li class="bp-chip bp-chip--art{done}" data-category="{_e(entry["category"])}">'
                         f'<span class="bp-art">{art}</span><span class="bp-chip__body">'
                         f'<span class="bp-chip__kind">{_e(entry["kind_label"])}</span>'
                         f'<strong>{_e(entry["title"])}</strong>'
                         f'<span class="bp-chip__what">{_e(break_plan.what_line(entry))}</span></span>'
                         f'{tick}</li>')
        body = "".join(items) or '<li class="bp-chip bp-chip--rest">A rest day</li>'
        columns.append(f'<li class="bp-col"><p class="bp-col__day">{_e(day["label"])}</p>'
                       f'<ul class="bp-col__items">{body}</ul></li>')
    return f'<ol class="bp-board bp-board--shared">{"".join(columns)}</ol>'


@router.get("/break/s/{token}", include_in_schema=False)
def shared_page(token: str, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    plan = break_plan.by_token(db, token)
    if plan is None:
        return _message("Link not working", "This plan isn't shared anymore",
                        "Whoever sent it may have turned the link off. You can plan your own break in a minute.",
                        (("Plan my break", "/break"), ("See what OmniTrackr does", "/about")))
    today = date.today()
    view = break_plan.shared_view(db, plan, today)
    if user is None or user.id != plan.user_id:
        plan.share_opened = (plan.share_opened or 0) + 1
        try:
            db.commit()
        except Exception:
            db.rollback()
    totals = view["totals"]
    owner = view["owner"]
    if view["phase"] == "after":
        line = (f'{_e(owner)} got through {totals["done"]} of {totals["stretches"]} things on the plan and finished '
                f'{totals["finished"]} {"title" if totals["finished"] == 1 else "titles"}.')
    elif view["phase"] == "during":
        line = f'{totals["titles"]} titles, about {_e(totals["hours"])}. {totals["done"]} ticked off so far.'
    else:
        line = f'{totals["titles"]} titles over {view["day_count"]} days, about {_e(totals["hours"])}.'
    private = (f'<p class="bp-muted">Plus {view["private_titles"]} from shelves {_e(owner)} keeps private.</p>'
               if view["private_titles"] else '')
    if user is None:
        funnel.record("break_link_opened", request)
        back = quote("/break", safe="")
        invite = db.query(models.FriendInvite).filter(models.FriendInvite.user_id == plan.user_id).first()
        join = f"/?invite={quote(invite.token)}&next={back}#signup" if invite is not None else f"/?next={back}#signup"
        actions = (f'<a class="button" rel="nofollow" href="{_e(join)}" data-break-signup>Plan my own break</a>'
                   '<a class="button button--ghost" href="/break">How it works</a>'
                   '<p class="bp-muted bp-shared__small">OmniTrackr is a free tracker for films, shows, anime, games, '
                   'books and more. The break planner fills your days off from your own list.</p>')
    elif user.id == plan.user_id:
        actions = '<a class="button" href="/break">Back to my plan</a>'
    else:
        actions = '<a class="button" href="/break">Plan my own break</a>'
    content = (
        '<section class="bp-shared">'
        f'<p class="eyebrow">{_e(owner).upper()}\'S BREAK PLAN</p>'
        f'<h1>{_e(view["name"])}</h1>'
        f'<p class="bp-shared__span">{_e(view["span"])}</p>'
        f'<p class="bp-shared__line">{line}</p>{private}'
        f'{_share_board(view)}'
        f'<div class="bp-shared__actions">{actions}</div></section>')
    facts = break_plan.card_facts(db, plan, today)
    version = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:10]
    from ..digest import app_url
    path = break_plan.share_path(plan)
    response = _shell(f"{owner}'s plan for {view['name']}", path, content, member=user is not None,
                      description=f"{owner} planned {view['name'].lower()} on OmniTrackr: {totals['titles']} titles, "
                                  f"about {totals['hours']}. Plan your own break from your list.",
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


@router.get("/break/s/{token}/card.png", include_in_schema=False)
def shared_card(token: str, request: Request, db: Session = Depends(get_db)):
    plan = break_plan.by_token(db, token)
    if plan is None:
        raise HTTPException(404, "This plan isn't shared anymore")
    facts = break_plan.card_facts(db, plan, date.today())
    fingerprint = hashlib.sha256(json.dumps(facts, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    etag = f'"{fingerprint}"'
    headers = {"Cache-Control": "private, max-age=300", "ETag": etag, "X-Content-Type-Options": "nosniff",
               "X-Robots-Tag": "noindex"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    cache = _card_cache()
    png = cache.get(("break", plan.id, fingerprint))
    if png is None:
        from .. import break_card
        try:
            png = break_card.render(facts)
        except Exception:
            raise HTTPException(404, "Card unavailable")
        cache.put(("break", plan.id, fingerprint), png)
    return Response(content=png, media_type="image/png", headers=headers)


# ------------------------------------------------------------------ API: no plan id

def _presets_json(today: date) -> list[dict]:
    return [{"key": entry["key"], "name": entry["name"], "slug": entry["slug"],
             "starts_on": entry["starts_on"].isoformat(), "ends_on": entry["ends_on"].isoformat(),
             "span": break_plan.span_label(entry["starts_on"], entry["ends_on"]),
             "light": [day.isoformat() for day in entry["light"]]}
            for entry in break_plan.presets(today)]


def _state(db: Session, user: models.User, today: date) -> dict:
    plan = break_plan.active(db, user.id, today)
    return {
        "plan": break_plan.view(db, user, plan, today) if plan is not None else None,
        "presets": _presets_json(today), "today": today.isoformat(),
        "choices": list(break_plan.DAY_CHOICES), "default_minutes": break_plan.DEFAULT_MINUTES,
        "light_minutes": break_plan.LIGHT_MINUTES, "max_days": break_plan.MAX_DAYS,
        "start_within_days": break_plan.START_WITHIN_DAYS,
        "email_offer": bool(user.email and user.is_verified),
    }


@router.get("/api/break")
def my_break(request: Request, response: Response, today: Optional[str] = TODAY, user=Depends(get_current_user),
             db: Session = Depends(get_db)):
    _private(response)
    return _state(db, user, _today(today))


@router.get("/api/break/home")
def break_home(request: Request, response: Response, today: Optional[str] = TODAY, user=Depends(get_current_user),
               db: Session = Depends(get_db)):
    _private(response)
    try:
        return {"card": break_plan.home(db, user, _today(today))}
    except Exception:
        db.rollback()
        return {"card": None}  # an optional card; the home screen never waits on it


@router.post("/api/break/seen")
def break_seen(request: Request, payload: Today, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    try:
        return break_plan.note_seen(db, user, _today(payload.today))
    except IntegrityError:
        db.rollback()
        return {"counted": False}


@router.post("/api/break/demo")
def break_demo(payload: Demo, request: Request, response: Response):
    """The guide page's sample plan. No account, no library: twelve made-up titles."""
    _private(response)
    if payload.ends_on < payload.starts_on or (payload.ends_on - payload.starts_on).days + 1 > break_plan.MAX_DAYS:
        raise HTTPException(422, f"Pick one to {break_plan.MAX_DAYS} days.")
    _check_minutes(payload.minutes)
    days = break_plan.days_of(payload.starts_on, payload.ends_on)
    minutes = {day.isoformat(): payload.minutes.get(day.isoformat(), break_plan.DEFAULT_MINUTES) for day in days}
    funnel.record("break_demo_used", request)
    return {"days": break_plan.demo(payload.starts_on, minutes)}


@router.post("/api/break", status_code=201)
def create_plan(request: Request, payload: PlanCreate, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    _check_minutes(payload.minutes)
    today = _today(payload.today)
    try:
        break_plan.create(db, user, starts_on=payload.starts_on, ends_on=payload.ends_on, minutes=payload.minutes,
                          today=today, tz_minutes=payload.tz, name=payload.name, preset_key=payload.preset,
                          games=payload.games, emails=payload.emails)
    except break_plan.BreakError as error:
        db.rollback()
        _fail(error)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That didn't save. Please try again.")
    return _state(db, user, today)


# ------------------------------------------------------------------ API: one plan

def _plan(db: Session, user, plan_id: int) -> models.BreakPlan:
    try:
        return break_plan.owned(db, user.id, plan_id)
    except break_plan.BreakError as error:
        _fail(error)


def _run(db: Session, user, today: date, action) -> dict:
    try:
        extra = action()
    except break_plan.BreakError as error:
        db.rollback()
        _fail(error)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That didn't save. Please try again.")
    state = _state(db, user, today)
    if isinstance(extra, dict):
        state.update(extra)
    return state


@router.patch("/api/break/{plan_id}")
def update_plan(request: Request, plan_id: PositiveDatabaseId, payload: PlanUpdate, response: Response, user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    _private(response)
    _check_minutes(payload.minutes)
    today = _today(payload.today)
    plan = _plan(db, user, plan_id)
    return _run(db, user, today, lambda: break_plan.update(
        db, user, plan, today, minutes=payload.minutes, ends_on=payload.ends_on, name=payload.name,
        games=payload.games, emails=payload.emails))


@router.delete("/api/break/{plan_id}")
def delete_plan(request: Request, plan_id: PositiveDatabaseId, response: Response, today: Optional[str] = TODAY,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    plan = _plan(db, user, plan_id)
    break_plan.cancel(db, plan)
    return _state(db, user, _today(today))


@router.post("/api/break/{plan_id}/fill")
def fill_plan(request: Request, plan_id: PositiveDatabaseId, payload: Fill, response: Response, user=Depends(get_current_user),
              db: Session = Depends(get_db)):
    _private(response)
    today = _today(payload.today)
    plan = _plan(db, user, plan_id)
    return _run(db, user, today, lambda: {"added": break_plan.refill(db, user, plan, today, payload.day)})


@router.post("/api/break/{plan_id}/shuffle")
def shuffle_plan(request: Request, plan_id: PositiveDatabaseId, payload: Today, response: Response, user=Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _private(response)
    today = _today(payload.today)
    plan = _plan(db, user, plan_id)
    return _run(db, user, today, lambda: {"added": break_plan.reshuffle(db, user, plan, today)})


@router.get("/api/break/{plan_id}/titles")
def plan_titles(request: Request, plan_id: PositiveDatabaseId, response: Response, user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    _private(response)
    plan = _plan(db, user, plan_id)
    return {"titles": break_plan.addable(db, user, plan)}


@router.post("/api/break/{plan_id}/items")
def add_item(request: Request, plan_id: PositiveDatabaseId, payload: AddItem, response: Response, user=Depends(get_current_user),
             db: Session = Depends(get_db)):
    _private(response)
    today = _today(payload.today)
    plan = _plan(db, user, plan_id)
    return _run(db, user, today, lambda: break_plan.add(db, user, plan, payload.category, payload.item_id,
                                                        payload.day, today))


@router.patch("/api/break/{plan_id}/items/{item_id}")
def move_item(request: Request, plan_id: PositiveDatabaseId, item_id: PositiveDatabaseId, payload: MoveItem, response: Response,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    today = _today(payload.today)
    plan = _plan(db, user, plan_id)
    return _run(db, user, today, lambda: break_plan.move(db, plan, item_id, payload.day))


@router.delete("/api/break/{plan_id}/items/{item_id}")
def remove_item(request: Request, plan_id: PositiveDatabaseId, item_id: PositiveDatabaseId, response: Response, swap: bool = False,
                today: Optional[str] = TODAY, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    local = _today(today)
    plan = _plan(db, user, plan_id)
    return _run(db, user, local, lambda: {"added": break_plan.remove(db, user, plan, item_id, local, swap=swap)})


@router.post("/api/break/{plan_id}/items/{item_id}/done")
def tick_item(request: Request, plan_id: PositiveDatabaseId, item_id: PositiveDatabaseId, payload: Today, response: Response,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    today = _today(payload.today)
    plan = _plan(db, user, plan_id)
    return _run(db, user, today, lambda: {"ticked": break_plan.tick(db, user, plan, item_id)})


@router.post("/api/break/{plan_id}/items/{item_id}/undo")
def untick_item(request: Request, plan_id: PositiveDatabaseId, item_id: PositiveDatabaseId, payload: Today, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    today = _today(payload.today)
    plan = _plan(db, user, plan_id)
    return _run(db, user, today, lambda: break_plan.untick(db, plan, item_id))


@router.post("/api/break/{plan_id}/items/{item_id}/finish")
def finish_item(request: Request, plan_id: PositiveDatabaseId, item_id: PositiveDatabaseId, payload: Score, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    today = _today(payload.today)
    plan = _plan(db, user, plan_id)
    return _run(db, user, today, lambda: {"title": break_plan.finish(db, user, plan, item_id, payload.rating)})


@router.post("/api/break/{plan_id}/items/{item_id}/rate")
def rate_item(request: Request, plan_id: PositiveDatabaseId, item_id: PositiveDatabaseId, payload: Rating, response: Response,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    today = _today(payload.today)
    plan = _plan(db, user, plan_id)
    return _run(db, user, today, lambda: {"title": break_plan.rate(db, user, plan, item_id, payload.rating)})


@router.post("/api/break/{plan_id}/share")
def share_plan(request: Request, plan_id: PositiveDatabaseId, payload: Today, response: Response, user=Depends(get_current_user),
               db: Session = Depends(get_db)):
    _private(response)
    today = _today(payload.today)
    plan = _plan(db, user, plan_id)
    return _run(db, user, today, lambda: {"path": break_plan.share_on(db, plan)})


@router.delete("/api/break/{plan_id}/share")
def unshare_plan(request: Request, plan_id: PositiveDatabaseId, response: Response, today: Optional[str] = TODAY,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    plan = _plan(db, user, plan_id)
    break_plan.share_off(db, plan)
    return _state(db, user, _today(today))


@router.post("/api/break/{plan_id}/hide-wrap")
def hide_wrap(request: Request, plan_id: PositiveDatabaseId, payload: Today, response: Response, user=Depends(get_current_user),
              db: Session = Depends(get_db)):
    _private(response)
    plan = _plan(db, user, plan_id)
    break_plan.hide_wrap(db, plan)
    return {"card": None}


@router.get("/api/break/{plan_id}/calendar.ics")
def plan_calendar(request: Request, plan_id: PositiveDatabaseId, user=Depends(get_current_user), db: Session = Depends(get_db)):
    plan = _plan(db, user, plan_id)
    body = break_plan.calendar_ics(db, user, plan)
    response = Response(content=body, media_type="text/calendar; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="omnitrackr-break-plan.ics"'
    _private(response)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
