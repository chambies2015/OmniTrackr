"""Fill in your year (see app/year_fill.py): the member page, its JSON calls, and the no-sign-in page from the email."""
from __future__ import annotations

from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, visits, year_fill
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..site_chrome import message_page
from .discover import page

router = APIRouter(tags=["year-fill"])
CSS_VERSION = "20261126-fill-1"
JS_VERSION = "20261126-fill-1"


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _private(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Referrer-Policy"] = "same-origin"  # on the emailed page, the address is the key
    return response


def _person(request: Request) -> bool:
    from .check_in import _person as person
    return person(request)


def _here(query: str) -> str:
    """A query-only address: the browser keeps the page's own path, so a redirect never carries the link."""
    if not query.startswith("?"):
        raise ValueError("query-only addresses start with ?")
    return query


def _plural(count: int, one: str, many: Optional[str] = None) -> str:
    return f"{count:,} {one if count == 1 else (many or one + 's')}"


# ---------------------------------------------------------------- shared pieces

def _cover(card: dict) -> str:
    if card.get("image"):
        return (f'<img src="{_e(card["image"])}" alt="" width="120" height="180" loading="lazy" '
                'referrerpolicy="no-referrer">')
    return f'<span class="yf-cover__initial" aria-hidden="true">{_e(card["title"][:1].upper())}</span>'


def _meta(card: dict) -> str:
    return card["label"] + (f" · {card['year']}" if card.get("year") else "")


def _choices(card: dict, months: list[dict], year: int, *, form: bool) -> str:
    """The month buttons and the two other answers. ``form``: plain submit buttons for the emailed page."""
    ref = f'{card["category"]}-{card["id"]}'
    kind = "submit" if form else "button"

    def attrs(choice: str) -> str:
        return f'name="choice" value="{_e(choice)}"' if form else f'data-answer="{_e(choice.split("-")[0])}"'

    buttons = []
    for month in months:
        label = month["short"]
        aria = f'{month["name"]} {year}' + (" (this month)" if month["current"] else "")
        extra = f' data-month="{month["n"]}"' if not form else ""
        buttons.append(f'<button type="{kind}" class="yf-month{" yf-month--now" if month["current"] else ""}" '
                       f'{attrs("month-" + str(month["n"]))}{extra} aria-label="{_e(aria)}">{_e(label)}</button>')
    if card["kind"] == "undated":
        others = (f'<button type="{kind}" class="yf-other" {attrs("before")}>Before {year}</button>'
                  f'<button type="{kind}" class="yf-other" {attrs("skip")}>Not sure</button>')
    else:
        others = (f'<button type="{kind}" class="yf-other" {attrs("before")}>Finished before {year}</button>'
                  f'<button type="{kind}" class="yf-other" {attrs("skip")}>Not yet</button>')
    return (f'<div class="yf-months" role="group" aria-labelledby="yf-q-{_e(ref)}">{"".join(buttons)}</div>'
            f'<div class="yf-others">{others}</div>')


def _card_html(card: dict, months: list[dict], year: int, *, form_action: str = "", index: Optional[int] = None,
               anchor: str = "") -> str:
    ref = f'{card["category"]}-{card["id"]}'
    head = (f'<div class="yf-cover">{_cover(card)}</div><div class="yf-body">'
            f'<p class="yf-label">{_e(_meta(card))}</p><h3 class="yf-title">{_e(card["title"])}</h3>'
            f'<p class="yf-q" id="yf-q-{_e(ref)}">{_e(card["question"])}</p>')
    choices = _choices(card, months, year, form=bool(form_action))
    if form_action:
        choices = (f'<form method="post" action="{_e(form_action)}#{_e(anchor)}">'
                   f'<input type="hidden" name="item" value="{index}">{choices}</form>')
    item_id = f' id="{_e(anchor)}"' if anchor else ""
    return (f'<li class="yf-card"{item_id} data-category="{_e(card["category"])}" data-id="{card["id"]}" '
            f'data-kind="{_e(card["kind"])}">{head}{choices}</div></li>')


def _answered_html(card: dict, year: int, form_action: str, index: int, anchor: str) -> str:
    answer, month = card.get("answer"), card.get("month")
    if answer == "month" and month:
        said = f"Finished in {year_fill.MONTHS[month - 1]}. It's in your recap."
    elif answer == "before":
        said = (f"Finished before {year}. Ticked off, without a {year} date." if card["kind"] == "open"
                else f"Finished before {year}, so it stays out of this recap.")
    elif answer == "dated":
        said = "Already has a finish date."
    else:
        said = "Not yet. It stays on your list." if card["kind"] == "open" else "Skipped. You can date it later."
    change = ("" if answer == "dated" else
              f'<form method="post" action="{_e(form_action)}#{_e(anchor)}" class="yf-change">'
              f'<input type="hidden" name="item" value="{index}">'
              '<button type="submit" name="choice" value="undo" class="yf-link">Change</button></form>')
    return (f'<li class="yf-card is-answered" id="{_e(anchor)}">'
            f'<div class="yf-cover">{_cover(card)}</div><div class="yf-body">'
            f'<p class="yf-label">{_e(_meta(card))}</p><h3 class="yf-title">{_e(card["title"])}</h3>'
            f'<p class="yf-said"><span aria-hidden="true">✓</span> {_e(said)}</p>{change}</div></li>')


def _lead(year: int, since: Optional[str]) -> str:
    if since:
        return (f"OmniTrackr started dating what you finish in {since} {year}, so your recap leaves out anything "
                f"you ticked off before then. Give each title the month you finished it and it joins your {year}. "
                "A guess is fine.")
    return (f"These titles are ticked off in your library with no date, so your {year} recap leaves them out. "
            "Give each one the month you finished it. A guess is fine.")


def _next_steps(db: Session, user: models.User, year: int) -> str:
    """Where to go once everything is dated: the recap first, then the yearbook and the pledge while they're open."""
    links = [(f"Play your {year}", f"/year-in-review/{year}#story", True)]
    try:
        from .. import yearbook
        if year in yearbook.EDITIONS and yearbook.state_of(year) == "open":
            links.append(("Make your yearbook" if yearbook.get(db, user.id, year) is None else "Open your yearbook",
                          "/yearbook", False))
    except Exception:
        db.rollback()
    try:
        from .. import new_year_challenge
        if new_year_challenge.is_open(year + 1):
            links.append((f"Pledge for {year + 1}", new_year_challenge.path(year + 1) + "#pledge", False))
    except Exception:
        db.rollback()
    return "".join(f'<a class="site-btn {"site-btn--primary" if primary else "site-btn--ghost"}" href="{_e(href)}">'
                   f'{_e(label)}</a>' for label, href, primary in links)


# ---------------------------------------------------------------- the member page

def _member_content(db: Session, user: models.User, data: dict) -> str:
    year = data["year"]
    months = data["months"]
    deck = "".join(_card_html(card, months, year) for card in data["undated"])
    still = "".join(_card_html(card, months, year) for card in data["open"])
    left = data["undated_total"] + data["open_total"]
    undated_note = ""
    if data["undated_total"] > len(data["undated"]):
        undated_note = (f'<p class="yf-note">Showing the newest {len(data["undated"])} of '
                        f'{data["undated_total"]:,}. The rest load as you go.</p>')
    deck_section = (
        '<section class="yf-section yf-section--deck" aria-labelledby="yfDeckTitle" data-yf-deck'
        f'{"" if data["undated"] else " hidden"}>'
        f'<div class="yf-section__head"><h2 id="yfDeckTitle">Ticked off, no date</h2>'
        f'<p class="yf-count" data-yf-undated-left>{_plural(data["undated_total"], "title")} to go</p></div>'
        f'<ol class="yf-cards" data-yf-list="undated">{deck}</ol>{undated_note}'
        f'<div class="yf-bulk" data-yf-bulk="undated"><button type="button" class="yf-link" data-yf-rest="undated">'
        f'The rest were all before {year}</button></div></section>')
    open_section = (
        '<section class="yf-section yf-section--open" aria-labelledby="yfOpenTitle" data-yf-open'
        f'{"" if data["open"] else " hidden"}>'
        f'<div class="yf-section__head"><h2 id="yfOpenTitle">Still on your list</h2>'
        f'<p class="yf-count" data-yf-open-left>{_plural(data["open_total"], "title")}</p></div>'
        f'<p class="yf-note">Saved before this month and never ticked off. If you finished any of them in {year}, '
        'pick the month and it gets ticked off too.</p>'
        f'<ol class="yf-cards yf-cards--list" data-yf-list="open">{still}</ol>'
        '<div class="yf-bulk" data-yf-bulk="open"><button type="button" class="yf-link" data-yf-rest="open">'
        'None of these yet</button></div></section>')
    bring_back = (f'<button type="button" class="yf-link" data-yf-bring-back>Ask again about the '
                  f'{_plural(data["skipped"], "title")} I skipped</button>' if data["skipped"] else "")
    done = (
        f'<section class="yf-done" aria-labelledby="yfDoneTitle" data-yf-done{"" if not left else " hidden"}>'
        f'<h2 id="yfDoneTitle">Your {year} is filled in</h2>'
        f'<p>Your recap counts <strong data-yf-finished-done>{_plural(data["finished_total"], "finish", "finishes")}</strong> '
        'now. Play it through and save the story image to post.</p>'
        f'<p class="yf-done__actions">{_next_steps(db, user, year)}</p>'
        f'<p class="yf-done__again" data-yf-bring-back-wrap>{bring_back}</p></section>')
    return (
        f'<section class="yf" aria-labelledby="yfTitle" data-yf data-year="{year}">'
        '<header class="yf-head">'
        f'<p class="eyebrow">YEAR IN REVIEW · {year}</p>'
        f'<h1 id="yfTitle">Fill in your {year}</h1>'
        f'<p class="yf-lead">{_e(_lead(year, data["dated_from"]))}</p>'
        '<div class="yf-tally" role="status" aria-live="polite">'
        f'<p><strong data-yf-finished>{data["finished_total"]:,}</strong> '
        f'<span data-yf-finished-label>{"finish" if data["finished_total"] == 1 else "finishes"} in your {year} recap</span></p>'
        f'<p><strong data-yf-filled>{data["filled"]:,}</strong> <span>dated here</span></p>'
        f'<a class="yf-tally__link" href="/year-in-review/{year}">See the recap</a>'
        '</div>'
        '<noscript><p class="yf-note">This page needs JavaScript to save answers.</p></noscript>'
        '</header>'
        + deck_section + open_section + done +
        '<p class="yf-undo" data-yf-undo hidden role="status" aria-live="polite"><span data-yf-undo-text></span>'
        '<button type="button" class="yf-link" data-yf-undo-button>Undo</button></p>'
        '<p class="yf-error" data-yf-error hidden role="alert"></p>'
        '<p class="yf-small">A dated title counts in your recap, your yearly goals and the New Year pledge numbers. '
        'Monthly challenges and streaks only count finishes as you log them, so dating an old one doesn’t change them. '
        'Picking this month (the one outlined in green) is the same as ticking it off today.</p>'
        '</section>'
    )


@router.get("/year-in-review/{year}/fill", include_in_schema=False)
def fill_page(year: int, request: Request, db: Session = Depends(get_db),
              viewer: Optional[models.User] = Depends(get_optional_current_user)):
    if viewer is None:
        return RedirectResponse("/#login", status_code=302)
    if not year_fill.is_fill_year(year):
        # Last year's page in February, or a typo: the recap is the useful place (a fixed address, so nothing
        # from the request goes into the Location header).
        return RedirectResponse("/year-in-review", status_code=302)
    if _person(request):
        year_fill.count("opened_page")
    data = year_fill.state(db, viewer.id, year)
    head = (f'<link rel="stylesheet" href="/static/year-fill.css?v={CSS_VERSION}">'
            f'<script src="/static/year-fill.js?v={JS_VERSION}" defer></script>')
    response = page(f"Fill in your {year}", f"Date the titles your {year} Year in Review is missing.",
                    f"/year-in-review/{year}/fill", _member_content(db, viewer, data),
                    indexable=False, head=head, member=True)
    return _private(response)


class FillAnswer(BaseModel):
    category: str = Field(..., max_length=20)
    id: int = Field(..., ge=1, le=2147483647)
    answer: str = Field(..., pattern="^(month|before|skip)$")
    month: Optional[int] = Field(None, ge=1, le=12)


class FillRef(BaseModel):
    category: str = Field(..., max_length=20)
    id: int = Field(..., ge=1, le=2147483647)


class FillRest(BaseModel):
    kind: str = Field(..., pattern="^(undated|open)$")


def _year_or_404(year: int) -> int:
    if not year_fill.is_fill_year(year):
        raise HTTPException(404, "That year can't be filled in")
    return year


def _counts(db: Session, user: models.User, year: int) -> dict:
    found = year_fill.summary(db, user.id, year)
    return {"finished_total": year_fill.finished_total(db, user.id, year), "filled": found["filled"],
            "undated_left": found["undated"], "open_left": found["open"]}


@router.get("/api/year-in-review/{year}/fill")
def fill_state(year: int, request: Request, response: Response, user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    return year_fill.state(db, user.id, _year_or_404(year))


@router.post("/api/year-in-review/{year}/fill")
def fill_answer(year: int, payload: FillAnswer, request: Request, response: Response, user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    _year_or_404(year)
    if payload.category not in year_fill.categories():
        raise HTTPException(422, "Unknown shelf")
    try:
        result = year_fill.answer(db, user, year, payload.category, payload.id, payload.answer, payload.month, "page")
    except ValueError as error:
        raise HTTPException(422, str(error))
    if result is None:
        raise HTTPException(404, "That title isn't in your library anymore")
    year_fill.count_answer(result, "page")
    counts = _counts(db, user, year)
    if result["state"] in year_fill.ANSWERS and not counts["undated_left"] and not counts["open_left"]:
        year_fill.count("all_done_page")
    try:
        visits.record_visit(db, user)
    except Exception:
        db.rollback()
    return {**result, **counts}


@router.post("/api/year-in-review/{year}/fill/undo")
def fill_undo(year: int, payload: FillRef, request: Request, response: Response, user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    _year_or_404(year)
    undone = year_fill.undo(db, user, year, payload.category, payload.id)
    if undone:
        year_fill.count("undone_page")
    return {"undone": undone, **_counts(db, user, year)}


@router.post("/api/year-in-review/{year}/fill/rest")
def fill_rest(year: int, payload: FillRest, request: Request, response: Response, user: models.User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    _year_or_404(year)
    answered = year_fill.answer_rest(db, user, year, payload.kind, "page")
    if answered:
        year_fill.count("before_page" if payload.kind == "undated" else "skipped_page")
    return {"answered": answered, **_counts(db, user, year)}


@router.post("/api/year-in-review/{year}/fill/bring-back")
def fill_bring_back(year: int, request: Request, response: Response, user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    _year_or_404(year)
    return {"brought_back": year_fill.bring_back(db, user, year), **_counts(db, user, year)}


# ---------------------------------------------------------------- the emailed page (no sign-in)

def _expired():
    html = message_page(
        "Fill in your year", "This link has run out",
        "The links in the Year in Review email work for 30 days. Sign in to fill in your year from your recap page, "
        "where every title is waiting.", eyebrow="Year in Review",
        actions=(("Log in", "/#login"), ("Today's daily puzzle", "/daily")))
    return _private(strict_html_response(html, status_code=404))


def _token_member(db: Session, token: str):
    data = year_fill.read_token(token)
    if data is None:
        return None, None
    user = db.get(models.User, data["user_id"])
    if user is None or not user.is_active:
        return None, None
    return user, data


def _token_content(db: Session, user: models.User, data: dict, token: str, signed_in: bool) -> str:
    year = data["year"]
    months = year_fill.months_for(year)
    items = year_fill.token_items(db, user.id, year, data["items"])
    action = f"/fill-in/{token}"
    rows = []
    answered = 0
    for index, card in enumerate(items):
        if card is None:
            continue
        anchor = f"yf-{index}"
        if card.get("answer"):
            answered += 1
            rows.append(_answered_html(card, year, action, index, anchor))
        else:
            rows.append(_card_html(card, months, year, form_action=action, index=index, anchor=anchor))
    total = len(rows)
    finished = year_fill.finished_total(db, user.id, year)
    left = year_fill.summary(db, user.id, year)
    elsewhere = max(0, left["undated"] + left["open"] - (total - answered))
    all_done = answered == total
    if all_done:
        lead = (f"That’s everything from the email. Your {year} recap counts {_plural(finished, 'finish', 'finishes')} now."
                + (f" {_plural(elsewhere, 'more title')} {'is' if elsewhere == 1 else 'are'} waiting on the full page "
                   "once you sign in." if elsewhere else ""))
    else:
        lead = (f"Pick the month you finished each one and it counts in your {year} recap. A guess is fine. "
                "It saves straight to your library, and you don’t need to sign in.")
    if signed_in:
        primary = (f'<a class="site-btn site-btn--primary" href="/year-in-review/{year}/fill">See every title</a>'
                   if elsewhere else
                   f'<a class="site-btn site-btn--primary" href="/year-in-review/{year}#story">Play your {year}</a>')
        secondary = f'<a class="site-btn site-btn--ghost" href="/year-in-review/{year}">Open the recap</a>'
    else:
        primary = '<a class="site-btn site-btn--primary" href="/#login">Log in to play your year</a>'
        secondary = '<a class="site-btn site-btn--ghost" href="/daily">Play today’s daily puzzle</a>'
    return (
        f'<section class="yf yf--emailed" aria-labelledby="yfTitle">'
        '<header class="yf-head">'
        f'<p class="eyebrow">YEAR IN REVIEW · {year}</p>'
        f'<h1 id="yfTitle">{"All filled in, " + _e(user.username) if all_done else "Fill in your " + str(year) + ", " + _e(user.username)}</h1>'
        f'<p class="yf-lead">{_e(lead)}</p>'
        f'<p class="yf-progress" role="status"><progress value="{answered}" max="{total}"></progress>'
        f'<span>{answered} of {total} answered</span></p>'
        '</header>'
        f'<ol class="yf-cards yf-cards--list">{"".join(rows)}</ol>'
        f'<div class="yf-foot">{primary}{secondary}</div>'
        '<p class="yf-small">This page only shows the titles from your email, and the link stops working 30 days '
        'after it was sent. A dated title counts in your recap and yearly goals, not in monthly challenges.</p>'
        '</section>'
    )


@router.get("/fill-in/{token}", include_in_schema=False)
def token_page(token: str, request: Request, r: str = "", db: Session = Depends(get_db),
               viewer: Optional[models.User] = Depends(get_optional_current_user)):
    user, data = _token_member(db, token)
    if user is None or not year_fill.is_fill_year(data["year"]):
        return _expired()
    if not any(year_fill.token_items(db, user.id, data["year"], data["items"])):
        return _expired()
    if not r and _person(request):  # our own redirects after a button press carry r=1
        year_fill.count("opened_email")
    signed_in = viewer is not None and viewer.id == user.id
    head = (f'<link rel="stylesheet" href="/static/year-fill.css?v={CSS_VERSION}">'
            '<meta name="referrer" content="same-origin">')
    response = page(f"Fill in your {data['year']}", "Date the titles your Year in Review is missing.", "/fill-in",
                    _token_content(db, user, data, token, signed_in), indexable=False, head=head, member=True)
    return _private(response)


@router.post("/fill-in/{token}", include_in_schema=False)
async def token_answer(token: str, request: Request, db: Session = Depends(get_db)):
    user, data = _token_member(db, token)
    if user is None or not year_fill.is_fill_year(data["year"]):
        return _expired()
    try:
        form = await request.form()
    except Exception:
        form = {}
    raw_item = str(form.get("item", ""))[:2]
    choice = str(form.get("choice", ""))[:12]
    size = len(data["items"])
    if not raw_item.isdigit() or int(raw_item) >= size:
        return _private(RedirectResponse(_here("?r=1"), status_code=303))
    index = int(raw_item)
    category, item_id = data["items"][index]
    year = data["year"]
    target = _here(f"?r=1#yf-{index}")
    if choice == "undo":
        if year_fill.undo(db, user, year, category, item_id):
            year_fill.count("undone_email")
        return _private(RedirectResponse(target, status_code=303))
    answer, month = choice, None
    if choice.startswith("month-"):
        raw = choice[len("month-"):]
        if not raw.isdigit():
            return _private(RedirectResponse(target, status_code=303))
        answer, month = "month", int(raw)
    if answer not in year_fill.ANSWERS:
        return _private(RedirectResponse(target, status_code=303))
    try:
        result = year_fill.answer(db, user, year, category, item_id, answer, month, "email")
    except ValueError:
        return _private(RedirectResponse(target, status_code=303))
    year_fill.count_answer(result, "email")
    if result and result["state"] in year_fill.ANSWERS:
        items = [card for card in year_fill.token_items(db, user.id, year, data["items"]) if card is not None]
        if items and all(card.get("answer") for card in items):
            year_fill.count("all_done_email")
    try:
        visits.record_visit(db, user)  # answering is opening OmniTrackr, signed in or not
    except Exception:
        db.rollback()
    return _private(RedirectResponse(target, status_code=303))
