"""The check-in page an email links to (see app/check_in.py). Works without signing in."""
from __future__ import annotations

from html import escape
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import check_in, models, visits
from ..dependencies import get_db, get_optional_current_user
from ..site_chrome import message_page
from ..csp import strict_html_response
from .discover import page

router = APIRouter(tags=["check-in"])
CSS_VERSION = "20261117-check-in-1"
MAX_LIST = 12  # the "answered" lists carried in the address are a few indexes, never more


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _private(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Referrer-Policy"] = "same-origin"  # the address is the key to this page
    return response


def _indexes(value: Optional[str], size: int) -> list[int]:
    found = []
    for part in (value or "").split(",")[:MAX_LIST]:
        if part.isdigit() and int(part) < size and int(part) not in found:
            found.append(int(part))
    return sorted(found)


def _here(query: str) -> str:
    """A query-only address: the browser keeps the page's own path, so a redirect never carries the link."""
    if not query.startswith("?"):
        raise ValueError("query-only addresses start with ?")
    return query


def _expired():
    html = message_page(
        "Check-in", "This check-in link has run out",
        "Check-in links work for three weeks. Your library is still where you left it: open it to tick titles off "
        "or give them a score.", eyebrow="Check-in", actions=(("Open my library", "/"), ("Today's daily puzzle", "/daily")))
    return _private(strict_html_response(html, status_code=404))


def _person(request: Request) -> bool:
    """Not a mail app's link checker or a prefetch: only people are counted."""
    from ..site_traffic import BOT_PATTERN
    agent = request.headers.get("user-agent", "")
    purpose = (request.headers.get("sec-purpose", "") + request.headers.get("purpose", "")).lower()
    return bool(agent) and not BOT_PATTERN.search(agent) and "prefetch" not in purpose and "prerender" not in purpose


def _member(db: Session, token: str):
    data = check_in.read_token(token)
    if data is None:
        return None, None
    user = db.get(models.User, data["user_id"])
    if user is None or not user.is_active:
        return None, None
    return user, data


def _score_buttons(index: int, prefix: str, current=None) -> str:
    buttons = "".join(
        f'<button type="submit" name="choice" value="{prefix}-{score}" class="ci-score{" is-current" if current == score else ""}" '
        f'aria-label="{score} out of 10">{score}</button>' for score in range(1, 11))
    return f'<div class="ci-scores" role="group" aria-labelledby="ci-q-{index}">{buttons}</div>'


def _item(index: int, item: dict, token: str, settled: list[int], pick: Optional[int], picked: str,
          just_saved: Optional[int], week: bool = False) -> tuple[str, bool]:
    """(html, answered) for one title. ``week``: the link came from the Your week Sunday nudge, where
    "still going" means progress made this week, so it is worded that way and counts the day."""
    still = "Made some progress" if week else "Still going"
    hidden = f'<input type="hidden" name="item" value="{index}"><input type="hidden" name="ok" value="{_e(",".join(map(str, settled)))}">'
    cover = (f'<img src="{_e(item["image"])}" alt="" width="96" height="144" loading="lazy" referrerpolicy="no-referrer">'
             if item.get("image") else f'<span class="ci-cover__initial" aria-hidden="true">{_e(item["title"][:1].upper())}</span>')
    head = (f'<div class="ci-cover">{cover}</div><div class="ci-body">'
            f'<p class="ci-label">{_e(item["label"])}</p><h2 class="ci-title">{_e(item["title"])}</h2>')
    focus = " is-focus" if pick == index or just_saved == index else ""
    if item["finished"] and item["rating"] is not None:
        score = item["rating"]
        shown = int(score) if float(score).is_integer() else score
        note = "Saved. " if just_saved == index else ""
        body = (f'<p class="ci-done"><span aria-hidden="true">✓</span> {note}Finished, your score {_e(shown)}/10</p>'
                f'<details class="ci-change"><summary>Change the score</summary>'
                f'<form method="post" action="/check-in/{_e(token)}#ci-{index}">{hidden}'
                f'<p class="ci-q" id="ci-q-{index}">Your score out of 10</p>{_score_buttons(index, "rate", int(score) if float(score).is_integer() else None)}</form></details>')
        return f'<li class="ci-item is-answered{focus}" id="ci-{index}">{head}{body}</div></li>', True
    if index in settled:
        if item["finished"]:
            body = '<p class="ci-done"><span aria-hidden="true">✓</span> Finished. No score, and that’s fine.</p>'
        else:
            body = ('<p class="ci-done"><span aria-hidden="true">✓</span> Counted for this week. It stays on your list.</p>'
                    if week else '<p class="ci-done"><span aria-hidden="true">✓</span> Still going. It stays on your list.</p>')
        return f'<li class="ci-item is-answered{focus}" id="ci-{index}">{head}{body}</div></li>', True
    if item["finished"]:
        body = (f'<form method="post" action="/check-in/{_e(token)}#ci-{index}">{hidden}'
                f'<p class="ci-q" id="ci-q-{index}">You finished it. How was it, out of 10?</p>'
                f'{_score_buttons(index, "rate")}'
                '<div class="ci-actions"><button type="submit" name="choice" value="noscore" class="ci-btn ci-btn--ghost">No score</button></div></form>')
        return f'<li class="ci-item{focus}" id="ci-{index}">{head}{body}</div></li>', False
    if pick == index and picked == "finished":
        body = (f'<form method="post" action="/check-in/{_e(token)}#ci-{index}">{hidden}'
                f'<p class="ci-q" id="ci-q-{index}">Nice. Tap a score out of 10 to save it as finished.</p>'
                f'{_score_buttons(index, "finished")}'
                '<div class="ci-actions"><button type="submit" name="choice" value="finished" class="ci-btn ci-btn--ghost">'
                'Save as finished, no score</button>'
                f'<button type="submit" name="choice" value="still" class="ci-btn ci-btn--ghost">{"Not yet, but I made progress" if week else "Not yet, still going"}</button></div></form>')
        return f'<li class="ci-item{focus}" id="ci-{index}">{head}{body}</div></li>', False
    body = (f'<form method="post" action="/check-in/{_e(token)}?pick={index}#ci-{index}">{hidden}'
            f'<p class="ci-q" id="ci-q-{index}">{_e(item["question"])}</p>'
            '<div class="ci-actions">'
            f'<button type="submit" name="choice" value="open" class="ci-btn">{_e(item["finished_label"])}</button>'
            f'<button type="submit" name="choice" value="still" class="ci-btn ci-btn--ghost">{still}</button></div></form>')
    return f'<li class="ci-item{focus}" id="ci-{index}">{head}{body}</div></li>', False


def _picks_html(suggestions: list[dict]) -> str:
    if not suggestions:
        return ""
    cards = "".join(
        f'<li><a class="ci-pick" href="{_e(pick["url"])}">'
        + (f'<img src="{_e(pick["image"])}" alt="" width="72" height="108" loading="lazy" referrerpolicy="no-referrer">'
           if pick.get("image") else f'<span class="ci-cover__initial" aria-hidden="true">{_e(pick["title"][:1].upper())}</span>')
        + f'<span class="ci-pick__text"><strong>{_e(pick["title"])}</strong>'
          f'<span>{_e(" · ".join(part for part in (pick["label"], pick["reason"]) if part))}</span></span></a></li>'
        for pick in suggestions)
    return ('<section class="ci-picks" aria-labelledby="ciPicks"><h2 id="ciPicks">Picked for you</h2>'
            '<p>From what members with libraries like yours track. Every score you give sharpens these.</p>'
            f'<ul>{cards}</ul></section>')


def _content(user: models.User, items: list[dict], token: str, settled: list[int], pick: Optional[int],
             picked: str, just_saved: Optional[int], suggestions: list[dict], signed_in: bool,
             source: str = "checkin") -> str:
    week = source == "week"
    rendered = [_item(index, item, token, settled, pick, picked, just_saved, week) for index, item in enumerate(items)
                if item is not None]
    answered = sum(1 for _, done in rendered if done)
    total = len(rendered)
    all_done = answered == total
    if all_done:
        # Only point at "the picks below" when there are some: with no suggestions the page has none to show.
        lead = ("That’s everything. Your library is up to date, and your scores are already shaping the picks below."
                if suggestions and any(item and item["rating"] is not None for item in items)
                else "That’s everything. Your library is up to date.")
    elif week:
        lead = ("Finished one, or got a bit further? Tap it and it counts toward your week. "
                "It saves straight to your library, and you don’t need to sign in.")
    else:
        lead = "Tap an answer for each one. It saves straight to your library, and you don’t need to sign in."
    library_label = "Open my library" if signed_in else "Log in to my library"
    library_href = "/" if signed_in else "/?next=/#landing-auth"
    return (
        '<section class="ci" aria-labelledby="ciTitle">'
        '<header class="ci-head">'
        f'<p class="eyebrow">{"YOUR WEEK" if week else "CHECK-IN"}</p>'
        f'<h1 id="ciTitle">{"All caught up, " + _e(user.username) if all_done else "How’s it going, " + _e(user.username) + "?"}</h1>'
        f'<p class="ci-lead">{lead}</p>'
        f'<p class="ci-progress" role="status"><progress value="{answered}" max="{total}"></progress>'
        f'<span>{answered} of {total} answered</span></p>'
        '</header>'
        f'<ol class="ci-list">{"".join(html for html, _ in rendered)}</ol>'
        + _picks_html(suggestions) +
        '<div class="ci-foot">'
        f'<a class="button primary" href="{library_href}">{library_label}</a>'
        '<a class="ci-btn ci-btn--ghost ci-link" href="/daily">Play today’s daily puzzle</a>'
        '</div>'
        '<p class="ci-small">This page only shows the titles from your email, and the link stops working three weeks after it was sent.</p>'
        '</section>'
    )


@router.get("/check-in/{token}", include_in_schema=False)
def check_in_page(token: str, request: Request, pick: Optional[int] = None, a: str = "", ok: str = "",
                  saved: Optional[int] = None, r: str = "", db: Session = Depends(get_db),
                  viewer=Depends(get_optional_current_user)):
    user, data = _member(db, token)
    if user is None:
        return _expired()
    items = check_in.aligned_items(db, user.id, data["items"])
    if not any(items):
        return _expired()
    size = len(items)
    settled = _indexes(ok, size)
    pick = pick if pick is not None and 0 <= pick < size else None
    saved = saved if saved is not None and 0 <= saved < size else None
    picked = a if a in ("finished", "still") else ""
    if pick is not None and items[pick] is None:
        pick = None
    if (pick is not None and picked == "still" and not items[pick]["finished"] and pick not in settled
            and data["source"] != "week"):  # from the Sunday nudge, "made progress" is a press, never a link
        # "Still going" changes nothing in the library, so the email's button answers straight away.
        settled = sorted(settled + [pick])
    if not r and _person(request):  # our own redirects after a button press carry r=1
        check_in.count(f"opened_{data['source']}")
        if picked == "still" and pick is not None:
            check_in.count(f"still_{data['source']}")
    suggestions = check_in.picks(db, user.id)
    signed_in = viewer is not None and viewer.id == user.id
    head = (f'<link rel="stylesheet" href="/static/check-in.css?v={CSS_VERSION}">'
            '<meta name="referrer" content="same-origin">')
    response = page("Check-in", "A quick check-in on titles in your OmniTrackr library.", "/check-in",
                    _content(user, items, token, settled, pick, picked, saved, suggestions, signed_in, data["source"]),
                    indexable=False, head=head, member=True)  # a member's page: no "create a free account" prompt
    return _private(response)


@router.post("/check-in/{token}", include_in_schema=False)
async def check_in_answer(token: str, request: Request, db: Session = Depends(get_db)):
    user, data = _member(db, token)
    if user is None:
        return _expired()
    try:
        form = await request.form()
    except Exception:
        form = {}
    raw_item = str(form.get("item", ""))[:3]
    choice = str(form.get("choice", ""))[:16]
    size = len(data["items"])
    if not raw_item.isdigit() or int(raw_item) >= size:
        return _private(RedirectResponse(_here("?r=1"), status_code=303))
    index = int(raw_item)
    settled = _indexes(str(form.get("ok", "")), size)
    category, item_id = data["items"][index]
    source = data["source"]
    action, score = choice, None
    if "-" in choice:
        action, _, raw_score = choice.partition("-")
        score = int(raw_score) if raw_score.isdigit() and 1 <= int(raw_score) <= 10 else None
        if score is None:
            return _private(RedirectResponse(_here(f"?r=1#ci-{index}"), status_code=303))
    target = f"?saved={index}&r=1"
    current = check_in.aligned_items(db, user.id, [(category, item_id)])[0]
    was_answered = index in settled or bool(current and current["finished"] and current["rating"] is not None)
    if action == "open":
        # "Finished it" opens the score buttons first; nothing is saved yet.
        query = f"?pick={index}&a=finished&r=1&ok={','.join(map(str, settled))}"
        return _private(RedirectResponse(_here(f"{query}#ci-{index}"), status_code=303))
    if action in ("still", "noscore"):
        settled = sorted(set(settled) | {index})
        if action == "still":
            check_in.count(f"still_{source}")
            if source == "week" and index not in _indexes(str(form.get("ok", "")), size):
                try:
                    from .. import your_week
                    your_week.note_logged(db, user)
                except Exception:
                    db.rollback()
    elif action in ("finished", "rate"):
        before = current
        result = check_in.answer(db, user, category, item_id, action, score)
        if result is None:
            return _private(RedirectResponse(_here("?r=1"), status_code=303))
        if action == "finished" and before and not before["finished"]:
            check_in.count(f"finished_{source}")
        if score is not None:
            check_in.count(f"rated_{source}")
    else:
        return _private(RedirectResponse(_here(f"?r=1#ci-{index}"), status_code=303))
    try:
        visits.record_visit(db, user)  # answering is opening OmniTrackr, signed in or not
    except Exception:
        db.rollback()
    items = [item for item in enumerate(check_in.aligned_items(db, user.id, data["items"])) if item[1] is not None]
    done = [i for i, item in items if i in settled or (item["finished"] and item["rating"] is not None)]
    if items and len(done) == len(items) and not was_answered:
        check_in.count(f"all_done_{source}")
    target += f"&ok={','.join(map(str, settled))}#ci-{index}"
    return _private(RedirectResponse(_here(target), status_code=303))
